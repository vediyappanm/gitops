"""Data models for CI/CD Failure Monitor"""
from datetime import datetime
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field, asdict
from enum import Enum


class FailureStatus(str, Enum):
    """Status of a failure record"""
    DETECTED = "detected"
    ANALYZED = "analyzed"
    APPROVED = "approved"
    REMEDIATED = "remediated"
    FAILED = "failed"


class ApprovalStatus(str, Enum):
    """Status of an approval request"""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


class ActionType(str, Enum):
    """Type of audit action"""
    DETECTION = "detection"
    ANALYSIS = "analysis"
    VALIDATION = "validation"
    APPROVAL = "approval"
    REMEDIATION = "remediation"
    ERROR = "error"


class FailureCategory(str, Enum):
    """Category of failure"""
    DEPENDENCY = "dependency"
    TIMEOUT = "timeout"
    CONFIG = "config"
    FLAKY_TEST = "flaky_test"
    INFRASTRUCTURE = "infrastructure"
    TEST_FAILURE = "test_failure"
    BUILD_ERROR = "build_error"
    LINT_ERROR = "lint_error"


@dataclass
class FailureRecord:
    """Record of a detected workflow failure"""
    failure_id: str
    repository: str
    workflow_run_id: str
    branch: str
    commit_sha: str
    failure_reason: str
    logs: str
    status: FailureStatus = FailureStatus.DETECTED
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        data = asdict(self)
        data['status'] = self.status.value
        data['created_at'] = self.created_at.isoformat()
        data['updated_at'] = self.updated_at.isoformat()
        return data


@dataclass
class AnalysisResult:
    """Result of AI analysis of a failure"""
    failure_id: str
    error_type: str  # "DEVOPS" or "DEVELOPER"
    category: FailureCategory
    risk_score: int
    confidence: int
    proposed_fix: str
    effort_estimate: str
    affected_components: List[str]
    reasoning: str
    files_to_modify: List[str] = field(default_factory=list)
    fix_commands: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        data = asdict(self)
        data['category'] = self.category.value
        data['created_at'] = self.created_at.isoformat()
        return data


@dataclass
class ApprovalRequest:
    """Request for human approval of a remediation"""
    request_id: str
    failure_id: str
    analysis_id: str
    status: ApprovalStatus = ApprovalStatus.PENDING
    requested_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    slack_message_ts: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        data = asdict(self)
        data['status'] = self.status.value
        data['requested_at'] = self.requested_at.isoformat()
        if self.expires_at:
            data['expires_at'] = self.expires_at.isoformat()
        if self.approved_at:
            data['approved_at'] = self.approved_at.isoformat()
        return data


@dataclass
class AuditLogEntry:
    """Entry in the audit trail"""
    log_id: str
    timestamp: datetime
    actor: str
    action_type: ActionType
    failure_id: Optional[str]
    request_id: Optional[str]
    details: Dict[str, Any]
    outcome: str
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        data['action_type'] = self.action_type.value
        return data


@dataclass
class MetricsRecord:
    """Metrics for a processed failure"""
    metric_id: str
    failure_id: str
    detection_latency_ms: int
    analysis_latency_ms: int
    remediation_latency_ms: int
    total_latency_ms: int
    remediation_success: bool
    category: str
    repository: str
    risk_score: int
    recorded_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        data = asdict(self)
        data['recorded_at'] = self.recorded_at.isoformat()
        return data


@dataclass
class Feedback:
    """Classification feedback record"""
    failure_id: str
    predicted_category: str
    actual_category: str
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data
