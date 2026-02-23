"""Snapshot Manager for repository state snapshots and rollback"""
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from enum import Enum
from apscheduler.schedulers.background import BackgroundScheduler

logger = logging.getLogger(__name__)


class SnapshotStatus(str, Enum):
    """Status of a snapshot"""
    ACTIVE = "active"
    ROLLED_BACK = "rolled_back"
    EXPIRED = "expired"
    DELETED = "deleted"


@dataclass
class FileSnapshot:
    """Snapshot of a single file"""
    path: str
    content_hash: str
    content: str


@dataclass
class Snapshot:
    """Repository state snapshot"""
    id: str
    repository_id: str
    remediation_id: str
    commit_sha: str
    branch_name: str
    modified_files: List[FileSnapshot] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = None
    status: SnapshotStatus = SnapshotStatus.ACTIVE
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "repository_id": self.repository_id,
            "remediation_id": self.remediation_id,
            "commit_sha": self.commit_sha,
            "branch_name": self.branch_name,
            "modified_files": [
                {"path": f.path, "content_hash": f.content_hash}
                for f in self.modified_files
            ],
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "status": self.status.value,
            "metadata": self.metadata
        }


@dataclass
class RollbackResult:
    """Result of a rollback operation"""
    success: bool
    snapshot_id: str
    files_reverted: List[str]
    commit_sha: str
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "snapshot_id": self.snapshot_id,
            "files_reverted": self.files_reverted,
            "commit_sha": self.commit_sha,
            "error": self.error
        }


