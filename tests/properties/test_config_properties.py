"""Property-based tests for configuration management"""
import pytest
import os
import json
import tempfile
from pathlib import Path
from hypothesis import given, strategies as st, settings
from src.config_manager import ConfigurationManager


@pytest.fixture
def env_setup(monkeypatch):
    """Set up required environment variables"""
    monkeypatch.setenv("GITHUB_TOKEN", "test-github-token")
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")
    monkeypatch.setenv("SLACK_BOT_TOKEN", "test-slack-token")


class TestConfigurationProperties:
    """Property-based tests for configuration management"""

    @given(threshold=st.integers(min_value=0, max_value=10))
    @settings(max_examples=100)
    def test_property_52_environment_variable_loading(self, env_setup, threshold):
        """
        **Property 52: Environment Variable Loading**
        *For any* sensitive configuration value (API keys, tokens), the value should be 
        loadable from environment variables
        **Validates: Requirements 10.1**
        """
        config_manager = ConfigurationManager(config_file="/nonexistent/path.json")
        
        # Verify all sensitive values are loaded from environment
        assert config_manager.config.github_token == "test-github-token"
        assert config_manager.config.openai_api_key == "test-openai-key"
        assert config_manager.config.slack_bot_token == "test-slack-token"

    @given(
        threshold=st.integers(min_value=0, max_value=10),
        timeout=st.integers(min_value=1, max_value=72),
        interval=st.integers(min_value=1, max_value=60)
    )
    @settings(max_examples=100)
    def test_property_53_configuration_file_loading(self, env_setup, threshold, timeout, interval):
        """
        **Property 53: Configuration File Loading**
        *For any* non-sensitive configuration setting, the value should be loadable from 
        configuration files
        **Validates: Requirements 10.2**
        """
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            config_data = {
                "risk_threshold": threshold,
                "approval_timeout_hours": timeout,
                "polling_interval_minutes": interval
            }
            json.dump(config_data, f)
            f.flush()
            
            try:
                config_manager = ConfigurationManager(config_file=f.name)
                
                # Verify all non-sensitive values are loaded from file
                assert config_manager.get_risk_threshold() == threshold
                assert config_manager.get_approval_timeout() == timeout
                assert config_manager.get_polling_interval() == interval
            finally:
                Path(f.name).unlink()

    @given(
        threshold=st.integers(min_value=0, max_value=10),
        repo_threshold=st.integers(min_value=0, max_value=10)
    )
    @settings(max_examples=100)
    def test_property_54_configuration_reload(self, env_setup, threshold, repo_threshold):
        """
        **Property 54: Configuration Reload**
        *For any* configuration file update, the system should reload configuration 
        without requiring a restart
        **Validates: Requirements 10.3**
        """
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            config_data = {"risk_threshold": threshold}
            json.dump(config_data, f)
            f.flush()
            
            try:
                config_manager = ConfigurationManager(config_file=f.name)
                original_threshold = config_manager.get_risk_threshold()
                
                # Update config file
                config_data["risk_threshold"] = repo_threshold
                with open(f.name, 'w') as cf:
                    json.dump(config_data, cf)
                
                # Reload configuration
                config_manager.reload_configuration()
                
                # Verify new threshold is loaded
                assert config_manager.get_risk_threshold() == repo_threshold
            finally:
                Path(f.name).unlink()

    @given(
        global_threshold=st.integers(min_value=0, max_value=10),
        repo_threshold=st.integers(min_value=0, max_value=10),
        repo_name=st.text(min_size=1, max_size=50, alphabet=st.characters(blacklist_characters='/'))
    )
    @settings(max_examples=100)
    def test_property_55_per_repository_configuration_override(self, env_setup, global_threshold, repo_threshold, repo_name):
        """
        **Property 55: Per-Repository Configuration Override**
        *For any* repository with configured settings, those settings should override 
        global settings
        **Validates: Requirements 10.4**
        """
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            config_data = {
                "risk_threshold": global_threshold,
                "repository_configs": {
                    f"{repo_name}/repo": {
                        "risk_threshold": repo_threshold,
                        "protected": False
                    }
                }
            }
            json.dump(config_data, f)
            f.flush()
            
            try:
                config_manager = ConfigurationManager(config_file=f.name)
                
                # Verify repository-specific threshold overrides global
                assert config_manager.get_repo_risk_threshold(f"{repo_name}/repo") == repo_threshold
                
                # Verify other repositories use global threshold
                assert config_manager.get_repo_risk_threshold("other/repo") == global_threshold
            finally:
                Path(f.name).unlink()

    @given(threshold=st.integers(min_value=0, max_value=10))
    @settings(max_examples=100)
    def test_property_56_configuration_validation(self, env_setup, threshold):
        """
        **Property 56: Configuration Validation**
        *For any* invalid configuration, the system should reject it on startup with 
        clear error messages
        **Validates: Requirements 10.5**
        """
        # Valid threshold should not raise
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            config_data = {"risk_threshold": threshold}
            json.dump(config_data, f)
            f.flush()
            
            try:
                config_manager = ConfigurationManager(config_file=f.name)
                assert config_manager.get_risk_threshold() == threshold
            finally:
                Path(f.name).unlink()
        
        # Invalid threshold should raise
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            config_data = {"risk_threshold": 15}  # Invalid: > 10
            json.dump(config_data, f)
            f.flush()
            
            try:
                with pytest.raises(ValueError):
                    ConfigurationManager(config_file=f.name)
            finally:
                Path(f.name).unlink()
