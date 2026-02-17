"""Database layer for CI/CD Failure Monitor"""
import logging
from datetime import datetime, timedelta
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
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


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
    created_at = Column(DateTime, default=datetime.utcnow)


class ApprovalRequestORM(Base):
    """ORM model for approval requests"""
    __tablename__ = "approval_requests"

    request_id = Column(String, primary_key=True)
    failure_id = Column(String, nullable=False)
    analysis_id = Column(String, nullable=False)
    status = Column(SQLEnum(ApprovalStatus), default=ApprovalStatus.PENDING)
    requested_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)
    approved_by = Column(String, nullable=True)
    approved_at = Column(DateTime, nullable=True)
    slack_message_ts = Column(String, nullable=True)


class AuditLogEntryORM(Base):
    """ORM model for audit log entries"""
    __tablename__ = "audit_logs"

    log_id = Column(String, primary_key=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
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
    recorded_at = Column(DateTime, default=datetime.utcnow)


class FeedbackORM(Base):
    """ORM model for classification feedback"""
    __tablename__ = "feedback"

    id = Column(Integer, primary_key=True, autoincrement=True)
    failure_id = Column(String, nullable=False)
    predicted_category = Column(String, nullable=False)
    actual_category = Column(String, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)


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
            cutoff_date = datetime.utcnow() - timedelta(days=retention_days)
            
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
