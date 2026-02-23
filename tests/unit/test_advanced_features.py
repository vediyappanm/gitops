"""Unit tests for Advanced Features: Dry-Run, Circuit Breaker, Rollback, blast radius, and memory"""
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta, timezone
import numpy as np

from src.dry_run_mode import DryRunMode
from src.circuit_breaker import CircuitBreaker, FailureSignature, CircuitState
from src.blast_radius import BlastRadiusEstimator
from src.failure_pattern_memory import FailurePatternMemory, FailurePattern
from src.metric_alerting import MetricAlertingEngine
from src.health_checker import HealthChecker
from src.models import FailureCategory

class TestDryRunMode:
    def test_dry_run_interception(self):
        dry_run = DryRunMode(enabled=True)
        
        # Test PR interception
        pr_url = dry_run.intercept_pr_creation(
            repo="org/repo", branch="fix/123", title="Fix", body="Proposed fix"
        )
        assert "[DRY-RUN]" in pr_url
        assert len(dry_run.actions) == 1
        assert dry_run.actions[0].action_type == "PR_CREATION"
        
        # Test File modification interception
        dry_run.intercept_file_modification("repo", ["file.py"], "update")
        assert len(dry_run.actions) == 2
        assert dry_run.actions[1].action_type == "FILE_MODIFICATION"
        
        # Test report generation
        report = dry_run.generate_report()
        assert report.prs_that_would_be_created == 1
        assert "file.py" in report.files_modified

class TestCircuitBreaker:
    def test_circuit_state_transitions(self):
        mock_db = MagicMock()
        mock_db.get_circuit_breaker_state.return_value = None
        cb = CircuitBreaker(mock_db, failure_threshold=2)
        
        sig = FailureSignature("repo", "workflow", "error", "main")
        
        # 1. First failure
        cb.record_failure(sig)
        state = cb.get_state(sig)
        assert state.state == CircuitState.CLOSED
        assert state.failure_count == 1
        
        # 2. Second failure triggers OPEN
        cb.record_failure(sig)
        state = cb.get_state(sig)
        assert state.state == CircuitState.OPEN
        assert cb.is_remediation_allowed(sig) is False
        
        # 3. Advance time to trigger auto-reset (simulation)
        state.auto_reset_at = datetime.now(timezone.utc) - timedelta(hours=1)
        assert cb.is_remediation_allowed(sig) is True # Transitions to HALF_OPEN
        assert state.state == CircuitState.HALF_OPEN
        
        # 4. Success closes circuit
        cb.record_success(sig)
        assert state.state == CircuitState.CLOSED
        assert state.failure_count == 0

class TestBlastRadius:
    def test_critical_file_scoring(self):
        mock_gh = MagicMock()
        mock_db = MagicMock()
        estimator = BlastRadiusEstimator(mock_gh, mock_db)
        
        # Test critical infrastructure file
        result = estimator.estimate_blast_radius(
            repository="repo",
            branch="main",
            files_to_modify=["docker-compose.yml"],
            failure_category="infrastructure"
        )
        
        assert result.blast_radius_score >= 7
        assert result.impact_level.value in ["high", "critical"]

class TestFailurePatternMemory:
    def test_similarity_search(self):
        mock_db = MagicMock()
        memory = FailurePatternMemory(mock_db, use_local_embeddings=True)
        
        # Manually create a pattern with a known embedding
        test_embedding = memory._generate_embedding("Syntax error", "code")
        pattern = FailurePattern(
            pattern_id="1", repository="repo", branch="main",
            failure_reason="Syntax error in python", failure_category="code",
            error_signature="code_syntax_error", proposed_fix="Fix code",
            fix_successful=True, embedding=test_embedding
        )
        # Mock load_patterns to use our test pattern
        memory.pattern_cache = {"1": pattern}
        
        # Find similar - should match perfectly
        results = memory.find_similar_patterns("Syntax error", "code")
        assert len(results) > 0
        assert results[0].similarity_score >= 0.9

class TestMetricAlerting:
    def test_threshold_breach(self):
        mock_db = MagicMock()
        mock_notifier = MagicMock()
        mock_tracker = MagicMock()
        
        # Threshold 90%
        engine = MetricAlertingEngine(mock_db, mock_notifier, mock_tracker, success_rate_threshold=90.0)
        
        # Mock metrics: 7 successful out of 10 = 70% (below 90% threshold)
        from src.models import MetricsRecord
        from datetime import datetime, timedelta
        recent_time = datetime.now(timezone.utc)
        
        mock_metrics = []
        for i in range(10):
            metric = MagicMock(spec=MetricsRecord)
            metric.remediation_success = i < 7  # First 7 are successful
            metric.recorded_at = recent_time
            mock_metrics.append(metric)
        
        mock_db.get_metrics.return_value = mock_metrics
        
        # Run check
        alert = engine.check_success_rate("org/repo")
        
        # Verify alert was created
        assert alert is not None
        assert alert.current_value == 70.0

class TestRollbackEngine:
    @patch('src.agent.GitHubClient')
    @patch('prometheus_client.start_http_server')
    def test_health_check_failure_triggers_rollback(self, mock_prometheus, mock_gh_client):
        mock_db = MagicMock()
        mock_notifier = MagicMock()
        mock_snapshot = MagicMock()
        
        # Setup config mock
        mock_config = MagicMock()
        mock_config.config.github_token = "valid_token"
        mock_config.config.telegram_bot_token = "bot_token"
        
        from src.agent import CICDFailureMonitorAgent
        # Initialize agent
        agent = CICDFailureMonitorAgent(mock_config, mock_db)
        agent.notifier = mock_notifier
        agent.snapshot_manager = mock_snapshot
        
        # Setup health check metadata in DB
        mock_db.get_health_check.return_value = {
            "remediation_id": "rem-123",
            "snapshot_id": "snap-123",
            "repository": "org/repo",
            "status": "scheduled"
        }
        
        # Simulate health check failure callback
        agent._on_health_check_fail("rem-123")
        
        # Verify autonomous actions
        assert mock_snapshot.rollback.called
        assert mock_snapshot.rollback.call_args[0][0] == "snap-123"
        assert mock_notifier.send_rollback_alert.called
        assert mock_db.update_health_check_rollback.called

if __name__ == "__main__":
    pytest.main([__file__])
