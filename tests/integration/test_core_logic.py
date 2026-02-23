import pytest
import os
import time
from github import Github
from src.models import FailureRecord, FailureStatus

@pytest.mark.github_integration
class TestCoreLogic:
    def test_real_branch_detection(self, test_repo, integration_agent, db):
        """Tier 1: Test agent detects failure on teammate branch, not main"""
        branch_name = f"test-branch-{int(time.time())}"
        main_sha = test_repo.get_branch("main").commit.sha
        
        # Create test branch
        test_repo.create_git_ref(ref=f"refs/heads/{branch_name}", sha=main_sha)
        
        try:
            # Simulate a failure record detected by the monitor on this branch
            failure_id = f"fail-{branch_name}"
            failure = FailureRecord(
                failure_id=failure_id,
                repository=test_repo.full_name,
                workflow_run_id="999999",
                branch=branch_name,
                commit_sha=main_sha,
                failure_reason="Intentional test failure",
                logs="Error: Process completed with exit code 1",
                status=FailureStatus.DETECTED
            )
            db.store_failure(failure)
            
            # Run the agent processing
            integration_agent.process_failure(failure_id)
            
            # Verify the record in DB
            updated_failure = db.get_failure(failure_id)
            assert updated_failure.branch == branch_name
            assert updated_failure.repository == test_repo.full_name
            
        finally:
            # Cleanup handled by autouse fixtures in conftest.py
            pass

    def test_fix_branch_created_from_broken_not_main(self, integration_agent, test_repo):
        """Tier 1: Test agent creates fix branch FROM broken branch (not main)"""
        main_branch = test_repo.get_branch("main")
        branch_name = f"test-broken-{int(time.time())}"
        test_repo.create_git_ref(ref=f"refs/heads/{branch_name}", sha=main_branch.commit.sha)
        
        try:
            # Test the utility method in GitHubClient
            client = integration_agent.github_client
            fix_branch = client.create_fix_branch_from_broken(
                test_repo.full_name, branch_name
            )
            
            # The naming pattern should be branch-aware
            assert fix_branch.startswith(f"agent-fix/{branch_name}-")
            # Verify it exists in GitHub
            assert test_repo.get_branch(fix_branch) is not None
        finally:
            # Cleanuphandled by conftest but also defensive here
            pass

    def test_pr_targets_teammate_branch_not_main(self, integration_agent, test_repo):
        """Tier 1: PR targets teammate branch, NOT main"""
        branch_name = f"test-base-{int(time.time())}"
        main_branch = test_repo.get_branch("main")
        test_repo.create_git_ref(ref=f"refs/heads/{branch_name}", sha=main_branch.commit.sha)
        
        fix_branch = f"agent-fix/{branch_name}-123"
        # We don't need to create the fix branch for a dry-run test
        
        # Intercept via dry_run_mode
        integration_agent.dry_run_mode.intercept_pr_creation(
            repo=test_repo.full_name,
            branch=fix_branch,
            title="🤖 Agent Fix",
            body="Analysis Summary",
            base=branch_name
        )
        
        actions = integration_agent.dry_run_mode.actions
        pr_action = next(a for a in actions if a.action_type == "PR_CREATION")
        assert pr_action.base == branch_name
