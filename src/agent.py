"""Main agent orchestrator for CI/CD Failure Monitor"""
import logging
import time
from datetime import datetime
from typing import List, Optional
from src.github_client import GitHubClient
from src.database import Database
from src.config_manager import ConfigurationManager
from src.monitor import Monitor
from src.analyzer import Analyzer
from src.safety_gate import SafetyGate
from src.approval_workflow import ApprovalWorkflow
from src.executor import RemediationExecutor
from src.pr_creator import PRCreator
from src.telegram_notifier import TelegramNotifier
from src.audit_logger import AuditLogger
from src.metrics_tracker import MetricsTracker
from src.error_handler import ErrorHandler
from src.models import FailureStatus, ActionType
from src.dry_run_mode import DryRunMode
from src.snapshot_manager import SnapshotManager
from src.health_checker import HealthChecker
from src.circuit_breaker import CircuitBreaker, FailureSignature
from src.metric_alerting import MetricAlertingEngine
from src.blast_radius import BlastRadiusEstimator
from src.failure_pattern_memory import FailurePatternMemory
from prometheus_client import start_http_server, Counter, Gauge
from src.explainability import ExplainabilityLayer
from src.repo_personality import RepositoryPersonalityProfiler
from src.github_approval import GitHubNativeApproval
from src.health_report import HealthReportGenerator
from src.web_dashboard import WebDashboard
from src.notifier import SlackNotifier

logger = logging.getLogger(__name__)


