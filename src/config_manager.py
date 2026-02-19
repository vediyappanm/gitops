"""Configuration management for CI/CD Failure Monitor"""
import os
import json
import logging
from typing import Dict, Any, Optional
from pathlib import Path
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class RepositoryConfig:
    """Per-repository configuration"""
    name: str
    risk_threshold: Optional[int] = None
    protected: bool = False


@dataclass
class Configuration:
    """System configuration"""
    github_token: str
    groq_api_key: str
    slack_bot_token: Optional[str] = None
    telegram_bot_token: Optional[str] = None
    risk_threshold: int = 5
    protected_repositories: list = field(default_factory=list)
    slack_channels: Dict[str, str] = field(default_factory=lambda: {
        "alerts": "#ci-cd-alerts",
        "approvals": "#ci-cd-approvals",
        "critical": "#critical-alerts"
    })
    telegram_chat_ids: Dict[str, str] = field(default_factory=lambda: {
        "alerts": "",
        "approvals": "",
        "critical": ""
    })
    approval_timeout_hours: int = 24
    polling_interval_minutes: int = 5
    retry_count: int = 3
    retry_backoff_seconds: int = 1
    repository_configs: Dict[str, RepositoryConfig] = field(default_factory=dict)

    def validate(self) -> None:
        """Validate configuration"""
        if not self.github_token:
            raise ValueError("GitHub token is required")
        if not self.groq_api_key:
            raise ValueError("Groq API key is required")
        if not self.slack_bot_token and not self.telegram_bot_token:
            raise ValueError("Either Slack bot token or Telegram bot token must be provided")
        if not (0 <= self.risk_threshold <= 10):
            raise ValueError("Risk threshold must be between 0 and 10")
        if self.approval_timeout_hours <= 0:
            raise ValueError("Approval timeout must be positive")
        if self.polling_interval_minutes <= 0:
            raise ValueError("Polling interval must be positive")


