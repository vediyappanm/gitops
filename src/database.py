"""Database layer for CI/CD Failure Monitor"""
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Dict, Any
from sqlalchemy import create_engine, Column, String, Integer, DateTime, Boolean, Text, JSON, Enum as SQLEnum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from src.models import (
    FailureRecord, AnalysisResult, ApprovalRequest, AuditLogEntry, MetricsRecord, Feedback,
    FailureStatus, ApprovalStatus, ActionType, FailureCategory
)

logger = logging.getLogger(__name__)

Base = declarative_base()


class FailureRecordORM(Base):
    """ORM model for failure records"""
    __tablename__ = "failures"

    failure_id = Column(String, primary_key=True)
    repository = Column(String, nullable=False)
    workflow_run_id = Column(String, nullable=False, unique=True)
    branch = Column(String, nullable=False)
    commit_sha = Column(String, nullable=False)
    failure_reason = Column(String, nullable=False)
    logs = Column(Text, nullable=False)
    status = Column(SQLEnum(FailureStatus), default=FailureStatus.DETECTED)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class AnalysisResultORM(Base):
    """ORM model for analysis results"""
    __tablename__ = "analysis_results"

    failure_id = Column(String, primary_key=True)
    error_type = Column(String, nullable=False)
    category = Column(SQLEnum(FailureCategory), nullable=False)
    risk_score = Column(Integer, nullable=False)
    confidence = Column(Integer, nullable=False)
    proposed_fix = Column(Text, nullable=False)
    effort_estimate = Column(String, nullable=False)
    affected_components = Column(JSON, nullable=False)
    reasoning = Column(Text, nullable=False)
    files_to_modify = Column(JSON, nullable=False)
    fix_commands = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class ApprovalRequestORM(Base):
    """ORM model for approval requests"""
    __tablename__ = "approval_requests"

    request_id = Column(String, primary_key=True)
    failure_id = Column(String, nullable=False)
    analysis_id = Column(String, nullable=False)
    status = Column(SQLEnum(ApprovalStatus), default=ApprovalStatus.PENDING)
    requested_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    expires_at = Column(DateTime(timezone=True), nullable=True)
    approved_by = Column(String, nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    slack_message_ts = Column(String, nullable=True)


class AuditLogEntryORM(Base):
    """ORM model for audit log entries"""
    __tablename__ = "audit_logs"

    log_id = Column(String, primary_key=True)
    timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    actor = Column(String, nullable=False)
    action_type = Column(SQLEnum(ActionType), nullable=False)
    failure_id = Column(String, nullable=True)
    request_id = Column(String, nullable=True)
    details = Column(JSON, nullable=False)
    outcome = Column(String, nullable=False)
    error_message = Column(String, nullable=True)


class MetricsRecordORM(Base):
    """ORM model for metrics records"""
    __tablename__ = "metrics"

    metric_id = Column(String, primary_key=True)
    failure_id = Column(String, nullable=False)
    detection_latency_ms = Column(Integer, nullable=False)
    analysis_latency_ms = Column(Integer, nullable=False)
    remediation_latency_ms = Column(Integer, nullable=False)
    total_latency_ms = Column(Integer, nullable=False)
    remediation_success = Column(Boolean, nullable=False)
    category = Column(String, nullable=False)
    repository = Column(String, nullable=False)
    risk_score = Column(Integer, nullable=False)
    recorded_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class FeedbackORM(Base):
    """ORM model for classification feedback"""
    __tablename__ = "feedback"

    id = Column(Integer, primary_key=True, autoincrement=True)
    failure_id = Column(String, nullable=False)
    predicted_category = Column(String, nullable=False)
    actual_category = Column(String, nullable=False)
    timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class SnapshotORM(Base):
    """ORM model for repository snapshots"""
    __tablename__ = "snapshots"

    id = Column(String, primary_key=True)
    repository_id = Column(String, nullable=False)
    remediation_id = Column(String, nullable=False)
    commit_sha = Column(String, nullable=False)
    branch_name = Column(String, nullable=False)
    modified_files = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    expires_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(String, nullable=False)
    snapshot_metadata = Column(JSON, nullable=False)


class HealthCheckORM(Base):
    """ORM model for health checks"""
    __tablename__ = "health_checks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    remediation_id = Column(String, nullable=False)
    snapshot_id = Column(String, nullable=True)
    repository = Column(String, nullable=False)
    workflow_run_id = Column(String, nullable=False)
    scheduled_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    executed_at = Column(DateTime(timezone=True), nullable=True)
    passed = Column(Boolean, nullable=True)
    checks = Column(JSON, nullable=True)
    triggered_rollback = Column(Boolean, default=False)
    status = Column(String, default="scheduled")
    delay_minutes = Column(Integer, default=5)


class CircuitBreakerORM(Base):
    """ORM model for circuit breaker state"""
    __tablename__ = "circuit_breakers"

    failure_signature = Column(String, primary_key=True)
    repository_id = Column(String, nullable=False)
    workflow_name = Column(String, nullable=False)
    error_pattern = Column(String, nullable=False)
    branch = Column(String, default="main")
    state = Column(String, nullable=False)
    failure_count = Column(Integer, default=0)
    last_failure_at = Column(DateTime(timezone=True), nullable=True)
    opened_at = Column(DateTime(timezone=True), nullable=True)
    auto_reset_at = Column(DateTime(timezone=True), nullable=True)
    manually_reset_at = Column(DateTime(timezone=True), nullable=True)
    manually_reset_by = Column(String, nullable=True)
    history = Column(JSON, nullable=False)


class FailurePatternORM(Base):
    """ORM model for failure patterns"""
    __tablename__ = "failure_patterns"

    pattern_id = Column(String, primary_key=True)
    repository = Column(String, nullable=False)
    branch = Column(String, nullable=False)
    failure_reason = Column(Text, nullable=False)
    failure_category = Column(String, nullable=False)
    error_signature = Column(String, nullable=False)
    proposed_fix = Column(Text, nullable=False)
    fix_successful = Column(Boolean, nullable=False)
    files_modified = Column(JSON, nullable=False)
    fix_commands = Column(JSON, nullable=False)
    risk_score = Column(Integer, default=5)
    resolution_time_ms = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    embedding = Column(JSON, nullable=True)


class DecisionExplanationORM(Base):
    """ORM model for decision explanations"""
    __tablename__ = "decision_explanations"

    decision_id = Column(String, primary_key=True)
    failure_id = Column(String, nullable=False)
    decision_type = Column(String, nullable=False)
    chosen_option = Column(Text, nullable=False)
    chosen_reasoning = Column(Text, nullable=False)
    confidence_score = Column(Integer, nullable=False)
    alternatives_considered = Column(JSON, nullable=False)
    context_used = Column(JSON, nullable=False)
    model_used = Column(String, nullable=False)
    prompt_summary = Column(Text, nullable=False)
    response_time_ms = Column(Integer, default=0)
    timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class RepositoryProfileORM(Base):
    """ORM model for repository personality profiles"""
    __tablename__ = "repository_profiles"

    repository = Column(String, primary_key=True)
    total_failures = Column(Integer, default=0)
    most_common_category = Column(String, nullable=False)
    most_common_day = Column(String, nullable=False)
    most_common_hour = Column(Integer, default=0)
    flaky_test_rate = Column(Integer, default=0)
    avg_resolution_time_minutes = Column(Integer, default=0)
    success_rate = Column(Integer, default=0)
    patterns = Column(JSON, nullable=False)
    last_updated = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class GitHubApprovalRequestORM(Base):
    """ORM model for GitHub approval requests"""
    __tablename__ = "github_approval_requests"

    request_id = Column(String, primary_key=True)
    failure_id = Column(String, nullable=False)
    repository = Column(String, nullable=False)
    environment_name = Column(String, nullable=False)
    deployment_id = Column(String, nullable=False)
    pr_number = Column(Integer, nullable=False)
    required_reviewers = Column(JSON, nullable=False)
    status = Column(String, default="pending")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    reviewed_at = Column(DateTime(timezone=True), nullable=True)


class HealthReportORM(Base):
    """ORM model for health reports"""
    __tablename__ = "health_reports"

    report_id = Column(String, primary_key=True)
    week_start = Column(DateTime(timezone=True), nullable=False)
    week_end = Column(DateTime(timezone=True), nullable=False)
    total_failures = Column(Integer, default=0)
    total_remediations = Column(Integer, default=0)
    success_rate = Column(Integer, default=0)
    avg_fix_time_minutes = Column(Integer, default=0)
    top_recurring_failures = Column(JSON, nullable=False)
    riskiest_repositories = Column(JSON, nullable=False)
    ai_confidence_trend = Column(String, nullable=False)
    circuit_breakers_triggered = Column(Integer, default=0)
    patterns_learned = Column(Integer, default=0)
    generated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class Database:
    """Database connection and session management"""

    def __init__(self, db_url: str = "sqlite:///:memory:"):
        """Initialize database connection"""
        self.engine = create_engine(
            db_url,
            connect_args={"check_same_thread": False} if "sqlite" in db_url else {},
            poolclass=StaticPool if "sqlite" in db_url else None
        )
        self.SessionLocal = sessionmaker(bind=self.engine)
        Base.metadata.create_all(self.engine)
        logger.info(f"Database initialized: {db_url}")

    def get_session(self) -> Session:
        """Get a database session"""
        return self.SessionLocal()

    def store_failure(self, failure: FailureRecord) -> None:
        """Store a failure record"""
        session = self.get_session()
        try:
            orm_obj = FailureRecordORM(
                failure_id=failure.failure_id,
                repository=failure.repository,
                workflow_run_id=failure.workflow_run_id,
                branch=failure.branch,
                commit_sha=failure.commit_sha,
                failure_reason=failure.failure_reason,
                logs=failure.logs,
                status=failure.status,
                created_at=failure.created_at,
                updated_at=failure.updated_at
            )
            session.merge(orm_obj)
            session.commit()
            logger.debug(f"Stored failure: {failure.failure_id}")
        finally:
            session.close()

    def get_failure(self, failure_id: str) -> Optional[FailureRecord]:
        """Retrieve a failure record"""
        session = self.get_session()
        try:
            orm_obj = session.query(FailureRecordORM).filter_by(failure_id=failure_id).first()
            if orm_obj:
                return FailureRecord(
                    failure_id=orm_obj.failure_id,
                    repository=orm_obj.repository,
                    workflow_run_id=orm_obj.workflow_run_id,
                    branch=orm_obj.branch,
                    commit_sha=orm_obj.commit_sha,
                    failure_reason=orm_obj.failure_reason,
                    logs=orm_obj.logs,
                    status=orm_obj.status,
                    created_at=orm_obj.created_at,
                    updated_at=orm_obj.updated_at
                )
            return None
        finally:
            session.close()

    def failure_exists(self, workflow_run_id: str) -> bool:
        """Check if a failure has been processed"""
        session = self.get_session()
        try:
            return session.query(FailureRecordORM).filter_by(workflow_run_id=workflow_run_id).first() is not None
        finally:
            session.close()

    def store_analysis(self, analysis: AnalysisResult) -> None:
        """Store an analysis result"""
        session = self.get_session()
        try:
            orm_obj = AnalysisResultORM(
                failure_id=analysis.failure_id,
                error_type=analysis.error_type,
                category=analysis.category,
                risk_score=analysis.risk_score,
                confidence=analysis.confidence,
                proposed_fix=analysis.proposed_fix,
                effort_estimate=analysis.effort_estimate,
                affected_components=analysis.affected_components,
                reasoning=analysis.reasoning,
                files_to_modify=analysis.files_to_modify,
                fix_commands=analysis.fix_commands,
                created_at=analysis.created_at
            )
            session.merge(orm_obj)
            session.commit()
            logger.debug(f"Stored analysis for failure: {analysis.failure_id}")
        finally:
            session.close()

    def get_analysis(self, failure_id: str) -> Optional[AnalysisResult]:
        """Retrieve an analysis result"""
        session = self.get_session()
        try:
            orm_obj = session.query(AnalysisResultORM).filter_by(failure_id=failure_id).first()
            if orm_obj:
                return AnalysisResult(
                    failure_id=orm_obj.failure_id,
                    error_type=orm_obj.error_type,
                    category=orm_obj.category,
                    risk_score=orm_obj.risk_score,
                    confidence=orm_obj.confidence,
                    proposed_fix=orm_obj.proposed_fix,
                    effort_estimate=orm_obj.effort_estimate,
                    affected_components=orm_obj.affected_components,
                    reasoning=orm_obj.reasoning,
                    files_to_modify=orm_obj.files_to_modify,
                    fix_commands=orm_obj.fix_commands,
                    created_at=orm_obj.created_at
                )
            return None
        finally:
            session.close()

    def store_approval_request(self, request: ApprovalRequest) -> None:
        """Store an approval request"""
        session = self.get_session()
        try:
            orm_obj = ApprovalRequestORM(
                request_id=request.request_id,
                failure_id=request.failure_id,
                analysis_id=request.analysis_id,
                status=request.status,
                requested_at=request.requested_at,
                expires_at=request.expires_at,
                approved_by=request.approved_by,
                approved_at=request.approved_at,
                slack_message_ts=request.slack_message_ts
            )
            session.merge(orm_obj)
            session.commit()
            logger.debug(f"Stored approval request: {request.request_id}")
        finally:
            session.close()

    def get_approval_request(self, request_id: str) -> Optional[ApprovalRequest]:
        """Retrieve an approval request"""
        session = self.get_session()
        try:
            orm_obj = session.query(ApprovalRequestORM).filter_by(request_id=request_id).first()
            if orm_obj:
                return ApprovalRequest(
                    request_id=orm_obj.request_id,
                    failure_id=orm_obj.failure_id,
                    analysis_id=orm_obj.analysis_id,
                    status=orm_obj.status,
                    requested_at=orm_obj.requested_at,
                    expires_at=orm_obj.expires_at,
                    approved_by=orm_obj.approved_by,
                    approved_at=orm_obj.approved_at,
                    slack_message_ts=orm_obj.slack_message_ts
                )
            return None
        finally:
            session.close()

    def store_audit_log(self, log_entry: AuditLogEntry) -> None:
        """Store an audit log entry"""
        session = self.get_session()
        try:
            orm_obj = AuditLogEntryORM(
                log_id=log_entry.log_id,
                timestamp=log_entry.timestamp,
                actor=log_entry.actor,
                action_type=log_entry.action_type,
                failure_id=log_entry.failure_id,
                request_id=log_entry.request_id,
                details=log_entry.details,
                outcome=log_entry.outcome,
                error_message=log_entry.error_message
            )
            session.add(orm_obj)
            session.commit()
            logger.debug(f"Stored audit log: {log_entry.log_id}")
        finally:
            session.close()

    def query_audit_logs(self, filters: Optional[Dict[str, Any]] = None) -> List[AuditLogEntry]:
        """Query audit logs with filters"""
        session = self.get_session()
        try:
            query = session.query(AuditLogEntryORM)
            
            if filters:
                if "start_date" in filters:
                    query = query.filter(AuditLogEntryORM.timestamp >= filters["start_date"])
                if "end_date" in filters:
                    query = query.filter(AuditLogEntryORM.timestamp <= filters["end_date"])
                if "repository" in filters:
                    query = query.filter(AuditLogEntryORM.details["repository"].astext == filters["repository"])
                if "action_type" in filters:
                    query = query.filter(AuditLogEntryORM.action_type == filters["action_type"])
            
            results = []
            for orm_obj in query.all():
                results.append(AuditLogEntry(
                    log_id=orm_obj.log_id,
                    timestamp=orm_obj.timestamp,
                    actor=orm_obj.actor,
                    action_type=orm_obj.action_type,
                    failure_id=orm_obj.failure_id,
                    request_id=orm_obj.request_id,
                    details=orm_obj.details,
                    outcome=orm_obj.outcome,
                    error_message=orm_obj.error_message
                ))
            return results
        finally:
            session.close()

    def store_metrics(self, metrics: MetricsRecord) -> None:
        """Store a metrics record"""
        session = self.get_session()
        try:
            orm_obj = MetricsRecordORM(
                metric_id=metrics.metric_id,
                failure_id=metrics.failure_id,
                detection_latency_ms=metrics.detection_latency_ms,
                analysis_latency_ms=metrics.analysis_latency_ms,
                remediation_latency_ms=metrics.remediation_latency_ms,
                total_latency_ms=metrics.total_latency_ms,
                remediation_success=metrics.remediation_success,
                category=metrics.category,
                repository=metrics.repository,
                risk_score=metrics.risk_score,
                recorded_at=metrics.recorded_at
            )
            session.add(orm_obj)
            session.commit()
            logger.debug(f"Stored metrics: {metrics.metric_id}")
        finally:
            session.close()

    def get_metrics(self, filters: Optional[Dict[str, Any]] = None) -> List[MetricsRecord]:
        """Retrieve metrics with optional filters"""
        session = self.get_session()
        try:
            query = session.query(MetricsRecordORM)
            
            if filters:
                if "repository" in filters:
                    query = query.filter(MetricsRecordORM.repository == filters["repository"])
                if "category" in filters:
                    query = query.filter(MetricsRecordORM.category == filters["category"])
            
            results = []
            for orm_obj in query.all():
                results.append(MetricsRecord(
                    metric_id=orm_obj.metric_id,
                    failure_id=orm_obj.failure_id,
                    detection_latency_ms=orm_obj.detection_latency_ms,
                    analysis_latency_ms=orm_obj.analysis_latency_ms,
                    remediation_latency_ms=orm_obj.remediation_latency_ms,
                    total_latency_ms=orm_obj.total_latency_ms,
                    remediation_success=orm_obj.remediation_success,
                    category=orm_obj.category,
                    repository=orm_obj.repository,
                    risk_score=orm_obj.risk_score,
                    recorded_at=orm_obj.recorded_at
                ))
            return results
        finally:
            session.close()

    def archive_old_data(self, retention_days: int = 90) -> int:
        """Archive or delete data older than retention period"""
        session = self.get_session()
        try:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=retention_days)
            
            # Delete old metrics
            deleted_count = session.query(MetricsRecordORM).filter(
                MetricsRecordORM.recorded_at < cutoff_date
            ).delete()
            
            session.commit()
            logger.info(f"Archived {deleted_count} old records")
            return deleted_count
        finally:
            session.close()

    def store_feedback(self, feedback: Feedback) -> None:
        """Store classification feedback"""
        session = self.get_session()
        try:
            orm_obj = FeedbackORM(
                failure_id=feedback.failure_id,
                predicted_category=feedback.predicted_category,
                actual_category=feedback.actual_category,
                timestamp=feedback.timestamp
            )
            session.add(orm_obj)
            session.commit()
            logger.debug(f"Stored feedback for failure {feedback.failure_id}")
        finally:
            session.close()

    def get_feedback(self) -> List[Feedback]:
        """Retrieve all feedback"""
        session = self.get_session()
        try:
            query = session.query(FeedbackORM)
            results = []
            for orm_obj in query.all():
                results.append(Feedback(
                    failure_id=orm_obj.failure_id,
                    predicted_category=orm_obj.predicted_category,
                    actual_category=orm_obj.actual_category,
                    timestamp=orm_obj.timestamp
                ))
            return results
        finally:
            session.close()

    def store_snapshot(self, snapshot) -> None:
        """Store a snapshot"""
        session = self.get_session()
        try:
            orm_obj = SnapshotORM(
                id=snapshot.id,
                repository_id=snapshot.repository_id,
                remediation_id=snapshot.remediation_id,
                commit_sha=snapshot.commit_sha,
                branch_name=snapshot.branch_name,
                modified_files=[{"path": f.path, "content_hash": f.content_hash, "content": f.content} 
                               for f in snapshot.modified_files],
                created_at=snapshot.created_at,
                expires_at=snapshot.expires_at,
                status=snapshot.status.value if hasattr(snapshot.status, 'value') else snapshot.status,
                metadata=snapshot.metadata
            )
            session.merge(orm_obj)
            session.commit()
            logger.debug(f"Stored snapshot: {snapshot.id}")
        finally:
            session.close()

    def get_snapshot(self, snapshot_id: str):
        """Retrieve a snapshot"""
        session = self.get_session()
        try:
            orm_obj = session.query(SnapshotORM).filter_by(id=snapshot_id).first()
            if orm_obj:
                from src.snapshot_manager import Snapshot, FileSnapshot, SnapshotStatus
                return Snapshot(
                    id=orm_obj.id,
                    repository_id=orm_obj.repository_id,
                    remediation_id=orm_obj.remediation_id,
                    commit_sha=orm_obj.commit_sha,
                    branch_name=orm_obj.branch_name,
                    modified_files=[FileSnapshot(**f) for f in orm_obj.modified_files],
                    created_at=orm_obj.created_at,
                    expires_at=orm_obj.expires_at,
                    status=SnapshotStatus(orm_obj.status),
                    metadata=orm_obj.metadata
                )
            return None
        finally:
            session.close()

    def get_pending_approvals(self) -> List[ApprovalRequest]:
        """Get all pending approval requests"""
        from src.models import ApprovalRequest, ApprovalStatus
        session = self.get_session()
        try:
            query = session.query(ApprovalRequestORM).filter(
                ApprovalRequestORM.status == ApprovalStatus.PENDING.value
            )
            results = []
            for orm_obj in query.all():
                results.append(ApprovalRequest(
                    request_id=orm_obj.request_id,
                    failure_id=orm_obj.failure_id,
                    analysis_id=orm_obj.analysis_id,
                    status=ApprovalStatus(orm_obj.status),
                    requested_at=orm_obj.requested_at,
                    expires_at=orm_obj.expires_at,
                    approved_by=orm_obj.approved_by,
                    approved_at=orm_obj.approved_at,
                    slack_message_ts=orm_obj.slack_message_ts
                ))
            return results
        finally:
            session.close()

    def get_analysis(self, failure_id: str):
        """Get analysis result for a failure"""
        from src.models import AnalysisResult, FailureCategory
        session = self.get_session()
        try:
            orm_obj = session.query(AnalysisResultORM).filter_by(failure_id=failure_id).first()
            if not orm_obj:
                return None
            
            return AnalysisResult(
                failure_id=orm_obj.failure_id,
                error_type=orm_obj.error_type,
                category=FailureCategory(orm_obj.category),
                risk_score=orm_obj.risk_score,
                confidence=orm_obj.confidence,
                proposed_fix=orm_obj.proposed_fix,
                effort_estimate=orm_obj.effort_estimate,
                affected_components=orm_obj.affected_components,
                reasoning=orm_obj.reasoning,
                files_to_modify=orm_obj.files_to_modify,
                fix_commands=orm_obj.fix_commands,
                created_at=orm_obj.created_at
            )
        finally:
            session.close()

    def store_health_check(self, check_data: Dict[str, Any]) -> None:
        """Store health check metadata"""
        session = self.get_session()
        try:
            orm_obj = HealthCheckORM(**check_data)
            session.add(orm_obj)
            session.commit()
            logger.debug(f"Stored health check for remediation: {check_data.get('remediation_id')}")
        finally:
            session.close()

    def get_health_check(self, remediation_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve health check metadata"""
        session = self.get_session()
        try:
            orm_obj = session.query(HealthCheckORM).filter_by(
                remediation_id=remediation_id
            ).first()
            if orm_obj:
                return {
                    "remediation_id": orm_obj.remediation_id,
                    "snapshot_id": orm_obj.snapshot_id,
                    "repository": orm_obj.repository,
                    "workflow_run_id": orm_obj.workflow_run_id,
                    "scheduled_at": orm_obj.scheduled_at,
                    "delay_minutes": orm_obj.delay_minutes,
                    "status": orm_obj.status,
                    "passed": orm_obj.passed,
                    "triggered_rollback": orm_obj.triggered_rollback
                }
            return None
        finally:
            session.close()

    def store_health_check_result(self, result) -> None:
        """Store health check result"""
        session = self.get_session()
        try:
            orm_obj = session.query(HealthCheckORM).filter_by(
                remediation_id=result.remediation_id
            ).first()
            
            if orm_obj:
                orm_obj.executed_at = result.timestamp
                orm_obj.passed = result.passed
                orm_obj.checks = [
                    {"name": c.name, "passed": c.passed, "message": c.message, "details": c.details}
                    for c in result.checks
                ]
                orm_obj.status = "completed"
                session.commit()
                logger.debug(f"Updated health check result for remediation: {result.remediation_id}")
        finally:
            session.close()

    def update_health_check_rollback(self, remediation_id: str, triggered: bool = True) -> None:
        """Update rollback status of a health check"""
        session = self.get_session()
        try:
            orm_obj = session.query(HealthCheckORM).filter_by(
                remediation_id=remediation_id
            ).first()
            if orm_obj:
                orm_obj.triggered_rollback = triggered
                session.commit()
                logger.debug(f"Marked rollback as {triggered} for remediation {remediation_id}")
        finally:
            session.close()

    def store_circuit_breaker_state(self, state) -> None:
        """Store circuit breaker state"""
        session = self.get_session()
        try:
            orm_obj = CircuitBreakerORM(
                failure_signature=state.failure_signature,
                repository_id=state.repository_id,
                workflow_name=state.workflow_name,
                error_pattern=state.error_pattern,
                branch=state.branch,
                state=state.state.value if hasattr(state.state, 'value') else state.state,
                failure_count=state.failure_count,
                last_failure_at=state.last_failure_at,
                opened_at=state.opened_at,
                auto_reset_at=state.auto_reset_at,
                manually_reset_at=state.manually_reset_at,
                manually_reset_by=state.manually_reset_by,
                history=[t.to_dict() for t in state.history]
            )
            session.merge(orm_obj)
            session.commit()
            logger.debug(f"Stored circuit breaker state: {state.failure_signature}")
        finally:
            session.close()

    def get_circuit_breaker_state(self, failure_signature: str):
        """Retrieve circuit breaker state"""
        session = self.get_session()
        try:
            orm_obj = session.query(CircuitBreakerORM).filter_by(
                failure_signature=failure_signature
            ).first()
            
            if orm_obj:
                from src.circuit_breaker import CircuitBreakerState, CircuitState, StateTransition
                return CircuitBreakerState(
                    failure_signature=orm_obj.failure_signature,
                    repository_id=orm_obj.repository_id,
                    workflow_name=orm_obj.workflow_name,
                    error_pattern=orm_obj.error_pattern,
                    branch=orm_obj.branch if hasattr(orm_obj, 'branch') else "main",
                    state=CircuitState(orm_obj.state),
                    failure_count=orm_obj.failure_count,
                    last_failure_at=orm_obj.last_failure_at,
                    opened_at=orm_obj.opened_at,
                    auto_reset_at=orm_obj.auto_reset_at,
                    manually_reset_at=orm_obj.manually_reset_at,
                    manually_reset_by=orm_obj.manually_reset_by,
                    history=[StateTransition(**t) for t in orm_obj.history] if orm_obj.history else []
                )
            return None
        finally:
            session.close()

    def store_failure_pattern(self, pattern) -> None:
        """Store failure pattern"""
        session = self.get_session()
        try:
            orm_obj = FailurePatternORM(
                pattern_id=pattern.pattern_id,
                repository=pattern.repository,
                branch=pattern.branch,
                failure_reason=pattern.failure_reason,
                failure_category=pattern.failure_category,
                error_signature=pattern.error_signature,
                proposed_fix=pattern.proposed_fix,
                fix_successful=pattern.fix_successful,
                files_modified=pattern.files_modified,
                fix_commands=pattern.fix_commands,
                risk_score=pattern.risk_score,
                resolution_time_ms=pattern.resolution_time_ms,
                created_at=pattern.created_at,
                embedding=pattern.embedding
            )
            session.merge(orm_obj)
            session.commit()
            logger.debug(f"Stored failure pattern: {pattern.pattern_id}")
        finally:
            session.close()

    def get_all_failure_patterns(self) -> List:
        """Retrieve all failure patterns"""
        session = self.get_session()
        try:
            from src.failure_pattern_memory import FailurePattern
            
            query = session.query(FailurePatternORM)
            results = []
            
            for orm_obj in query.all():
                pattern = FailurePattern(
                    pattern_id=orm_obj.pattern_id,
                    repository=orm_obj.repository,
                    branch=orm_obj.branch,
                    failure_reason=orm_obj.failure_reason,
                    failure_category=orm_obj.failure_category,
                    error_signature=orm_obj.error_signature,
                    proposed_fix=orm_obj.proposed_fix,
                    fix_successful=orm_obj.fix_successful,
                    files_modified=orm_obj.files_modified,
                    fix_commands=orm_obj.fix_commands,
                    risk_score=orm_obj.risk_score,
                    resolution_time_ms=orm_obj.resolution_time_ms,
                    created_at=orm_obj.created_at,
                    embedding=orm_obj.embedding
                )
                results.append(pattern)
            
            return results
        finally:
            session.close()

    def store_decision_explanation(self, decision) -> None:
        """Store decision explanation"""
        session = self.get_session()
        try:
            orm_obj = DecisionExplanationORM(
                decision_id=decision.decision_id,
                failure_id=decision.failure_id,
                decision_type=decision.decision_type.value if hasattr(decision.decision_type, 'value') else decision.decision_type,
                chosen_option=decision.chosen_option,
                chosen_reasoning=decision.chosen_reasoning,
                confidence_score=int(decision.confidence_score * 100),
                alternatives_considered=[
                    {
                        "option": alt.option,
                        "reasoning": alt.reasoning,
                        "score": alt.score,
                        "rejected_reason": alt.rejected_reason
                    }
                    for alt in decision.alternatives_considered
                ],
                context_used=decision.context_used,
                model_used=decision.model_used,
                prompt_summary=decision.prompt_summary,
                response_time_ms=decision.response_time_ms,
                timestamp=decision.timestamp
            )
            session.merge(orm_obj)
            session.commit()
            logger.debug(f"Stored decision explanation: {decision.decision_id}")
        finally:
            session.close()

    def get_decisions_for_failure(self, failure_id: str) -> List:
        """Get decisions for failure"""
        session = self.get_session()
        try:
            from src.explainability import DecisionExplanation, DecisionType, Alternative
            
            query = session.query(DecisionExplanationORM).filter_by(failure_id=failure_id)
            results = []
            
            for orm_obj in query.all():
                alternatives = [
                    Alternative(
                        option=alt["option"],
                        reasoning=alt["reasoning"],
                        score=alt["score"],
                        rejected_reason=alt["rejected_reason"]
                    )
                    for alt in orm_obj.alternatives_considered
                ]
                
                decision = DecisionExplanation(
                    decision_id=orm_obj.decision_id,
                    failure_id=orm_obj.failure_id,
                    decision_type=DecisionType(orm_obj.decision_type),
                    chosen_option=orm_obj.chosen_option,
                    chosen_reasoning=orm_obj.chosen_reasoning,
                    confidence_score=orm_obj.confidence_score / 100.0,
                    alternatives_considered=alternatives,
                    context_used=orm_obj.context_used,
                    model_used=orm_obj.model_used,
                    prompt_summary=orm_obj.prompt_summary,
                    response_time_ms=orm_obj.response_time_ms,
                    timestamp=orm_obj.timestamp
                )
                results.append(decision)
            
            return results
        finally:
            session.close()

    def store_repository_profile(self, profile) -> None:
        """Store repository profile"""
        session = self.get_session()
        try:
            orm_obj = RepositoryProfileORM(
                repository=profile.repository,
                total_failures=profile.total_failures,
                most_common_category=profile.most_common_category,
                most_common_day=profile.most_common_day,
                most_common_hour=profile.most_common_hour,
                flaky_test_rate=int(profile.flaky_test_rate * 100),
                avg_resolution_time_minutes=int(profile.avg_resolution_time_minutes),
                success_rate=int(profile.success_rate * 100),
                patterns=[
                    {
                        "pattern_type": p.pattern_type,
                        "frequency": p.frequency,
                        "description": p.description,
                        "confidence_adjustment": p.confidence_adjustment,
                        "recommended_action": p.recommended_action
                    }
                    for p in profile.patterns
                ],
                last_updated=profile.last_updated
            )
            session.merge(orm_obj)
            session.commit()
            logger.debug(f"Stored repository profile: {profile.repository}")
        finally:
            session.close()

    def store_github_approval_request(self, request) -> None:
        """Store GitHub approval request"""
        session = self.get_session()
        try:
            orm_obj = GitHubApprovalRequestORM(
                request_id=request.request_id,
                failure_id=request.failure_id,
                repository=request.repository,
                environment_name=request.environment_name,
                deployment_id=request.deployment_id,
                pr_number=request.pr_number,
                required_reviewers=request.required_reviewers,
                status=request.status,
                created_at=request.created_at,
                reviewed_by=request.reviewed_by,
                reviewed_at=request.reviewed_at
            )
            session.merge(orm_obj)
            session.commit()
            logger.debug(f"Stored GitHub approval request: {request.request_id}")
        finally:
            session.close()

    def get_github_approval_request(self, request_id: str):
        """Get GitHub approval request"""
        session = self.get_session()
        try:
            from src.github_approval import GitHubApprovalRequest
            
            orm_obj = session.query(GitHubApprovalRequestORM).filter_by(request_id=request_id).first()
            if orm_obj:
                return GitHubApprovalRequest(
                    request_id=orm_obj.request_id,
                    failure_id=orm_obj.failure_id,
                    repository=orm_obj.repository,
                    environment_name=orm_obj.environment_name,
                    deployment_id=orm_obj.deployment_id,
                    pr_number=orm_obj.pr_number,
                    required_reviewers=orm_obj.required_reviewers,
                    status=orm_obj.status,
                    created_at=orm_obj.created_at,
                    reviewed_by=orm_obj.reviewed_by,
                    reviewed_at=orm_obj.reviewed_at
                )
            return None
        finally:
            session.close()

    def store_health_report(self, report) -> None:
        """Store health report"""
        session = self.get_session()
        try:
            orm_obj = HealthReportORM(
                report_id=report.report_id,
                week_start=report.week_start,
                week_end=report.week_end,
                total_failures=report.total_failures,
                total_remediations=report.total_remediations,
                success_rate=int(report.success_rate),
                avg_fix_time_minutes=int(report.avg_fix_time_minutes),
                top_recurring_failures=report.top_recurring_failures,
                riskiest_repositories=report.riskiest_repositories,
                ai_confidence_trend=report.ai_confidence_trend,
                circuit_breakers_triggered=report.circuit_breakers_triggered,
                patterns_learned=report.patterns_learned,
                generated_at=report.generated_at
            )
            session.add(orm_obj)
            session.commit()
            logger.debug(f"Stored health report: {report.report_id}")
        finally:
            session.close()
