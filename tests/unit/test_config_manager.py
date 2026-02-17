"""Unit tests for configuration manager"""
import pytest
import os
import json
import tempfile
from pathlib import Path
from src.config_manager import ConfigurationManager, Configuration, RepositoryConfig


@pytest.fixture
def env_setup(monkeypatch):
    """Set up required environment variables"""
    monkeypatch.setenv("GITHUB_TOKEN", "test-github-token")
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")
    monkeypatch.setenv("SLACK_BOT_TOKEN", "test-slack-token")


@pytest.fixture
def config_file():
    """Create a temporary config file"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        config_data = {
            "risk_threshold": 6,
            "protected_repositories": ["critical/repo"],
            "slack_channels": {
                "alerts": "#alerts",
                "approvals": "#approvals",
                "critical": "#critical"
            },
            "approval_timeout_hours": 48,
            "polling_interval_minutes": 10,
            "repository_configs": {
                "special/repo": {
                    "risk_threshold": 3,
                    "protected": True
                }
            }
        }
        json.dump(config_data, f)
        f.flush()
        yield f.name
    
    # Cleanup
    Path(f.name).unlink()


class TestConfigurationLoading:
    """Test configuration loading"""

    def test_load_from_environment(self, env_setup):
        """Test loading configuration from environment variables"""
        config_manager = ConfigurationManager(config_file="/nonexistent/path.json")
        
        assert config_manager.config.github_token == "test-github-token"
        assert config_manager.config.openai_api_key == "test-openai-key"
        assert config_manager.config.slack_bot_token == "test-slack-token"

    def test_load_from_config_file(self, env_setup, config_file):
        """Test loading configuration from file"""
        config_manager = ConfigurationManager(config_file=config_file)
        
        assert config_manager.get_risk_threshold() == 6
        assert config_manager.get_approval_timeout() == 48
        assert config_manager.get_polling_interval() == 10

    def test_missing_environment_variables(self, monkeypatch):
        """Test error when required environment variables are missing"""
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("SLACK_BOT_TOKEN", raising=False)
        
        with pytest.raises(ValueError):
            ConfigurationManager(config_file="/nonexistent/path.json")

    def test_invalid_risk_threshold(self, env_setup):
        """Test validation of invalid risk threshold"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({"risk_threshold": 15}, f)
            f.flush()
            
            with pytest.raises(ValueError):
                ConfigurationManager(config_file=f.name)
            
            Path(f.name).unlink()


class TestRiskThresholdManagement:
    """Test risk threshold configuration"""

    def test_get_global_risk_threshold(self, env_setup):
        """Test getting global risk threshold"""
        config_manager = ConfigurationManager(config_file="/nonexistent/path.json")
        assert config_manager.get_risk_threshold() == 5  # Default

    def test_set_global_risk_threshold(self, env_setup):
        """Test setting global risk threshold"""
        config_manager = ConfigurationManager(config_file="/nonexistent/path.json")
        config_manager.set_risk_threshold(7)
        assert config_manager.get_risk_threshold() == 7

    def test_get_repo_specific_threshold(self, env_setup, config_file):
        """Test getting repository-specific threshold"""
        config_manager = ConfigurationManager(config_file=config_file)
        
        # Repository with override
        assert config_manager.get_repo_risk_threshold("special/repo") == 3
        
        # Repository without override
        assert config_manager.get_repo_risk_threshold("other/repo") == 6

    def test_set_repo_specific_threshold(self, env_setup):
        """Test setting repository-specific threshold"""
        config_manager = ConfigurationManager(config_file="/nonexistent/path.json")
        config_manager.set_repo_risk_threshold("test/repo", 4)
        
        assert config_manager.get_repo_risk_threshold("test/repo") == 4
        assert config_manager.get_risk_threshold() == 5  # Global unchanged

    def test_invalid_threshold_value(self, env_setup):
        """Test validation of invalid threshold values"""
        config_manager = ConfigurationManager(config_file="/nonexistent/path.json")
        
        with pytest.raises(ValueError):
            config_manager.set_risk_threshold(15)
        
        with pytest.raises(ValueError):
            config_manager.set_risk_threshold(-1)


class TestProtectedRepositories:
    """Test protected repository management"""

    def test_is_protected_repository(self, env_setup, config_file):
        """Test checking if repository is protected"""
        config_manager = ConfigurationManager(config_file=config_file)
        
        assert config_manager.is_protected_repository("critical/repo") is True
        assert config_manager.is_protected_repository("special/repo") is True
        assert config_manager.is_protected_repository("normal/repo") is False

    def test_add_protected_repository(self, env_setup):
        """Test adding a protected repository"""
        config_manager = ConfigurationManager(config_file="/nonexistent/path.json")
        
        assert config_manager.is_protected_repository("test/repo") is False
        config_manager.add_protected_repository("test/repo")
        assert config_manager.is_protected_repository("test/repo") is True

    def test_remove_protected_repository(self, env_setup, config_file):
        """Test removing a protected repository"""
        config_manager = ConfigurationManager(config_file=config_file)
        
        assert config_manager.is_protected_repository("critical/repo") is True
        config_manager.remove_protected_repository("critical/repo")
        assert config_manager.is_protected_repository("critical/repo") is False

    def test_get_all_protected_repositories(self, env_setup, config_file):
        """Test getting all protected repositories"""
        config_manager = ConfigurationManager(config_file=config_file)
        
        protected = config_manager.get_all_protected_repositories()
        assert "critical/repo" in protected
        assert "special/repo" in protected


class TestSlackChannels:
    """Test Slack channel configuration"""

    def test_get_slack_channels(self, env_setup):
        """Test getting all Slack channels"""
        config_manager = ConfigurationManager(config_file="/nonexistent/path.json")
        channels = config_manager.get_slack_channels()
        
        assert "alerts" in channels
        assert "approvals" in channels
        assert "critical" in channels

    def test_get_specific_slack_channel(self, env_setup):
        """Test getting specific Slack channel"""
        config_manager = ConfigurationManager(config_file="/nonexistent/path.json")
        
        assert config_manager.get_slack_channel("alerts") == "#ci-cd-alerts"
        assert config_manager.get_slack_channel("approvals") == "#ci-cd-approvals"
        assert config_manager.get_slack_channel("critical") == "#critical-alerts"

    def test_get_nonexistent_channel(self, env_setup):
        """Test getting nonexistent channel returns default"""
        config_manager = ConfigurationManager(config_file="/nonexistent/path.json")
        
        assert config_manager.get_slack_channel("nonexistent") == "#ci-cd-alerts"


class TestRetryConfiguration:
    """Test retry configuration"""

    def test_get_retry_config(self, env_setup):
        """Test getting retry configuration"""
        config_manager = ConfigurationManager(config_file="/nonexistent/path.json")
        retry_config = config_manager.get_retry_config()
        
        assert retry_config["count"] == 3
        assert retry_config["backoff_seconds"] == 1


class TestConfigurationReload:
    """Test configuration reload"""

    def test_reload_configuration(self, env_setup, config_file):
        """Test reloading configuration"""
        config_manager = ConfigurationManager(config_file=config_file)
        original_threshold = config_manager.get_risk_threshold()
        
        # Modify config file
        with open(config_file, 'r') as f:
            config_data = json.load(f)
        config_data["risk_threshold"] = 8
        with open(config_file, 'w') as f:
            json.dump(config_data, f)
        
        # Reload
        config_manager.reload_configuration()
        
        assert config_manager.get_risk_threshold() == 8
        assert config_manager.get_risk_threshold() != original_threshold
