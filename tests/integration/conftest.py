import pytest
import os
from github import Github
from unittest.mock import MagicMock, patch
from src.database import Database
from src.config_manager import ConfigurationManager
from src.agent import CICDFailureMonitorAgent

@pytest.fixture(scope="session")
def github_client():
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        pytest.skip("GITHUB_TOKEN not set — skipping real GitHub tests")
    return Github(token)

@pytest.fixture(scope="session")
def test_repo_name():
    return os.environ.get("REPOSITORIES", "vediyappanm/UltraThinking-LLM-Training").split(",")[0].strip()

@pytest.fixture(scope="session")
def test_repo(github_client, test_repo_name):
    return github_client.get_repo(test_repo_name)

@pytest.fixture(autouse=True)
def cleanup_test_branches(test_repo):
    """Auto-cleanup: delete all agent-fix/* and test-* branches after each test."""
    yield
    for branch in test_repo.get_branches():
        if branch.name.startswith(("agent-fix/", "test-")):
            try:
                test_repo.get_git_ref(f"heads/{branch.name}").delete()
            except Exception:
                pass  # best-effort cleanup

@pytest.fixture(autouse=True)
def cleanup_open_prs(test_repo):
    """Auto-cleanup: close all agent PRs after each test."""
    yield
    for pr in test_repo.get_pulls(state="open"):
        if "🤖 Agent Fix" in pr.title:
            pr.edit(state="closed")

@pytest.fixture(autouse=True)
def mock_background_services():
    """Mock background services to avoid port conflicts and metric duplicate errors."""
    with patch("src.agent.start_http_server"), \
         patch("src.agent.Counter"), \
         patch("src.agent.Gauge"), \
         patch("src.agent.WebDashboard"), \
         patch("src.agent.HealthReportGenerator"):
        yield

@pytest.fixture
def integration_agent(db):
    config_file = os.getenv("CONFIG_FILE", "config.json")
    config = ConfigurationManager(config_file=config_file)
    # Ensure environment variables are loaded for the agent's client initializations
    token = os.environ.get("GITHUB_TOKEN")
    groq_api_key = os.environ.get("GROQ_API_KEY")
    if not token or not groq_api_key:
        pytest.skip("Required environment variables (GITHUB_TOKEN, GROQ_API_KEY) not set")
        
    agent = CICDFailureMonitorAgent(config, db, dry_run=True) 
    return agent
