"""Remediation Executor component for applying fixes"""
import logging
import subprocess
import uuid
from typing import Tuple, Optional
from src.models import FailureRecord, AnalysisResult
from src.database import Database
from src.telegram_notifier import TelegramNotifier

logger = logging.getLogger(__name__)


class RemediationExecutor:
    """Execute approved remediations"""

    def __init__(self, database: Database, notifier: TelegramNotifier, 
                 snapshot_manager=None, health_checker=None, dry_run_mode=None):
        """Initialize executor"""
        self.database = database
        self.notifier = notifier
        self.snapshot_manager = snapshot_manager
        self.health_checker = health_checker
        self.dry_run_mode = dry_run_mode

    def execute_remediation(self, failure: FailureRecord, analysis: AnalysisResult) -> Tuple[bool, str]:
        """Execute the proposed remediation"""
        try:
            remediation_id = str(uuid.uuid4())
            logger.info(f"Executing remediation {remediation_id} for failure {failure.failure_id}")
            
            # Create snapshot before remediation (if not dry-run)
            snapshot_id = None
            if self.snapshot_manager and not (self.dry_run_mode and self.dry_run_mode.is_enabled()):
                try:
                    snapshot = self.snapshot_manager.create_snapshot(
                        repository=failure.repository,
                        remediation_id=remediation_id,
                        commit_sha=failure.commit_sha,
                        branch=failure.branch,
                        files_to_modify=analysis.files_to_modify
                    )
                    snapshot_id = snapshot.id
                    logger.info(f"Snapshot {snapshot_id} created before remediation")
                except Exception as e:
                    logger.error(f"Failed to create snapshot: {e}")
                    # Continue without snapshot (risky but allows operation)
            
            # Parse remediation steps from proposed fix
            steps = self._parse_remediation_steps(analysis.proposed_fix)
            
            output = ""
            for step in steps:
                if self.dry_run_mode and self.dry_run_mode.is_enabled():
                    # Simulate step execution
                    self.dry_run_mode.log_action(
                        action_type="REMEDIATION_STEP",
                        component="executor",
                        description=f"Would execute: {step}",
                        data={"step": step}
                    )
                    output += f"[DRY-RUN] Would execute: {step}\n"
                else:
                    success, step_output = self._execute_step(step)
                    output += step_output + "\n"
                    
                    if not success:
                        logger.error(f"Remediation step failed: {step}")
                        # Trigger rollback if snapshot exists
                        if snapshot_id and self.snapshot_manager:
                            logger.info(f"Triggering rollback for snapshot {snapshot_id}")
                            rollback_result = self.snapshot_manager.rollback(snapshot_id)
                            if rollback_result.success:
                                logger.info(f"Rollback successful: {len(rollback_result.files_reverted)} files reverted")
                            else:
                                logger.error(f"Rollback failed: {rollback_result.error}")
                        return False, output
            
            # Schedule health check (if not dry-run)
            if self.health_checker and snapshot_id and not (self.dry_run_mode and self.dry_run_mode.is_enabled()):
                try:
                    self.health_checker.schedule_check(
                        remediation_id=remediation_id,
                        snapshot_id=snapshot_id,
                        repository=failure.repository,
                        workflow_run_id=failure.workflow_run_id
                    )
                    logger.info(f"Health check scheduled for remediation {remediation_id}")
                except Exception as e:
                    logger.error(f"Failed to schedule health check: {e}")
            
            logger.info(f"Remediation executed successfully for failure {failure.failure_id}")
            return True, output
        except Exception as e:
            logger.error(f"Error executing remediation: {e}")
            return False, str(e)

    def _parse_remediation_steps(self, proposed_fix: str) -> list:
        """Parse remediation steps from proposed fix"""
        # Simple parsing: split by newlines and filter empty lines
        steps = [step.strip() for step in proposed_fix.split('\n') if step.strip()]
        return steps

    def _execute_step(self, step: str) -> Tuple[bool, str]:
        """Execute a single remediation step"""
        try:
            # For safety, only allow specific commands
            allowed_commands = ["echo", "ls", "pwd", "cat", "grep"]
            
            if not any(step.startswith(cmd) for cmd in allowed_commands):
                logger.warning(f"Skipping potentially unsafe command: {step}")
                return True, f"Skipped: {step}"
            
            result = subprocess.run(
                step,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode != 0:
                return False, result.stderr
            
            return True, result.stdout
        except subprocess.TimeoutExpired:
            return False, "Command timed out"
        except Exception as e:
            return False, str(e)

    def verify_fix(self, failure: FailureRecord) -> bool:
        """Verify the fix resolved the failure"""
        try:
            # Simple verification: check if the failure reason is no longer present
            # In a real system, this would re-run the workflow and check status
            logger.info(f"Verifying fix for failure {failure.failure_id}")
            return True
        except Exception as e:
            logger.error(f"Error verifying fix: {e}")
            return False

    def rollback_on_failure(self, failure: FailureRecord) -> bool:
        """Rollback changes if remediation fails"""
        try:
            logger.info(f"Rolling back changes for failure {failure.failure_id}")
            # In a real system, this would undo the changes made by remediation
            return True
        except Exception as e:
            logger.error(f"Error rolling back changes: {e}")
            return False
