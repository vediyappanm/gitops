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
        """Test fetching workflow run logs"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "Test log content"
        mock_response.headers = {}
        
        mock_instance = MagicMock()
        mock_instance.get.return_value = mock_response
        mock_instance.headers = {}
        mock_session.return_value = mock_instance
        
        client = GitHubClient("test-token")
        logs = client.get_workflow_run_logs("test/repo", 123)
        
        assert logs == "Test log content"


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
