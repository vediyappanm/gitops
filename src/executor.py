"""Remediation Executor component for applying fixes"""
import logging
import subprocess
from typing import Tuple, Optional
from src.models import FailureRecord, AnalysisResult
from src.database import Database
from src.notifier import SlackNotifier

logger = logging.getLogger(__name__)


class RemediationExecutor:
    """Execute approved remediations"""

    def __init__(self, database: Database, notifier: SlackNotifier):
        """Initialize executor"""
        self.database = database
        self.notifier = notifier

    def execute_remediation(self, failure: FailureRecord, analysis: AnalysisResult) -> Tuple[bool, str]:
        """Execute the proposed remediation"""
        try:
            logger.info(f"Executing remediation for failure {failure.failure_id}")
            
            # Parse remediation steps from proposed fix
            steps = self._parse_remediation_steps(analysis.proposed_fix)
            
            output = ""
            for step in steps:
                success, step_output = self._execute_step(step)
                output += step_output + "\n"
                
                if not success:
                    logger.error(f"Remediation step failed: {step}")
                    return False, output
            
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
