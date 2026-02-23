"""Unit tests for GitHub API client"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from src.github_client import GitHubClient


@pytest.fixture
def mock_session():
    """Create a mock requests session"""
    with patch('src.github_client.requests.Session') as mock:
        yield mock


class TestGitHubAuthentication:
    """Test GitHub authentication"""

    def test_authentication_success(self, mock_session):
        """Test successful authentication"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"login": "test-user"}
        
        mock_instance = MagicMock()
        mock_instance.get.return_value = mock_response
        mock_instance.headers = {}
        mock_session.return_value = mock_instance
        
        client = GitHubClient("test-token")
        assert client.token == "test-token"

    def test_authentication_failure(self, mock_session):
        """Test authentication failure"""
        mock_response = Mock()
        mock_response.status_code = 401
        
        mock_instance = MagicMock()
        mock_instance.get.return_value = mock_response
        mock_instance.headers = {}
        mock_session.return_value = mock_instance
        
        with pytest.raises(ValueError):
            GitHubClient("invalid-token")


class TestWorkflowRunFetching:
    """Test workflow run fetching"""

    def test_get_failed_workflow_runs(self, mock_session):
        """Test fetching failed workflow runs"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "workflow_runs": [
                {
                    "id": 123,
                    "name": "Test Workflow",
                    "status": "failure",
                    "conclusion": "failure"
                }
            ]
        }
        mock_response.headers = {}
        
        mock_instance = MagicMock()
        mock_instance.get.return_value = mock_response
        mock_instance.headers = {}
        mock_session.return_value = mock_instance
        
        client = GitHubClient("test-token")
        runs = client.get_failed_workflow_runs("test/repo")
        
        assert len(runs) == 1
        assert runs[0]["id"] == 123

    def test_get_workflow_run_details(self, mock_session):
        """Test fetching workflow run details"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": 123,
            "name": "Test Workflow",
            "status": "failure",
            "head_commit": {"sha": "abc123"}
        }
        mock_response.headers = {}
        
        mock_instance = MagicMock()
        mock_instance.get.return_value = mock_response
        mock_instance.headers = {}
        mock_session.return_value = mock_instance
        
        client = GitHubClient("test-token")
        details = client.get_workflow_run_details("test/repo", 123)
        
        assert details["id"] == 123
        assert details["status"] == "failure"

    def test_get_workflow_run_logs(self, mock_session):
        """Test fetching workflow run logs from failed jobs"""
        # Mock for authentication
        mock_auth_response = Mock()
        mock_auth_response.status_code = 200
        mock_auth_response.json.return_value = {"login": "test-user"}
        mock_auth_response.headers = {}

        # Mock for get_workflow_run_jobs
        mock_jobs_response = Mock()
        mock_jobs_response.status_code = 200
        mock_jobs_response.json.return_value = {
            "jobs": [{"id": 1, "name": "Job 1", "conclusion": "failure"}]
        }
        mock_jobs_response.headers = {}
        
        # Mock for get_job_logs
        mock_logs_response = Mock()
        mock_logs_response.status_code = 200
        mock_logs_response.text = "Job 1 logs"
        mock_logs_response.headers = {}
        
        mock_instance = MagicMock()
        # Authentication -> Jobs -> Logs
        mock_instance.get.side_effect = [mock_auth_response, mock_jobs_response, mock_logs_response]
        mock_instance.headers = {}
        mock_session.return_value = mock_instance
        
        client = GitHubClient("test-token")
        logs = client.get_workflow_run_logs("test/repo", 123)
        
        assert "Job 1 logs" in logs
        assert "--- LOGS FOR JOB: Job 1 ---" in logs


class TestRateLimitHandling:
    """Test rate limit handling"""

    def test_rate_limit_status(self, mock_session):
        """Test getting rate limit status"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "resources": {
                "core": {
                    "limit": 5000,
                    "remaining": 4999,
                    "reset": 1234567890
                }
            }
        }
        mock_response.headers = {}
        
        mock_instance = MagicMock()
        mock_instance.get.return_value = mock_response
        mock_instance.headers = {}
        mock_session.return_value = mock_instance
        
        client = GitHubClient("test-token")
        status = client.get_rate_limit_status()
        
        assert status["resources"]["core"]["limit"] == 5000


class TestBranchAwareBranching:
    """Test branch-aware branching and PR logic"""

    def test_create_fix_branch_from_broken(self, mock_session):
        """Test fix branch created from broken branch (not main)"""
        # Mock getting SHA for the broken branch
        mock_sha_response = Mock()
        mock_sha_response.status_code = 200
        mock_sha_response.json.return_value = {"object": {"sha": "broken_sha"}}
        mock_sha_response.headers = {}
        
        # Mock creating the branch
        mock_create_response = Mock()
        mock_create_response.status_code = 201
        mock_create_response.headers = {}
        
        mock_instance = MagicMock()
        mock_instance.get.return_value = mock_sha_response
        mock_instance.post.return_value = mock_create_response
        mock_instance.headers = {}
        mock_session.return_value = mock_instance
        
        client = GitHubClient("test-token")
        branch_name = client.create_fix_branch_from_broken("test/repo", "teammate-branch")
        
        assert branch_name is not None
        assert branch_name.startswith("agent-fix/teammate-branch-")
        
        # Verify SHA source
        mock_instance.get.assert_called_with(
            "https://api.github.com/repos/test/repo/git/refs/heads/teammate-branch"
        )
        # Verify creation parameters
        args, kwargs = mock_instance.post.call_args
        assert kwargs["json"]["sha"] == "broken_sha"
        assert kwargs["json"]["ref"] == f"refs/heads/{branch_name}"

    def test_create_pull_request_branch_aware(self, mock_session):
        """Test PR created with correct base branch"""
        mock_response = Mock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"html_url": "https://github.com/test/repo/pull/1"}
        mock_response.headers = {}
        
        mock_instance = MagicMock()
        mock_instance.post.return_value = mock_response
        mock_instance.headers = {}
        mock_session.return_value = mock_instance
        
        client = GitHubClient("test-token")
        pr_url = client.create_pull_request(
            "test/repo", "Agent Fix", "Body", "agent-fix/branch", "teammate-branch"
        )
        
        assert pr_url == "https://github.com/test/repo/pull/1"
        # Verify base branch targeting
        args, kwargs = mock_instance.post.call_args
        assert kwargs["json"]["base"] == "teammate-branch"
        assert kwargs["json"]["head"] == "agent-fix/branch"
