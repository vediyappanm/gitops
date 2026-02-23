import pytest
import time
from src.circuit_breaker import CircuitState, FailureSignature

@pytest.mark.github_integration
class TestSafetyResilience:
    def test_no_duplicate_prs(self, test_repo, integration_agent):
        """Tier 2: Agent doesn't create duplicate PRs if run twice"""
        branch_name = f"test-idempotency-{int(time.time())}"
        main_sha = test_repo.get_branch("main").commit.sha
        test_repo.create_git_ref(ref=f"refs/heads/{branch_name}", sha=main_sha)
        
        fix_branch = f"agent-fix/{branch_name}-999"
        test_repo.create_git_ref(ref=f"refs/heads/{fix_branch}", sha=main_sha)
        
        try:
            client = integration_agent.github_client
            # Create a diff between fix_branch and branch_name
            client.create_file(
                test_repo.full_name, 
                "REMEDIATION.md", 
                "This is a robot fix", 
                "Add remediation docs", 
                fix_branch
            )
            
            # First PR creation
            pr1_url = client.create_pull_request(
                test_repo.full_name, "Robot Fix 1", "Body", fix_branch, branch_name
            )
            assert pr1_url is not None
            
            # Second PR creation should ideally be handled gracefully by GitHub (it returns 422 if exists)
            # or the client should handle it. Our client currently just logs error and returns None.
            # We want to verify that the system handles this without crashing.
            pr2_url = client.create_pull_request(
                test_repo.full_name, "Robot Fix 1", "Body", fix_branch, branch_name
            )
            # If it already exists, GitHub returns 422. Our client returns None.
            assert pr2_url is None or pr2_url == pr1_url
            
        finally:
            pass # Cleanup handles it

    def test_circuit_breaker_opens_after_threshold(self, integration_agent, db):
        """Tier 2: After 3 consecutive failures, agent stops trying"""
        sig = FailureSignature(
            repository_id="org/repo",
            workflow_name="CI",
            error_pattern="Connection timeout",
            branch="test-branch"
        )
        
        # Record 3 failures
        for _ in range(3):
            integration_agent.circuit_breaker.record_failure(sig)
            
        state = integration_agent.circuit_breaker.get_state(sig)
        assert state.state == CircuitState.OPEN
        assert integration_agent.circuit_breaker.is_remediation_allowed(sig) is False

    def test_main_branch_protection(self, integration_agent, sample_failure, sample_analysis):
        """Tier 2: Agent NEVER touches main branch"""
        # Ensure the failure is for 'main'
        sample_failure.branch = "main"
        # Ensure it has files to modify so it doesn't fail on that check
        sample_analysis.files_to_modify = ["README.md"]
        
        # SafetyGate check
        is_safe, reason = integration_agent.safety_gate.validate_remediation(sample_failure, sample_analysis)
        
        # It should NOT be safe because main is protected
        assert is_safe is False
        assert "main" in reason.lower() or "forbidden" in reason.lower()
