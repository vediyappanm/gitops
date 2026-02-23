import pytest
import time
from src.models import FailureRecord, FailureStatus, FailureCategory

@pytest.mark.github_integration
class TestE2EFlow:
    def test_full_e2e_pipeline_dry_run(self, integration_agent, db, test_repo):
        """Tier 3: Full pipeline from detection to fixed (dry-run)"""
        # 1. Simulate finding a failure
        failure_id = "e2e-fail-123"
        failure = FailureRecord(
            failure_id=failure_id,
            repository=test_repo.full_name,
            workflow_run_id="workflow-1",
            branch="test-branch",
            commit_sha="abcd",
            failure_reason="dependency mismatch",
            logs="pip install error: package not found",
            status=FailureStatus.DETECTED
        )
        db.store_failure(failure)
        
        # 2. Process it
        integration_agent.process_failure(failure_id)
        
        # 3. Verify dry-run actions
        report = integration_agent.dry_run_mode.generate_report()
        assert len(integration_agent.dry_run_mode.actions) > 0
        
    def test_high_risk_goes_to_approval(self, integration_agent, db, test_repo, sample_failure, sample_analysis):
        """Tier 3: High risk failures go to approval, not auto-fix"""
        # Set high risk score
        sample_analysis.risk_score = 9 
        sample_analysis.failure_id = sample_failure.failure_id
        sample_failure.repository = test_repo.full_name
        sample_failure.branch = "feature/test-high-risk" # Must not be main
        sample_analysis.files_to_modify = ["README.md"]
        
        db.store_failure(sample_failure)
        
        # Mock analysis to return our high-risk result
        integration_agent.analyzer.analyze_failure = lambda f: sample_analysis
        
        # Process failure
        integration_agent.process_failure(sample_failure.failure_id)
        
        # Verify it's in ANALYZED status (awaiting approval)
        updated_failure = db.get_failure(sample_failure.failure_id)
        assert updated_failure.status == FailureStatus.ANALYZED

    def test_rollback_on_failed_remediation(self, integration_agent, db):
        """Tier 3: If health check fails, agent rolls back"""
        remediation_id = "rem-123"
        snapshot_id = "snap-123"
        
        # Setup mock health check in DB using correct method
        db.store_health_check({
            "remediation_id": remediation_id,
            "snapshot_id": snapshot_id,
            "repository": "org/repo",
            "workflow_run_id": "run-1",
            "status": "scheduled"
        })
        
        # Trigger failure callback
        integration_agent._on_health_check_fail(remediation_id)
        
        # Verify database update
        check = db.get_health_check(remediation_id)
        # Check if value is truthy (1 or True)
        assert check["triggered_rollback"]
