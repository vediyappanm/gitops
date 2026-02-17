"""Pytest configuration and fixtures"""
import pytest
from src.database import Database
from src.models import FailureRecord, AnalysisResult, FailureStatus, FailureCategory


@pytest.fixture
def db():
    """Create an in-memory database for testing"""
    database = Database("sqlite:///:memory:")
    yield database


@pytest.fixture
def sample_failure():
    """Create a sample failure record"""
    return FailureRecord(
        failure_id="test-failure-1",
        repository="test/repo",
        workflow_run_id="run-123",
        branch="main",
        commit_sha="abc123def456",
        failure_reason="Timeout in test suite",
        logs="Test execution timed out after 30 minutes",
        status=FailureStatus.DETECTED
    )


@pytest.fixture
def sample_analysis():
    """Create a sample analysis result"""
    return AnalysisResult(
        failure_id="test-failure-1",
        category=FailureCategory.TIMEOUT,
        risk_score=3,
        confidence=85,
        proposed_fix="Increase test timeout from 30 to 60 minutes",
        effort_estimate="low",
        affected_components=["test-suite"],
        reasoning="The test suite is timing out due to increased test count"
    )