class CICDFailureMonitorAgent:
    """Main orchestrator for CI/CD Failure Monitor"""

    def __init__(self, config: ConfigurationManager, db: Database, dry_run: bool = False):
        """Initialize the agent"""
        self.config = config
        self.db = db
        self.dry_run_enabled = dry_run
        
        # Initialize Prometheus metrics
        self.metrics_failures = Counter('cicd_failures_total', 'Total failures detected')
        self.metrics_fixes = Counter('cicd_fixes_total', 'Total auto-fixes created')
        self.metrics_risk = Gauge('cicd_last_risk_score', 'Risk score of last analyzed failure')
        
        # Start metrics server
        try:
            start_http_server(9091)
            logger.info("Prometheus metrics server started on port 9091")
        except Exception as e:
            logger.warning(f"Failed to start metrics server: {e}")
        
        # Initialize components
        self.github_client = GitHubClient(config.config.github_token)
        self.metrics_tracker = MetricsTracker(db)
        if config.config.telegram_bot_token:
            self.notifier = TelegramNotifier(config.config.telegram_bot_token, config)
        else:
            self.notifier = SlackNotifier(config.config.slack_bot_token, config)
        
        # Initialize safety features
        self.dry_run_mode = DryRunMode(enabled=dry_run)
        self.snapshot_manager = SnapshotManager(db, self.github_client, retention_days=7)
        self.health_checker = HealthChecker(db, self.github_client, delay_minutes=5)
        self.circuit_breaker = CircuitBreaker(db, failure_threshold=3, auto_reset_hours=24)
        
        # Initialize advanced features
        self.blast_radius_estimator = BlastRadiusEstimator(self.github_client, db)
        self.failure_pattern_memory = FailurePatternMemory(
            db, 
            openai_api_key=config.config.groq_api_key,
            use_local_embeddings=True
        )
        self.metric_alerting = MetricAlertingEngine(
            db,
            self.notifier,
            self.metrics_tracker,
            success_rate_threshold=80.0,
            resolution_time_multiplier=2.0
        )
        
        # Initialize quality-of-life features
        
        self.explainability = ExplainabilityLayer(db)
        self.repo_personality = RepositoryPersonalityProfiler(db)
        self.github_approval = GitHubNativeApproval(self.github_client, db, config)
        self.health_report_generator = HealthReportGenerator(
            db,
            self.metrics_tracker,
            self.notifier,
            self.circuit_breaker,
            self.failure_pattern_memory
        )
        
        # Initialize web dashboard (runs in background thread)
        self.web_dashboard = WebDashboard(
            db,
            self.metrics_tracker,
            self.circuit_breaker,
            self.failure_pattern_memory
        )
        
        # Setup health check callbacks
        self.health_checker.on_health_check_pass(self._on_health_check_pass)
        self.health_checker.on_health_check_fail(self._on_health_check_fail)
        
        self.monitor = Monitor(self.github_client, db, config)
        self.analyzer = Analyzer(config.config.groq_api_key, db, self.github_client, 
                                self.failure_pattern_memory)
        self.safety_gate = SafetyGate(config, self.circuit_breaker)
        self.approval_workflow = ApprovalWorkflow(db, config, self.notifier)
        self.executor = RemediationExecutor(db, self.notifier, self.snapshot_manager, 
                                           self.health_checker, self.dry_run_mode)
        self.pr_creator = PRCreator(self.github_client, self.analyzer)
        self.audit_logger = AuditLogger(db)
        self.error_handler = ErrorHandler(self.notifier)
        
        self.is_running = False
        
        if dry_run:
            logger.info("=" * 60)
            logger.info("DRY-RUN MODE ENABLED")
            logger.info("No actual changes will be made to repositories")
            logger.info("=" * 60)
        
        logger.info("Quality-of-life features initialized:")
        logger.info("  - Web Dashboard (API on port 8000)")
        logger.info("  - Explainability Layer")
        logger.info("  - Repository Personality Profiler")
        logger.info("  - GitHub Native Approval")
        logger.info("  - Health Report Generator (scheduled Monday 9 AM)")

    def start(self, repositories: List[str]) -> None:
        """Start the agent"""
        self.is_running = True
        logger.info("Starting CI/CD Failure Monitor Agent")
        
        try:
            # Pass process_failure as callback to monitor
            self.monitor.start_polling(repositories, callback=self.process_failure)
        except KeyboardInterrupt:
            logger.info("Agent interrupted by user")
            self.stop()
        except Exception as e:
            logger.error(f"Agent error: {e}")
            self.error_handler.handle_error(e, "agent_start", "agent")
            self.stop()

    def stop(self) -> None:
        """Stop the agent"""
        self.is_running = False
        self.monitor.stop_polling()
        self.github_client.close()
        
        # Shutdown health report scheduler
        try:
            self.health_report_generator.shutdown()
        except Exception as e:
            logger.warning(f"Failed to shutdown health report generator: {e}")
        
        # Shutdown web dashboard
        try:
            self.web_dashboard.shutdown()
        except Exception as e:
            logger.warning(f"Failed to shutdown web dashboard: {e}")
        
        # Generate dry-run report if enabled
        if self.dry_run_mode.is_enabled():
            report = self.dry_run_mode.generate_report()
            logger.info("Dry-run session completed")
        
        logger.info("CI/CD Failure Monitor Agent stopped")

    def process_failure(self, failure_id: str) -> None:
        """Process a single failure through the pipeline"""
        try:
            # Get failure from database
            failure = self.db.get_failure(failure_id)
            if not failure:
                logger.error(f"Failure not found: {failure_id}")
                return
            
            # Skip if already failed (e.g. missing logs)
            if failure.status == FailureStatus.FAILED:
                logger.info(f"Skipping processing for failure {failure_id} as logs are unavailable")
                return

            # Increment metrics
            self.metrics_failures.inc()
            
            # Log detection
            self.audit_logger.log_failure_detection(
                failure_id,
                {
                    "repository": failure.repository,
                    "branch": failure.branch,
                    "commit": failure.commit_sha
                }
            )
            
            # Analyze failure
            logger.info(f"Analyzing failure {failure_id}")
            analysis = self.analyzer.analyze_failure(failure)
            
            # Update risk metric
            self.metrics_risk.set(analysis.risk_score)
            
            # Log analysis
            self.audit_logger.log_analysis(
                failure_id,
                {
                    "error_type": analysis.error_type,
                    "category": analysis.category.value,
                    "risk_score": analysis.risk_score,
                    "confidence": analysis.confidence
                }
            )
            
            # Send analysis notification (non-blocking)
            try:
                self.notifier.send_analysis_notification(failure, analysis)
            except Exception as notify_err:
                logger.warning(f"Slack notification failed (non-critical): {notify_err}")
            
            # DECISION POINT: DevOps vs Developer
            if analysis.error_type == "DEVELOPER":
                # Developer issue - send notification only
                logger.info(f"Developer issue detected for failure {failure_id}")
                self._handle_developer_issue(failure, analysis)
            else:
                # DevOps issue - auto-fix and create PR
                logger.info(f"DevOps issue detected for failure {failure_id}")
                self._handle_devops_issue(failure, analysis)
        
        except Exception as e:
            logger.error(f"Error processing failure {failure_id}: {e}")
            self.error_handler.handle_error(e, f"process_failure_{failure_id}", "agent")
            self.audit_logger.log_error(str(e), "agent", {"failure_id": failure_id})

    def _handle_developer_issue(self, failure, analysis) -> None:
        """Handle developer code issues - send notification only"""
        logger.info(f"Handling developer issue for failure {failure.failure_id}")
        
        # Send developer notification (non-blocking)
        try:
            self.notifier.send_developer_notification(failure, analysis)
            logger.info(f"Slack notification sent for DEVELOPER issue {failure.failure_id}")
        except Exception as notify_err:
            logger.warning(f"Slack notification failed (non-critical): {notify_err}")
            logger.info(f"DEVELOPER ISSUE DETECTED:\n"
                       f"  Repository: {failure.repository}\n"
                       f"  Branch: {failure.branch}\n"
                       f"  Category: {analysis.category.value}\n"
                       f"  Reason: {failure.failure_reason}\n"
                       f"  Suggested Fix: {analysis.proposed_fix}")
        
        # Log action
        self.audit_logger.log_action(
            action_type=ActionType.DETECTION,
            actor="agent",
            details={
                "error_type": "DEVELOPER",
                "category": analysis.category.value,
                "reason": analysis.reasoning
            },
            outcome="success",
            failure_id=failure.failure_id
        )
        
        # Update failure status
        failure.status = FailureStatus.ANALYZED
        self.db.store_failure(failure)

    def _handle_devops_issue(self, failure, analysis) -> None:
        """Handle DevOps issues - auto-fix and create PR"""
        logger.info(f"Handling DevOps issue for failure {failure.failure_id}")
        
        # Record classification decision in explainability layer
        try:
            self.explainability.record_classification_decision(
                failure_id=failure.failure_id,
                chosen_category=analysis.category.value,
                chosen_error_type="DEVOPS",
                confidence=analysis.confidence,
                reasoning=analysis.reasoning,
                alternatives=[],  # Would be populated by analyzer
                context={
                    "repository": failure.repository,
                    "branch": failure.branch,
                    "workflow": failure.workflow_run_id
                },
                model="gpt-4o",
                response_time_ms=0
            )
        except Exception as e:
            logger.warning(f"Failed to record classification decision: {e}")
        
        # Get repository personality for confidence adjustment
        try:
            confidence_adjustment = self.repo_personality.get_adjusted_confidence(
                repository=failure.repository,
                failure_category=analysis.category.value,
                failure_time=failure.created_at
            )
            
            if confidence_adjustment != 0:
                original_confidence = analysis.confidence
                analysis.confidence = max(0, min(100, analysis.confidence + int(confidence_adjustment * 100)))
                logger.info(f"Adjusted confidence from {original_confidence} to {analysis.confidence} "
                          f"based on repo personality (adjustment={confidence_adjustment:+.2f})")
        except Exception as e:
            logger.warning(f"Failed to adjust confidence based on repo personality: {e}")
        
        # Create failure signature for circuit breaker
        failure_sig = FailureSignature(
            repository_id=failure.repository,
            workflow_name=failure.workflow_run_id,
            error_pattern=failure.failure_reason,
            branch=failure.branch
        )
        
        # Check circuit breaker
        if not self.circuit_breaker.is_remediation_allowed(failure_sig):
            logger.warning(f"Circuit breaker BLOCKED remediation for {failure.repository}")
            
            # Send escalation alert
            if not self.dry_run_mode.is_enabled():
                try:
                    self.notifier.send_circuit_breaker_alert(failure, analysis, 
                        self.circuit_breaker.get_circuit_status(failure.repository))
                except Exception as e:
                    logger.warning(f"Failed to send circuit breaker alert: {e}")
            else:
                self.dry_run_mode.intercept_notification(
                    "critical",
                    f"Circuit breaker triggered for {failure.repository}"
                )
            
            # Update failure status
            failure.status = FailureStatus.FAILED
            self.db.store_failure(failure)
            return
        
        # Check safety gates
        logger.info(f"Validating safety gates for failure {failure.failure_id}")
        safe, reason = self.safety_gate.validate_remediation(failure, analysis)
        
        # Estimate blast radius
        blast_radius = None
        try:
            blast_radius = self.blast_radius_estimator.estimate_blast_radius(
                repository=failure.repository,
                branch=failure.branch,
                files_to_modify=analysis.files_to_modify,
                failure_category=analysis.category.value
            )
            
            logger.info(f"Blast radius estimated: score={blast_radius.blast_radius_score}, "
                       f"impact={blast_radius.impact_level.value}, "
                       f"services={len(blast_radius.affected_services)}")
            
            # Record risk assessment decision
            try:
                self.explainability.record_risk_assessment_decision(
                    failure_id=failure.failure_id,
                    risk_score=analysis.risk_score,
                    reasoning=f"Risk score based on: category={analysis.category.value}, "
                             f"blast_radius={blast_radius.blast_radius_score}, "
                             f"confidence={analysis.confidence}",
                    factors={
                        "category": analysis.category.value,
                        "blast_radius_score": blast_radius.blast_radius_score,
                        "affected_services": len(blast_radius.affected_services),
                        "files_to_modify": len(analysis.files_to_modify)
                    },
                    model="blast_radius_estimator"
                )
            except Exception as e:
                logger.warning(f"Failed to record risk assessment: {e}")
            
            # Add blast radius to safety gate decision
            if blast_radius.blast_radius_score >= 8:
                safe = False
                reason = f"High blast radius (score={blast_radius.blast_radius_score}): {blast_radius.reasoning}"
                logger.warning(f"Remediation blocked by high blast radius: {reason}")
        except Exception as e:
            logger.error(f"Failed to estimate blast radius: {e}")
        
        # Log safety gate result
        self.audit_logger.log_safety_gate_result(failure.failure_id, safe, reason)
        
        if safe:
            # Create PR with fix
            logger.info(f"Creating PR for failure {failure.failure_id}")
            
            if self.dry_run_mode.is_enabled():
                # Simulate PR creation
                pr_url = self.dry_run_mode.intercept_pr_creation(
                    repo=failure.repository,
                    branch=f"fix/{failure.failure_id}",
                    title=f"Auto-fix: {analysis.category.value}",
                    body=analysis.proposed_fix
                )
                success = True
            else:
                success, pr_url = self.pr_creator.create_fix_pr(failure, analysis)
            
            if success:
                # Increment metrics
                self.metrics_fixes.inc()
                
                # Record success in circuit breaker
                self.circuit_breaker.record_success(failure_sig)
                
                # Store successful pattern in memory
                try:
                    self.failure_pattern_memory.store_pattern(
                        failure_id=failure.failure_id,
                        repository=failure.repository,
                        branch=failure.branch,
                        failure_reason=failure.failure_reason,
                        failure_category=analysis.category.value,
                        proposed_fix=analysis.proposed_fix,
                        fix_successful=True,
                        files_modified=analysis.files_to_modify,
                        fix_commands=analysis.fix_commands,
                        risk_score=analysis.risk_score,
                        resolution_time_ms=0  # Would be calculated from metrics
                    )
                    logger.info(f"Stored successful fix pattern for {failure.failure_id}")
                except Exception as e:
                    logger.error(f"Failed to store pattern: {e}")
                
                # Send success notification
                if not self.dry_run_mode.is_enabled():
                    try:
                        self.notifier.send_devops_fix_notification(failure, analysis, pr_url, True)
                    except Exception as notify_err:
                        logger.warning(f"Slack notification failed (non-critical): {notify_err}")
                else:
                    self.dry_run_mode.intercept_notification(
                        "alerts",
                        f"PR created successfully: {pr_url}"
                    )
                
                logger.info(f"PR CREATED SUCCESSFULLY: {pr_url}")
                
                # Log action
                self.audit_logger.log_action(
                    action_type=ActionType.REMEDIATION,
                    actor="pr_creator",
                    details={
                        "pr_url": pr_url,
                        "category": analysis.category.value
                    },
                    outcome="success",
                    failure_id=failure.failure_id
                )
                
                # Update failure status
                failure.status = FailureStatus.REMEDIATED
            else:
                # Record failure in circuit breaker
                transition = self.circuit_breaker.record_failure(failure_sig)
                
                # Check if circuit breaker was triggered
                if transition.to_state.value == "open":
                    logger.critical(f"CIRCUIT BREAKER TRIGGERED for {failure.repository}")
                    if not self.dry_run_mode.is_enabled():
                        try:
                            self.notifier.send_circuit_breaker_alert(failure, analysis,
                                self.circuit_breaker.get_circuit_status(failure.repository))
                        except Exception as e:
                            logger.warning(f"Failed to send circuit breaker alert: {e}")
                    else:
                        self.dry_run_mode.intercept_notification(
                            "critical",
                            f"Circuit breaker triggered for {failure.repository}"
                        )
                
                # Send failure notification
                if not self.dry_run_mode.is_enabled():
                    try:
                        self.notifier.send_devops_fix_notification(failure, analysis, pr_url, False)
                    except Exception as notify_err:
                        logger.warning(f"Slack notification failed (non-critical): {notify_err}")
                else:
                    self.dry_run_mode.intercept_notification(
                        "alerts",
                        f"PR creation failed: {pr_url}"
                    )
                
                logger.warning(f"PR creation failed for failure {failure.failure_id}: {pr_url}")
                failure.status = FailureStatus.FAILED
            
            self.db.store_failure(failure)
        else:
            # Use GitHub native approval instead of Slack
            logger.info(f"Requesting GitHub approval for failure {failure.failure_id}")
            
            try:
                # Create PR first (in pending state)
                if not self.dry_run_mode.is_enabled():
                    success, pr_url = self.pr_creator.create_fix_pr(failure, analysis)
                    if success:
                        # Extract PR number from URL
                        pr_number = int(pr_url.split('/')[-1])
                        
                        # Create GitHub approval request
                        approval_request = self.github_approval.create_approval_request(
                            failure_id=failure.failure_id,
                            repository=failure.repository,
                            pr_number=pr_number,
                            analysis_summary=analysis.reasoning,
                            risk_score=analysis.risk_score
                        )
                        
                        logger.info(f"GitHub approval request created: {approval_request.request_id}")
                    else:
                        logger.error(f"Failed to create PR for approval: {pr_url}")
                        failure.status = FailureStatus.FAILED
                        self.db.store_failure(failure)
                        return
                else:
                    # Dry-run mode
                    self.dry_run_mode.log_action(
                        action_type="APPROVAL_REQUEST",
                        component="github_approval",
                        description=f"Would request GitHub approval for {failure.failure_id}",
                        data={"reason": reason, "risk_score": analysis.risk_score}
                    )
                    # Define a dummy approval request for audit logging
                    from src.models import ApprovalRequest, ApprovalStatus
                    approval_request = ApprovalRequest(
                        request_id=f"dryrun-app-{failure.failure_id}",
                        failure_id=failure.failure_id,
                        analysis_id=failure.failure_id, # Simplified
                        status=ApprovalStatus.PENDING
                    )
            except Exception as e:
                logger.error(f"Failed to create GitHub approval request: {e}")
                # Fallback to old Slack approval
                approval_request = self.approval_workflow.request_approval(failure, analysis)
            
            # Log approval request
            self.audit_logger.log_approval_request(
                approval_request.request_id if hasattr(approval_request, 'request_id') else "unknown",
                failure.failure_id,
                {"reason": reason}
            )
            
            # Update failure status
            failure.status = FailureStatus.ANALYZED
            self.db.store_failure(failure)

    def handle_approval_response(self, request_id: str, approved: bool, approver: str) -> None:
        """Handle approval response from Slack"""
        try:
            approval_request = self.db.get_approval_request(request_id)
            if not approval_request:
                logger.error(f"Approval request not found: {request_id}")
                return
            
            if approved:
                # Handle approval
                self.approval_workflow.handle_approval(request_id, approver)
                
                # Log approval
                self.audit_logger.log_approval_response(
                    request_id,
                    approval_request.failure_id,
                    True,
                    approver
                )
                
                # Get failure and analysis
                failure = self.db.get_failure(approval_request.failure_id)
                analysis = self.db.get_analysis(approval_request.failure_id)
                
                if failure and analysis:
                    # Create PR with fix
                    success, pr_url = self.pr_creator.create_fix_pr(failure, analysis)
                    
                    # Send notification
                    self.notifier.send_devops_fix_notification(failure, analysis, pr_url, success)
                    
                    # Update failure status
                    failure.status = FailureStatus.REMEDIATED if success else FailureStatus.FAILED
                    self.db.store_failure(failure)
            else:
                # Handle rejection
                self.approval_workflow.handle_rejection(request_id, approver)
                
                # Log rejection
                self.audit_logger.log_approval_response(
                    request_id,
                    approval_request.failure_id,
                    False,
                    approver
                )
        
        except Exception as e:
            logger.error(f"Error handling approval response: {e}")
            self.error_handler.handle_error(e, f"handle_approval_{request_id}", "agent")

    def _on_health_check_pass(self, remediation_id: str) -> None:
        """Callback when health check passes"""
        logger.info(f"Health check PASSED for remediation {remediation_id}")
        
    def _on_health_check_fail(self, remediation_id: str) -> None:
        """Callback when health check fails - trigger rollback"""
        logger.critical(f"Health check FAILED for remediation {remediation_id} - triggering rollback")
        
        try:
            # Get health check metadata to find snapshot_id
            check_data = self.db.get_health_check(remediation_id)
            if not check_data or not check_data.get("snapshot_id"):
                logger.error(f"Cannot perform rollback: No snapshot found for remediation {remediation_id}")
                return
            
            snapshot_id = check_data["snapshot_id"]
            repo = check_data["repository"]
            
            # Send critical alert
            if not self.dry_run_mode.is_enabled():
                try:
                    self.notifier.send_rollback_alert(remediation_id, "Post-remediation health check failed")
                except Exception as e:
                    logger.error(f"Failed to send rollback alert: {e}")
            else:
                self.dry_run_mode.intercept_notification(
                    "critical",
                    f"Rollback alert for {remediation_id}"
                )
            
            # Execute rollback
            if self.dry_run_mode.is_enabled():
                self.dry_run_mode.log_action(
                    action_type="ROLLBACK",
                    component="agent",
                    description=f"Would rollback remediation {remediation_id} using snapshot {snapshot_id}",
                    data={"remediation_id": remediation_id, "snapshot_id": snapshot_id}
                )
                success = True
            else:
                rollback_result = self.snapshot_manager.rollback(snapshot_id)
                success = rollback_result.success
                
                if success:
                    logger.info(f"Rollback successful for remediation {remediation_id}")
                else:
                    logger.error(f"Rollback failed for remediation {remediation_id}: {rollback_result.error}")
            
            # Update status in DB
            if success:
                self.db.update_health_check_rollback(remediation_id, True)
            
            # Log action in audit trail
            self.audit_logger.log_action(
                action_type=ActionType.REMEDIATION,
                actor="health_checker",
                details={
                    "remediation_id": remediation_id,
                    "snapshot_id": snapshot_id,
                    "action": "rollback",
                    "reason": "health_check_failed",
                    "repository": repo
                },
                outcome="success" if success else "failed",
                failure_id=None
            )
        except Exception as e:
            logger.error(f"Error handling health check failure and rollback: {e}")
            self.error_handler.handle_error(e, f"rollback_{remediation_id}", "agent")