class SnapshotManager:
    """Manages repository snapshots for rollback capability"""

    def __init__(self, database, github_client, retention_days: int = 7):
        """Initialize snapshot manager"""
        self.database = database
        self.github_client = github_client
        self.retention_days = retention_days
        self.snapshots: Dict[str, Snapshot] = {}
        
        # Setup automatic cleanup scheduler
        self.scheduler = BackgroundScheduler()
        self.scheduler.add_job(
            self.cleanup_expired_snapshots,
            'cron',
            hour=2,  # Run at 2 AM daily
            minute=0,
            id='snapshot_cleanup',
            replace_existing=True
        )
        self.scheduler.start()
        
        logger.info(f"SnapshotManager initialized with {retention_days} day retention")
        logger.info("Automatic snapshot cleanup scheduled daily at 2:00 AM")

    def create_snapshot(self, repository: str, remediation_id: str, 
                       commit_sha: str, branch: str, 
                       files_to_modify: List[str]) -> Snapshot:
        """Create a snapshot of repository state before remediation"""
        try:
            snapshot_id = str(uuid.uuid4())
            logger.info(f"Creating snapshot {snapshot_id} for {repository} at {commit_sha}")
            
            # Capture file contents
            file_snapshots = []
            for file_path in files_to_modify:
                try:
                    content = self.github_client.get_file_contents(repository, file_path, commit_sha)
                    if content:
                        file_snapshots.append(FileSnapshot(
                            path=file_path,
                            content_hash=self._hash_content(content),
                            content=content
                        ))
                except Exception as e:
                    logger.warning(f"Could not snapshot file {file_path}: {e}")
            
            # Create snapshot
            snapshot = Snapshot(
                id=snapshot_id,
                repository_id=repository,
                remediation_id=remediation_id,
                commit_sha=commit_sha,
                branch_name=branch,
                modified_files=file_snapshots,
                created_at=datetime.now(timezone.utc),
                expires_at=datetime.now(timezone.utc) + timedelta(days=self.retention_days),
                status=SnapshotStatus.ACTIVE,
                metadata={
                    "file_count": len(file_snapshots),
                    "files": files_to_modify
                }
            )
            
            # Store snapshot
            self.snapshots[snapshot_id] = snapshot
            self.database.store_snapshot(snapshot)
            
            logger.info(f"Snapshot {snapshot_id} created with {len(file_snapshots)} files")
            return snapshot
        
        except Exception as e:
            logger.error(f"Failed to create snapshot: {e}")
            raise

    def rollback(self, snapshot_id: str) -> RollbackResult:
        """Rollback repository to snapshot state"""
        try:
            logger.info(f"Starting rollback for snapshot {snapshot_id}")
            
            # Get snapshot
            snapshot = self.get_snapshot(snapshot_id)
            if not snapshot:
                error_msg = f"Snapshot {snapshot_id} not found"
                logger.error(error_msg)
                return RollbackResult(
                    success=False,
                    snapshot_id=snapshot_id,
                    files_reverted=[],
                    commit_sha="",
                    error=error_msg
                )
            
            if snapshot.status != SnapshotStatus.ACTIVE:
                error_msg = f"Snapshot {snapshot_id} is not active (status: {snapshot.status})"
                logger.error(error_msg)
                return RollbackResult(
                    success=False,
                    snapshot_id=snapshot_id,
                    files_reverted=[],
                    commit_sha=snapshot.commit_sha,
                    error=error_msg
                )
            
            # Revert files using GitHub API
            reverted_files = []
            failed_files = []
            
            for file_snapshot in snapshot.modified_files:
                try:
                    logger.info(f"Reverting file: {file_snapshot.path} to hash {file_snapshot.content_hash}")
                    
                    # Get current file metadata (needed for GitHub API update)
                    current_file = self.github_client.get_file_metadata(
                        snapshot.repository_id,
                        file_snapshot.path,
                        snapshot.branch_name
                    )
                    
                    if current_file:
                        # Update file back to snapshot content
                        success = self.github_client.update_file(
                            repo=snapshot.repository_id,
                            path=file_snapshot.path,
                            content=file_snapshot.content,
                            message=f"[ROLLBACK] Revert {file_snapshot.path} to snapshot {snapshot_id[:8]}",
                            branch=snapshot.branch_name,
                            sha=current_file['sha']  # Current file SHA for update
                        )
                        
                        if success:
                            reverted_files.append(file_snapshot.path)
                            logger.info(f"Successfully reverted {file_snapshot.path}")
                        else:
                            failed_files.append(file_snapshot.path)
                            logger.error(f"Failed to revert {file_snapshot.path}")
                    else:
                        # File doesn't exist anymore, create it
                        success = self.github_client.create_file(
                            repo=snapshot.repository_id,
                            path=file_snapshot.path,
                            content=file_snapshot.content,
                            message=f"[ROLLBACK] Restore {file_snapshot.path} from snapshot {snapshot_id[:8]}",
                            branch=snapshot.branch_name
                        )
                        
                        if success:
                            reverted_files.append(file_snapshot.path)
                            logger.info(f"Successfully restored {file_snapshot.path}")
                        else:
                            failed_files.append(file_snapshot.path)
                            logger.error(f"Failed to restore {file_snapshot.path}")
                
                except Exception as e:
                    logger.error(f"Failed to revert file {file_snapshot.path}: {e}")
                    failed_files.append(file_snapshot.path)
            
            # Update snapshot status
            snapshot.status = SnapshotStatus.ROLLED_BACK
            self.database.store_snapshot(snapshot)
            
            # Determine overall success
            success = len(failed_files) == 0
            
            if success:
                logger.info(f"Rollback completed successfully: {len(reverted_files)} files reverted")
            else:
                logger.warning(f"Rollback partially completed: {len(reverted_files)} succeeded, {len(failed_files)} failed")
            
            return RollbackResult(
                success=success,
                snapshot_id=snapshot_id,
                files_reverted=reverted_files,
                commit_sha=snapshot.commit_sha,
                error=f"Failed to revert {len(failed_files)} files: {failed_files}" if failed_files else None
            )
        
        except Exception as e:
            error_msg = f"Rollback failed: {e}"
            logger.error(error_msg)
            return RollbackResult(
                success=False,
                snapshot_id=snapshot_id,
                files_reverted=[],
                commit_sha="",
                error=error_msg
            )

    def delete_snapshot(self, snapshot_id: str) -> bool:
        """Delete a snapshot"""
        try:
            snapshot = self.get_snapshot(snapshot_id)
            if snapshot:
                snapshot.status = SnapshotStatus.DELETED
                self.database.store_snapshot(snapshot)
                if snapshot_id in self.snapshots:
                    del self.snapshots[snapshot_id]
                logger.info(f"Snapshot {snapshot_id} deleted")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to delete snapshot {snapshot_id}: {e}")
            return False

    def get_snapshot(self, snapshot_id: str) -> Optional[Snapshot]:
        """Get a snapshot by ID"""
        if snapshot_id in self.snapshots:
            return self.snapshots[snapshot_id]
        
        # Try to load from database
        snapshot = self.database.get_snapshot(snapshot_id)
        if snapshot:
            self.snapshots[snapshot_id] = snapshot
        return snapshot

    def list_snapshots(self, repository: str) -> List[Snapshot]:
        """List all snapshots for a repository"""
        return [s for s in self.snapshots.values() if s.repository_id == repository]

    def cleanup_expired_snapshots(self) -> int:
        """Clean up expired snapshots"""
        try:
            now = datetime.now(timezone.utc)
            expired_count = 0
            
            for snapshot_id, snapshot in list(self.snapshots.items()):
                if snapshot.expires_at and snapshot.expires_at < now:
                    snapshot.status = SnapshotStatus.EXPIRED
                    self.database.store_snapshot(snapshot)
                    del self.snapshots[snapshot_id]
                    expired_count += 1
            
            logger.info(f"Cleaned up {expired_count} expired snapshots")
            return expired_count
        except Exception as e:
            logger.error(f"Failed to cleanup snapshots: {e}")
            return 0

    def shutdown(self) -> None:
        """Shutdown the snapshot manager and cleanup scheduler"""
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("Snapshot cleanup scheduler stopped")

    def _hash_content(self, content: str) -> str:
        """Generate hash of file content"""
        import hashlib
        return hashlib.sha256(content.encode()).hexdigest()
