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
from src.notifier import SlackNotifier
from src.audit_logger import AuditLogger
from src.metrics_tracker import MetricsTracker
from src.error_handler import ErrorHandler
from src.models import FailureStatus, ActionType
from prometheus_client import start_http_server, Counter, Gauge

logger = logging.getLogger(__name__)


class CICDFailureMonitorAgent:
    """Main orchestrator for CI/CD Failure Monitor"""

    def __init__(self, config: ConfigurationManager, db: Database):
        """Initialize the agent"""
        self.config = config
        self.db = db
        
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
        self.notifier = SlackNotifier(config.config.slack_bot_token, config)
        self.monitor = Monitor(self.github_client, db, config)
        self.analyzer = Analyzer(config.config.groq_api_key, db, self.github_client)
        self.safety_gate = SafetyGate(config)
        self.approval_workflow = ApprovalWorkflow(db, config, self.notifier)
        self.executor = RemediationExecutor(db, self.notifier)
        self.pr_creator = PRCreator(self.github_client, self.analyzer)
        self.audit_logger = AuditLogger(db)
        self.metrics_tracker = MetricsTracker(db)
        self.error_handler = ErrorHandler(self.notifier)
        
        self.is_running = False

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
        
        # Check safety gates
        logger.info(f"Validating safety gates for failure {failure.failure_id}")
        safe, reason = self.safety_gate.validate_remediation(failure, analysis)
        
        # Log safety gate result
        self.audit_logger.log_safety_gate_result(failure.failure_id, safe, reason)
        
        if safe:
            # Create PR with fix
            logger.info(f"Creating PR for failure {failure.failure_id}")
            success, pr_url = self.pr_creator.create_fix_pr(failure, analysis)
            
            if success:
                # Increment metrics
                self.metrics_fixes.inc()
                
                # Send success notification with PR link (non-blocking)
                try:
                    self.notifier.send_devops_fix_notification(failure, analysis, pr_url, True)
                except Exception as notify_err:
                    logger.warning(f"Slack notification failed (non-critical): {notify_err}")
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
                # Send failure notification (non-blocking)
                try:
                    self.notifier.send_devops_fix_notification(failure, analysis, pr_url, False)
                except Exception as notify_err:
                    logger.warning(f"Slack notification failed (non-critical): {notify_err}")
                logger.warning(f"PR creation failed for failure {failure.failure_id}: {pr_url}")
                failure.status = FailureStatus.FAILED
            
            self.db.store_failure(failure)
        else:
            # Request approval for high-risk DevOps issues
            logger.info(f"Requesting approval for failure {failure.failure_id}")
            approval_request = self.approval_workflow.request_approval(failure, analysis)
            
            # Log approval request
            self.audit_logger.log_approval_request(
                approval_request.request_id,
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
