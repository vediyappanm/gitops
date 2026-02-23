"""Dry-Run Mode component for simulating operations without execution"""
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class SimulatedAction:
    """Record of a simulated action"""
    timestamp: datetime
    action_type: str
    component: str
    description: str
    would_execute: bool
    simulated_data: Dict[str, Any]
    branch: Optional[str] = None
    base: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "action_type": self.action_type,
            "component": self.component,
            "description": self.description,
            "would_execute": self.would_execute,
            "simulated_data": self.simulated_data,
            "branch": self.branch,
            "base": self.base
        }


@dataclass
class DryRunReport:
    """Summary report of dry-run session"""
    session_id: str
    started_at: datetime
    ended_at: datetime
    total_actions: int
    prs_that_would_be_created: int
    files_modified: List[str] = field(default_factory=list)
    git_operations: List[str] = field(default_factory=list)
    notifications_sent: int = 0
    actions: List[SimulatedAction] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "started_at": self.started_at.isoformat(),
            "ended_at": self.ended_at.isoformat(),
            "total_actions": self.total_actions,
            "prs_that_would_be_created": self.prs_that_would_be_created,
            "files_modified": self.files_modified,
            "git_operations": self.git_operations,
            "notifications_sent": self.notifications_sent,
            "actions": [action.to_dict() for action in self.actions]
        }


class DryRunMode:
    """Manages dry-run mode operations"""

    def __init__(self, enabled: bool = False):
        """Initialize dry-run mode"""
        self.enabled = enabled
        self.actions: List[SimulatedAction] = []
        self.session_id = f"dryrun_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
        self.started_at = datetime.now(timezone.utc)
        
        if self.enabled:
            logger.info(f"[DRY-RUN] Mode ENABLED - Session: {self.session_id}")
            logger.info("[DRY-RUN] No actual changes will be made to repositories")

    def is_enabled(self) -> bool:
        """Check if dry-run mode is enabled"""
        return self.enabled

    def log_action(self, action_type: str, component: str, description: str, 
                   would_execute: bool = True, data: Dict[str, Any] = None, 
                   branch: str = None, base: str = None) -> None:
        """Log a simulated action"""
        if not self.enabled:
            return
        
        action = SimulatedAction(
            timestamp=datetime.now(timezone.utc),
            action_type=action_type,
            component=component,
            description=description,
            would_execute=would_execute,
            simulated_data=data or {},
            branch=branch,
            base=base
        )
        
        self.actions.append(action)
        branch_info = f" [branch: {branch}]" if branch else ""
        base_info = f" [base: {base}]" if base else ""
        logger.info(f"[DRY-RUN]{branch_info}{base_info} {component}: {description}")
        if data:
            logger.debug(f"[DRY-RUN] Data: {data}")

    def intercept_pr_creation(self, repo: str, branch: str, title: str, body: str, 
                            base: str = "main") -> str:
        """Intercept PR creation"""
        if not self.enabled:
            return None
        
        self.log_action(
            action_type="PR_CREATION",
            component="pr_creator",
            description=f"Would create PR in {repo} on branch {branch}",
            branch=branch,
            data={
                "repository": repo,
                "branch": branch,
                "base": base,
                "title": title,
                "body_preview": body[:200] + "..." if len(body) > 200 else body
            },
            base=base
        )
        
        return f"[DRY-RUN] PR would be created: {repo}#{branch}"

    def intercept_file_modification(self, repo: str, files: List[str], operation: str) -> None:
        """Intercept file modification operations"""
        if not self.enabled:
            return
        
        self.log_action(
            action_type="FILE_MODIFICATION",
            component="github_client",
            description=f"Would {operation} {len(files)} file(s) in {repo}",
            data={
                "repository": repo,
                "operation": operation,
                "files": files
            }
        )

    def intercept_git_operation(self, operation: str, repo: str, details: Dict[str, Any]) -> None:
        """Intercept Git operations"""
        if not self.enabled:
            return
        
        branch = details.get('branch')
        self.log_action(
            action_type="GIT_OPERATION",
            component="git",
            description=f"Would execute: {operation} on {repo}",
            branch=branch,
            data=details
        )

    def intercept_notification(self, channel: str, message: str, branch: str = None) -> None:
        """Intercept notification sending"""
        if not self.enabled:
            return
        
        self.log_action(
            action_type="NOTIFICATION",
            component="notifier",
            description=f"Would send notification to {channel}",
            branch=branch,
            data={
                "channel": channel,
                "message_preview": message[:100] + "..." if len(message) > 100 else message
            }
        )

    def generate_report(self) -> DryRunReport:
        """Generate summary report"""
        ended_at = datetime.now(timezone.utc)
        
        # Count different action types
        pr_count = sum(1 for a in self.actions if a.action_type == "PR_CREATION")
        notification_count = sum(1 for a in self.actions if a.action_type == "NOTIFICATION")
        
        # Extract file modifications
        files_modified = []
        git_operations = []
        for action in self.actions:
            if action.action_type == "FILE_MODIFICATION":
                files_modified.extend(action.simulated_data.get("files", []))
            elif action.action_type == "GIT_OPERATION":
                git_operations.append(action.simulated_data.get("operation", "unknown"))
        
        report = DryRunReport(
            session_id=self.session_id,
            started_at=self.started_at,
            ended_at=ended_at,
            total_actions=len(self.actions),
            prs_that_would_be_created=pr_count,
            files_modified=list(set(files_modified)),
            git_operations=list(set(git_operations)),
            notifications_sent=notification_count,
            actions=self.actions
        )
        
        # Log summary
        logger.info(f"[DRY-RUN] ===== SESSION SUMMARY =====")
        logger.info(f"[DRY-RUN] Session ID: {report.session_id}")
        logger.info(f"[DRY-RUN] Duration: {(ended_at - self.started_at).total_seconds():.2f}s")
        logger.info(f"[DRY-RUN] Total Actions: {report.total_actions}")
        logger.info(f"[DRY-RUN] PRs that would be created: {report.prs_that_would_be_created}")
        logger.info(f"[DRY-RUN] Notifications that would be sent: {report.notifications_sent}")
        logger.info(f"[DRY-RUN] ===========================")
        
        return report
