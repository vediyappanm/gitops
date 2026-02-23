"""Audit Logger component for comprehensive logging"""
import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from src.models import AuditLogEntry, ActionType
from src.database import Database

logger = logging.getLogger(__name__)


class AuditLogger:
    """Record all actions and decisions for compliance"""

    def __init__(self, database: Database):
        """Initialize audit logger"""
        self.database = database

    def log_action(self, action_type: ActionType, actor: str, details: Dict[str, Any], 
                  outcome: str, failure_id: Optional[str] = None, 
                  request_id: Optional[str] = None, error_message: Optional[str] = None) -> str:
        """Record an action in the audit trail"""
        log_id = str(uuid.uuid4())
        
        entry = AuditLogEntry(
            log_id=log_id,
            timestamp=datetime.now(timezone.utc),
            actor=actor,
            action_type=action_type,
            failure_id=failure_id,
            request_id=request_id,
            details=details,
            outcome=outcome,
            error_message=error_message
        )
        
        self.database.store_audit_log(entry)
        logger.debug(f"Audit log created: {log_id}")
        
        return log_id

    def log_failure_detection(self, failure_id: str, details: Dict[str, Any]) -> str:
        """Log failure detection"""
        return self.log_action(
            action_type=ActionType.DETECTION,
            actor="monitor",
            details=details,
            outcome="success",
            failure_id=failure_id
        )

    def log_analysis(self, failure_id: str, analysis_details: Dict[str, Any]) -> str:
        """Log AI analysis"""
        return self.log_action(
            action_type=ActionType.ANALYSIS,
            actor="analyzer",
            details=analysis_details,
            outcome="success",
            failure_id=failure_id
        )

    def log_safety_gate_result(self, failure_id: str, passed: bool, reason: str) -> str:
        """Log safety gate validation"""
        return self.log_action(
            action_type=ActionType.VALIDATION,
            actor="safety_gate",
            details={"passed": passed, "reason": reason},
            outcome="success" if passed else "failure",
            failure_id=failure_id
        )

    def log_approval_request(self, request_id: str, failure_id: str, details: Dict[str, Any]) -> str:
        """Log approval request"""
        return self.log_action(
            action_type=ActionType.APPROVAL,
            actor="approval_workflow",
            details=details,
            outcome="pending",
            failure_id=failure_id,
            request_id=request_id
        )

    def log_approval_response(self, request_id: str, failure_id: str, approved: bool, 
                            approver: str) -> str:
        """Log approval response"""
        return self.log_action(
            action_type=ActionType.APPROVAL,
            actor=approver,
            details={"approved": approved},
            outcome="success",
            failure_id=failure_id,
            request_id=request_id
        )

    def log_remediation(self, failure_id: str, success: bool, result: str) -> str:
        """Log remediation execution"""
        return self.log_action(
            action_type=ActionType.REMEDIATION,
            actor="executor",
            details={"result": result},
            outcome="success" if success else "failure",
            failure_id=failure_id
        )

    def log_error(self, error_message: str, actor: str, details: Dict[str, Any]) -> str:
        """Log an error"""
        return self.log_action(
            action_type=ActionType.ERROR,
            actor=actor,
            details=details,
            outcome="failure",
            error_message=error_message
        )

    def query_logs(self, filters: Optional[Dict[str, Any]] = None) -> List[AuditLogEntry]:
        """Query audit logs with filters"""
        return self.database.query_audit_logs(filters)
