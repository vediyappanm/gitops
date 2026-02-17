"""Monitor component for polling GitHub Actions failures"""
import logging
import time
import uuid
from datetime import datetime
from typing import List, Optional
from src.github_client import GitHubClient
from src.database import Database
from src.models import FailureRecord, FailureStatus
from src.config_manager import ConfigurationManager

logger = logging.getLogger(__name__)


class Monitor:
    """Monitor GitHub Actions for workflow failures"""

    def __init__(self, github_client: GitHubClient, database: Database, config: ConfigurationManager):
        """Initialize monitor"""
        self.github_client = github_client
        self.database = database
        self.config = config
        self.is_running = False

    def start_polling(self, repositories: List[str], callback=None) -> None:
        """Start continuous polling loop"""
        self.is_running = True
        logger.info("Starting monitoring loop")
        
        while self.is_running:
            try:
                failures = self.poll_once(repositories)
                
                # Process detected failures
                if callback and failures:
                    for failure in failures:
                        try:
                            callback(failure.failure_id)
                        except Exception as e:
                            logger.error(f"Error in failure callback: {e}")
                
                interval = self.config.get_polling_interval() * 60  # Convert to seconds
                logger.debug(f"Sleeping for {interval} seconds")
                time.sleep(interval)
            except Exception as e:
                logger.error(f"Error in polling loop: {e}")
                time.sleep(60)  # Wait before retrying

    def stop_polling(self) -> None:
        """Stop the polling loop"""
        self.is_running = False
        logger.info("Stopping monitoring loop")

    def poll_once(self, repositories: List[str]) -> List[FailureRecord]:
        """Execute a single poll cycle"""
        detected_failures = []
        
        for repo in repositories:
            try:
                logger.debug(f"Polling repository: {repo}")
                runs = self.github_client.get_failed_workflow_runs(repo)
                
                for run in runs:
                    run_id = run.get("id")
                    
                    # Check if already processed
                    if self.database.failure_exists(str(run_id)):
                        logger.debug(f"Run {run_id} already processed, skipping")
                        continue
                    
                    # Fetch complete details
                    failure = self._process_workflow_run(repo, run)
                    if failure:
                        detected_failures.append(failure)
                        self.database.store_failure(failure)
                        logger.info(f"Detected new failure: {failure.failure_id}")
            
            except Exception as e:
                logger.error(f"Error polling repository {repo}: {e}")
                continue
        
        return detected_failures

    def _process_workflow_run(self, repo: str, run: dict) -> Optional[FailureRecord]:
        """Process a workflow run and extract failure details"""
        try:
            run_id = run.get("id")
            
            # Get complete run details
            details = self.github_client.get_workflow_run_details(repo, run_id)
            
            # Get logs
            logs = self.github_client.get_workflow_run_logs(repo, run_id)
            
            if not logs:
                logger.warning(f"Logs for run {run_id} are unavailable (possibly expired)")
                return FailureRecord(
                    failure_id=str(uuid.uuid4()),
                    repository=repo,
                    workflow_run_id=str(run_id),
                    branch=details.get("head_branch", "unknown"),
                    commit_sha=details.get("head_commit", {}).get("sha", "unknown"),
                    failure_reason="Logs unavailable (expired or deleted)",
                    logs="",
                    status=FailureStatus.FAILED,
                    created_at=datetime.utcnow()
                )
            
            # Extract failure reason
            failure_reason = self._extract_failure_reason(logs)
            
            # Create failure record
            failure = FailureRecord(
                failure_id=str(uuid.uuid4()),
                repository=repo,
                workflow_run_id=str(run_id),
                branch=details.get("head_branch", "unknown"),
                commit_sha=details.get("head_commit", {}).get("sha", "unknown"),
                failure_reason=failure_reason,
                logs=logs,
                status=FailureStatus.DETECTED,
                created_at=datetime.utcnow()
            )
            
            return failure
        except Exception as e:
            logger.error(f"Error processing workflow run {run_id}: {e}")
            return None

    def _extract_failure_reason(self, logs: str) -> str:
        """Extract failure reason from workflow logs"""
        # Simple heuristic-based extraction
        lines = logs.split('\n')
        
        # Look for common error patterns
        error_keywords = [
            "error", "failed", "timeout", "exception", "fatal",
            "panic", "segmentation fault", "out of memory"
        ]
        
        for line in lines:
            lower_line = line.lower()
            for keyword in error_keywords:
                if keyword in lower_line:
                    return line.strip()[:200]  # Return first 200 chars
        
        # If no specific error found, return last non-empty line
        for line in reversed(lines):
            if line.strip():
                return line.strip()[:200]
        
        return "Unknown failure reason"
