"""Approval Workflow component for managing human approvals"""
import logging
import uuid
from datetime import datetime, timedelta
from typing import Optional, Callable
from src.models import ApprovalRequest, ApprovalStatus, FailureRecord, AnalysisResult
from src.database import Database
from src.config_manager import ConfigurationManager
from src.telegram_notifier import TelegramNotifier

logger = logging.getLogger(__name__)


class ApprovalWorkflow:
    """Manage human approval for high-risk remediations"""

    def __init__(self, database: Database, config: ConfigurationManager, notifier: TelegramNotifier):
        """Initialize approval workflow"""
        self.database = database
        self.config = config
        self.notifier = notifier
        self.approval_callbacks: dict = {}

    def request_approval(self, failure: FailureRecord, analysis: AnalysisResult) -> ApprovalRequest:
        """Request approval for a remediation"""
        request_id = str(uuid.uuid4())
        timeout_hours = self.config.get_approval_timeout()
        
        request = ApprovalRequest(
            request_id=request_id,
            failure_id=failure.failure_id,
            analysis_id=failure.failure_id,  # Using failure_id as analysis_id for simplicity
            status=ApprovalStatus.PENDING,
            requested_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(hours=timeout_hours)
        )
        
        # Send Slack notification
        message_ts = self.notifier.send_approval_request(failure, analysis, request_id)
        if message_ts:
            request.slack_message_ts = message_ts
        
        self.database.store_approval_request(request)
        logger.info(f"Approval requested for failure {failure.failure_id}")
        
        return request

    def handle_approval(self, request_id: str, approved_by: str) -> bool:
        """Handle approval response"""
        request = self.database.get_approval_request(request_id)
        if not request:
            logger.error(f"Approval request not found: {request_id}")
            return False
        
        request.status = ApprovalStatus.APPROVED
        request.approved_by = approved_by
        request.approved_at = datetime.utcnow()
        
        self.database.store_approval_request(request)
        logger.info(f"Approval granted for request {request_id} by {approved_by}")
        
        # Call approval callback if registered
        if request_id in self.approval_callbacks:
            self.approval_callbacks[request_id](request)
        
        return True

    def handle_rejection(self, request_id: str, rejected_by: str) -> bool:
        """Handle rejection response"""
        request = self.database.get_approval_request(request_id)
        if not request:
            logger.error(f"Approval request not found: {request_id}")
            return False
        
        request.status = ApprovalStatus.REJECTED
        request.approved_by = rejected_by
        request.approved_at = datetime.utcnow()
        
        self.database.store_approval_request(request)
        logger.info(f"Approval rejected for request {request_id} by {rejected_by}")
        
        return True

    def check_approval_timeout(self, request_id: str) -> bool:
        """Check if approval has timed out"""
        request = self.database.get_approval_request(request_id)
        if not request:
            return False
        
        if request.status != ApprovalStatus.PENDING:
            return False
        
        if datetime.utcnow() > request.expires_at:
            request.status = ApprovalStatus.EXPIRED
            self.database.store_approval_request(request)
            
            # Send escalation alert
            self.notifier.send_critical_alert(
                f"Approval request {request_id} for failure {request.failure_id} has expired"
            )
            
            logger.warning(f"Approval request {request_id} has expired")
            return True
        
        return False

    def register_approval_callback(self, request_id: str, callback: Callable) -> None:
        """Register a callback to be called when approval is granted"""
        self.approval_callbacks[request_id] = callback

    def wait_for_approval(self, request_id: str, timeout_seconds: int = 300) -> Optional[ApprovalRequest]:
        """Wait for approval response (blocking)"""
        import time
        start_time = datetime.utcnow()
        
        while True:
            request = self.database.get_approval_request(request_id)
            
            if request and request.status != ApprovalStatus.PENDING:
                return request
            
            elapsed = (datetime.utcnow() - start_time).total_seconds()
            if elapsed > timeout_seconds:
                return None
            
            time.sleep(5)  # Check every 5 seconds
