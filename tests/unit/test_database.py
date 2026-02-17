"""Unit tests for database layer"""
import pytest
from datetime import datetime
from src.database import Database
from src.models import (
    FailureRecord, AnalysisResult, ApprovalRequest, AuditLogEntry, MetricsRecord,
    FailureStatus, FailureCategory, ApprovalStatus, ActionType
)


class TestFailureRecordPersistence:
    """Test failure record storage and retrieval"""

    def test_store_and_retrieve_failure(self, db, sample_failure):
        """Test storing and retrieving a failure record"""
        db.store_failure(sample_failure)
        retrieved = db.get_failure(sample_failure.failure_id)
        
        assert retrieved is not None
        assert retrieved.failure_id == sample_failure.failure_id
        assert retrieved.repository == sample_failure.repository
        assert retrieved.workflow_run_id == sample_failure.workflow_run_id

    def test_failure_exists_check(self, db, sample_failure):
        """Test checking if a failure has been processed"""
        assert not db.failure_exists(sample_failure.workflow_run_id)
        db.store_failure(sample_failure)
        assert db.failure_exists(sample_failure.workflow_run_id)

    def test_update_failure_status(self, db, sample_failure):
        """Test updating failure status"""
        db.store_failure(sample_failure)
        
        sample_failure.status = FailureStatus.ANALYZED
        db.store_failure(sample_failure)
        
        retrieved = db.get_failure(sample_failure.failure_id)
        assert retrieved.status == FailureStatus.ANALYZED


class TestAnalysisResultPersistence:
    """Test analysis result storage and retrieval"""

    def test_store_and_retrieve_analysis(self, db, sample_analysis):
        """Test storing and retrieving an analysis result"""
        db.store_analysis(sample_analysis)
        retrieved = db.get_analysis(sample_analysis.failure_id)
        
        assert retrieved is not None
        assert retrieved.failure_id == sample_analysis.failure_id
        assert retrieved.category == sample_analysis.category
        assert retrieved.risk_score == sample_analysis.risk_score
        assert retrieved.confidence == sample_analysis.confidence

    def test_analysis_components_preserved(self, db, sample_analysis):
        """Test that affected components are preserved"""
        db.store_analysis(sample_analysis)
        retrieved = db.get_analysis(sample_analysis.failure_id)
        
        assert retrieved.affected_components == sample_analysis.affected_components


class TestApprovalRequestPersistence:
    """Test approval request storage and retrieval"""

    def test_store_and_retrieve_approval_request(self, db):
        """Test storing and retrieving an approval request"""
        request = ApprovalRequest(
            request_id="req-1",
            failure_id="fail-1",
            analysis_id="analysis-1",
            status=ApprovalStatus.PENDING
        )
        
        db.store_approval_request(request)
        retrieved = db.get_approval_request(request.request_id)
        
        assert retrieved is not None
        assert retrieved.request_id == request.request_id
        assert retrieved.status == ApprovalStatus.PENDING

    def test_approval_request_with_approver(self, db):
        """Test storing approval request with approver info"""
        request = ApprovalRequest(
            request_id="req-2",
            failure_id="fail-2",
            analysis_id="analysis-2",
            status=ApprovalStatus.APPROVED,
            approved_by="user@example.com"
        )
        
        db.store_approval_request(request)
        retrieved = db.get_approval_request(request.request_id)
        
        assert retrieved.approved_by == "user@example.com"
        assert retrieved.status == ApprovalStatus.APPROVED


class TestAuditLogPersistence:
    """Test audit log storage and querying"""

    def test_store_and_query_audit_log(self, db):
        """Test storing and querying audit logs"""
        log_entry = AuditLogEntry(
            log_id="log-1",
            timestamp=datetime.utcnow(),
            actor="monitor",
            action_type=ActionType.DETECTION,
            failure_id="fail-1",
            request_id=None,
            details={"repository": "test/repo"},
            outcome="success"
        )
        
        db.store_audit_log(log_entry)
        logs = db.query_audit_logs()
        
        assert len(logs) > 0
        assert logs[0].log_id == log_entry.log_id

    def test_audit_log_filtering_by_action_type(self, db):
        """Test filtering audit logs by action type"""
        log1 = AuditLogEntry(
            log_id="log-1",
            timestamp=datetime.utcnow(),
            actor="monitor",
            action_type=ActionType.DETECTION,
            failure_id="fail-1",
            request_id=None,
            details={},
            outcome="success"
        )
        log2 = AuditLogEntry(
            log_id="log-2",
            timestamp=datetime.utcnow(),
            actor="analyzer",
            action_type=ActionType.ANALYSIS,
            failure_id="fail-1",
            request_id=None,
            details={},
            outcome="success"
        )
        
        db.store_audit_log(log1)
        db.store_audit_log(log2)
        
        detection_logs = db.query_audit_logs({"action_type": ActionType.DETECTION})
        assert len(detection_logs) == 1
        assert detection_logs[0].action_type == ActionType.DETECTION


class TestMetricsRecordPersistence:
    """Test metrics record storage and retrieval"""

    def test_store_and_retrieve_metrics(self, db):
        """Test storing and retrieving metrics"""
        metrics = MetricsRecord(
            metric_id="metric-1",
            failure_id="fail-1",
            detection_latency_ms=100,
            analysis_latency_ms=500,
            remediation_latency_ms=1000,
            total_latency_ms=1600,
            remediation_success=True,
            category="timeout",
            repository="test/repo",
            risk_score=3
        )
        
        db.store_metrics(metrics)
        retrieved = db.get_metrics()
        
        assert len(retrieved) > 0
        assert retrieved[0].metric_id == metrics.metric_id
        assert retrieved[0].remediation_success is True

    def test_metrics_filtering_by_repository(self, db):
        """Test filtering metrics by repository"""
        metrics1 = MetricsRecord(
            metric_id="metric-1",
            failure_id="fail-1",
            detection_latency_ms=100,
            analysis_latency_ms=500,
            remediation_latency_ms=1000,
            total_latency_ms=1600,
            remediation_success=True,
            category="timeout",
            repository="repo1",
            risk_score=3
        )
        metrics2 = MetricsRecord(
            metric_id="metric-2",
            failure_id="fail-2",
            detection_latency_ms=150,
            analysis_latency_ms=600,
            remediation_latency_ms=1200,
            total_latency_ms=1950,
            remediation_success=False,
            category="dependency",
            repository="repo2",
            risk_score=5
        )
        
        db.store_metrics(metrics1)
        db.store_metrics(metrics2)
        
        repo1_metrics = db.get_metrics({"repository": "repo1"})
        assert len(repo1_metrics) == 1
        assert repo1_metrics[0].repository == "repo1"
