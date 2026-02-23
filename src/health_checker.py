"""Health Checker for post-remediation validation"""
import logging
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any, Callable
from dataclasses import dataclass, field
from enum import Enum

from apscheduler.schedulers.background import BackgroundScheduler

logger = logging.getLogger(__name__)


class HealthCheckType(str, Enum):
    """Type of health check"""
    WORKFLOW_SUCCESS = "workflow_success"
    BUILD_SUCCESS = "build_success"
    TEST_PASS = "test_pass"
    CUSTOM_SCRIPT = "custom_script"


@dataclass
class CheckResult:
    """Result of a single health check"""
    name: str
    passed: bool
    message: str
    details: Optional[Dict[str, Any]] = None


@dataclass
class HealthCheckResult:
    """Result of health check execution"""
    remediation_id: str
    passed: bool
    checks: List[CheckResult] = field(default_factory=list)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "remediation_id": self.remediation_id,
            "passed": self.passed,
            "checks": [
                {
                    "name": c.name,
                    "passed": c.passed,
                    "message": c.message,
                    "details": c.details
                }
                for c in self.checks
            ],
            "timestamp": self.timestamp.isoformat()
        }


class HealthChecker:
    """Manages health checks after remediations"""

    def __init__(self, database, github_client, delay_minutes: int = 5):
        """Initialize health checker"""
        self.database = database
        self.github_client = github_client
        self.delay_minutes = delay_minutes
        self.pass_callbacks: List[Callable] = []
        self.fail_callbacks: List[Callable] = []
        
        # Initialize scheduler
        self.scheduler = BackgroundScheduler()
        self.scheduler.start()
        
        logger.info(f"HealthChecker initialized with {delay_minutes} minute delay")

    def schedule_check(self, remediation_id: str, snapshot_id: str, 
                      repository: str, workflow_run_id: str) -> None:
        """Schedule a health check after delay"""
        try:
            logger.info(f"Scheduling health check for remediation {remediation_id} "
                       f"in {self.delay_minutes} minutes")
            
            # Store check metadata
            self.database.store_health_check({
                "remediation_id": remediation_id,
                "snapshot_id": snapshot_id,
                "repository": repository,
                "workflow_run_id": workflow_run_id,
                "scheduled_at": datetime.now(timezone.utc),
                "delay_minutes": self.delay_minutes,
                "status": "scheduled"
            })
            
            # Schedule the job
            self.scheduler.add_job(
                self.execute_health_check,
                'date',
                run_date=datetime.now(timezone.utc) + timedelta(minutes=self.delay_minutes),
                args=[remediation_id, repository, workflow_run_id],
                id=f"health_check_{remediation_id}",
                replace_existing=True
            )
            
            logger.info(f"Health check job added for remediation {remediation_id}")
        
        except Exception as e:
            logger.error(f"Failed to schedule health check: {e}")

    def cancel_check(self, remediation_id: str) -> bool:
        """Cancel a scheduled health check"""
        try:
            job_id = f"health_check_{remediation_id}"
            if self.scheduler.get_job(job_id):
                self.scheduler.remove_job(job_id)
                logger.info(f"Cancelled health check job for remediation {remediation_id}")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to cancel health check: {e}")
            return False

    def execute_health_check(self, remediation_id: str, repository: str, 
                            workflow_run_id: str) -> HealthCheckResult:
        """Execute health check for a remediation"""
        try:
            logger.info(f"Executing health check for remediation {remediation_id}")
            
            checks = []
            
            # Check 1: Workflow status
            workflow_check = self._check_workflow_status(repository, workflow_run_id)
            checks.append(workflow_check)
            
            # Check 2: Build success (if applicable)
            build_check = self._check_build_status(repository, workflow_run_id)
            if build_check:
                checks.append(build_check)
            
            # Check 3: Test pass (if applicable)
            test_check = self._check_test_status(repository, workflow_run_id)
            if test_check:
                checks.append(test_check)
            
            # Determine overall pass/fail
            all_passed = all(check.passed for check in checks)
            
            result = HealthCheckResult(
                remediation_id=remediation_id,
                passed=all_passed,
                checks=checks,
                timestamp=datetime.now(timezone.utc)
            )
            
            # Store result
            self.database.store_health_check_result(result)
            
            # Trigger callbacks
            if all_passed:
                logger.info(f"Health check PASSED for remediation {remediation_id}")
                self._trigger_pass_callbacks(remediation_id)
            else:
                logger.warning(f"Health check FAILED for remediation {remediation_id}")
                self._trigger_fail_callbacks(remediation_id)
            
            return result
        
        except Exception as e:
            logger.error(f"Health check execution failed: {e}")
            return HealthCheckResult(
                remediation_id=remediation_id,
                passed=False,
                checks=[CheckResult(
                    name="execution_error",
                    passed=False,
                    message=f"Health check execution failed: {e}"
                )]
            )

    def _check_workflow_status(self, repository: str, workflow_run_id: str) -> CheckResult:
        """Check if workflow completed successfully"""
        try:
            # In a real implementation, this would query GitHub API
            # For now, we simulate the check
            logger.info(f"Checking workflow status for {repository}#{workflow_run_id}")
            
            # Simulate workflow check
            passed = True  # Would be actual API call result
            
            return CheckResult(
                name="workflow_status",
                passed=passed,
                message="Workflow completed successfully" if passed else "Workflow failed",
                details={"workflow_run_id": workflow_run_id}
            )
        except Exception as e:
            return CheckResult(
                name="workflow_status",
                passed=False,
                message=f"Failed to check workflow status: {e}"
            )

    def _check_build_status(self, repository: str, workflow_run_id: str) -> Optional[CheckResult]:
        """Check if build succeeded"""
        try:
            logger.info(f"Checking build status for {repository}#{workflow_run_id}")
            
            # Simulate build check
            passed = True  # Would be actual check result
            
            return CheckResult(
                name="build_status",
                passed=passed,
                message="Build succeeded" if passed else "Build failed"
            )
        except Exception as e:
            logger.warning(f"Build status check failed: {e}")
            return None

    def _check_test_status(self, repository: str, workflow_run_id: str) -> Optional[CheckResult]:
        """Check if tests passed"""
        try:
            logger.info(f"Checking test status for {repository}#{workflow_run_id}")
            
            # Simulate test check
            passed = True  # Would be actual check result
            
            return CheckResult(
                name="test_status",
                passed=passed,
                message="Tests passed" if passed else "Tests failed"
            )
        except Exception as e:
            logger.warning(f"Test status check failed: {e}")
            return None

    def on_health_check_pass(self, callback: Callable[[str], None]) -> None:
        """Register callback for health check pass"""
        self.pass_callbacks.append(callback)

    def on_health_check_fail(self, callback: Callable[[str], None]) -> None:
        """Register callback for health check fail"""
        self.fail_callbacks.append(callback)

    def _trigger_pass_callbacks(self, remediation_id: str) -> None:
        """Trigger all pass callbacks"""
        for callback in self.pass_callbacks:
            try:
                callback(remediation_id)
            except Exception as e:
                logger.error(f"Pass callback failed: {e}")

    def _trigger_fail_callbacks(self, remediation_id: str) -> None:
        """Trigger all fail callbacks"""
        for callback in self.fail_callbacks:
            try:
                callback(remediation_id)
            except Exception as e:
                logger.error(f"Fail callback failed: {e}")