class ConfigurationManager:
    """Manage system configuration from environment and files"""

    def __init__(self, config_file: Optional[str] = None):
        """Initialize configuration manager"""
        self.config_file = config_file or "config.json"
        self.config: Optional[Configuration] = None
        self.load_configuration()

    def load_configuration(self) -> None:
        """Load configuration from environment and files"""
        logger.info("Loading configuration...")
        
        # Load from environment
        github_token = os.getenv("GITHUB_TOKEN")
        groq_api_key = os.getenv("GROQ_API_KEY")
        slack_bot_token = os.getenv("SLACK_BOT_TOKEN")
        telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        
        if not all([github_token, groq_api_key]) or (not slack_bot_token and not telegram_bot_token):
            raise ValueError("Required environment variables not set: GITHUB_TOKEN, GROQ_API_KEY, and either SLACK_BOT_TOKEN or TELEGRAM_BOT_TOKEN")
        
        # Load from config file if it exists
        config_data = {
            "github_token": github_token,
            "groq_api_key": groq_api_key,
            "slack_bot_token": slack_bot_token,
            "telegram_bot_token": telegram_bot_token,
            "risk_threshold": 5,
            "protected_repositories": [],
            "slack_channels": {
                "alerts": "#ci-cd-alerts",
                "approvals": "#ci-cd-approvals",
                "critical": "#critical-alerts"
            },
            "telegram_chat_ids": {
                "alerts": os.getenv("TELEGRAM_CHAT_ID", ""),
                "approvals": os.getenv("TELEGRAM_CHAT_ID", ""),
                "critical": os.getenv("TELEGRAM_CHAT_ID", "")
            },
            "approval_timeout_hours": 24,
            "polling_interval_minutes": 5,
            "retry_count": 3,
            "retry_backoff_seconds": 1,
            "repository_configs": {}
        }
        
        if Path(self.config_file).exists():
            try:
                with open(self.config_file, 'r') as f:
                    file_data = json.load(f)
                    config_data.update(file_data)
                logger.info(f"Loaded configuration from {self.config_file}")
            except Exception as e:
                logger.error(f"Failed to load configuration file: {e}")
                raise
        
        # Convert repository configs
        repo_configs = {}
        
        # Handle both "repositories" and "repository_configs" fields
        if "repositories" in config_data:
            # Convert repositories list to repository_configs dict
            for repo in config_data.get("repositories", []):
                if isinstance(repo, dict):
                    repo_name = f"{repo.get('owner', 'unknown')}/{repo.get('name', 'unknown')}"
                    repo_configs[repo_name] = RepositoryConfig(
                        name=repo_name,
                        risk_threshold=repo.get("risk_threshold"),
                        protected=repo.get("protected", False)
                    )
            del config_data["repositories"]
        
        if "repository_configs" in config_data:
            for repo_name, repo_config in config_data["repository_configs"].items():
                repo_configs[repo_name] = RepositoryConfig(
                    name=repo_name,
                    risk_threshold=repo_config.get("risk_threshold"),
                    protected=repo_config.get("protected", False)
                )
        
        config_data["repository_configs"] = repo_configs
        
        self.config = Configuration(**config_data)
        self.config.validate()
        logger.info("Configuration loaded and validated successfully")

    def reload_configuration(self) -> None:
        """Reload configuration without restart"""
        logger.info("Reloading configuration...")
        self.load_configuration()
        logger.info("Configuration reloaded")

    def get_risk_threshold(self) -> int:
        """Get global risk threshold"""
        if not self.config:
            raise RuntimeError("Configuration not loaded")
        return self.config.risk_threshold

    def get_repo_risk_threshold(self, repo: str) -> int:
        """Get repository-specific risk threshold or global threshold"""
        if not self.config:
            raise RuntimeError("Configuration not loaded")
        
        if repo in self.config.repository_configs:
            repo_config = self.config.repository_configs[repo]
            if repo_config.risk_threshold is not None:
                return repo_config.risk_threshold
        
        return self.config.risk_threshold

    def is_protected_repository(self, repo: str) -> bool:
        """Check if repository is protected"""
        if not self.config:
            raise RuntimeError("Configuration not loaded")
        
        if repo in self.config.repository_configs:
            return self.config.repository_configs[repo].protected
        
        return repo in self.config.protected_repositories

    def get_slack_channels(self) -> Dict[str, str]:
        """Get configured Slack channels"""
        if not self.config:
            raise RuntimeError("Configuration not loaded")
        return self.config.slack_channels

    def get_telegram_chat_id(self, channel_type: str) -> str:
        """Get specific Telegram chat ID"""
        if not self.config:
            raise RuntimeError("Configuration not loaded")
        return self.config.telegram_chat_ids.get(channel_type, "")

    def get_approval_timeout(self) -> int:
        """Get approval timeout in hours"""
        if not self.config:
            raise RuntimeError("Configuration not loaded")
        return self.config.approval_timeout_hours

    def get_polling_interval(self) -> int:
        """Get polling interval in minutes"""
        if not self.config:
            raise RuntimeError("Configuration not loaded")
        return self.config.polling_interval_minutes

    def get_retry_config(self) -> Dict[str, int]:
        """Get retry configuration"""
        if not self.config:
            raise RuntimeError("Configuration not loaded")
        return {
            "count": self.config.retry_count,
            "backoff_seconds": self.config.retry_backoff_seconds
        }

    def set_risk_threshold(self, threshold: int) -> None:
        """Set global risk threshold"""
        if not self.config:
            raise RuntimeError("Configuration not loaded")
        if not (0 <= threshold <= 10):
            raise ValueError("Risk threshold must be between 0 and 10")
        self.config.risk_threshold = threshold
        logger.info(f"Risk threshold updated to {threshold}")

    def set_repo_risk_threshold(self, repo: str, threshold: int) -> None:
        """Set repository-specific risk threshold"""
        if not self.config:
            raise RuntimeError("Configuration not loaded")
        if not (0 <= threshold <= 10):
            raise ValueError("Risk threshold must be between 0 and 10")
        
        if repo not in self.config.repository_configs:
            self.config.repository_configs[repo] = RepositoryConfig(name=repo)
        
        self.config.repository_configs[repo].risk_threshold = threshold
        logger.info(f"Risk threshold for {repo} updated to {threshold}")

    def add_protected_repository(self, repo: str) -> None:
        """Add repository to protected list"""
        if not self.config:
            raise RuntimeError("Configuration not loaded")
        
        if repo not in self.config.repository_configs:
            self.config.repository_configs[repo] = RepositoryConfig(name=repo, protected=True)
        else:
            self.config.repository_configs[repo].protected = True
        
        logger.info(f"Repository {repo} marked as protected")

    def remove_protected_repository(self, repo: str) -> None:
        """Remove repository from protected list"""
        if not self.config:
            raise RuntimeError("Configuration not loaded")
        
        if repo in self.config.repository_configs:
            self.config.repository_configs[repo].protected = False
        
        logger.info(f"Repository {repo} removed from protected list")

    def get_all_protected_repositories(self) -> list:
        """Get all protected repositories"""
        if not self.config:
            raise RuntimeError("Configuration not loaded")
        
        protected = list(self.config.protected_repositories)
        for repo_name, repo_config in self.config.repository_configs.items():
            if repo_config.protected and repo_name not in protected:
                protected.append(repo_name)
        
        return protected
