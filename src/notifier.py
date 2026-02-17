"""Slack Notifier component for sending notifications"""
import logging
from typing import Dict, Any, Optional
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from src.models import FailureRecord, AnalysisResult, ApprovalRequest
from src.config_manager import ConfigurationManager

logger = logging.getLogger(__name__)


class SlackNotifier:
    """Send Slack notifications at each stage"""

    def __init__(self, slack_token: str, config: ConfigurationManager):
        """Initialize Slack notifier"""
        self.client = WebClient(token=slack_token)
        self.config = config

    def send_initial_alert(self, failure: FailureRecord) -> Optional[str]:
        """Send initial alert when failure is detected"""
        try:
            channel = self.config.get_slack_channel("alerts")
            
            message = {
                "channel": channel,
                "blocks": [
                    {
                        "type": "header",
                        "text": {
                            "type": "plain_text",
                            "text": "🚨 CI/CD Failure Detected"
                        }
                    },
                    {
                        "type": "section",
                        "fields": [
                            {
                                "type": "mrkdwn",
                                "text": f"*Repository:*\n{failure.repository}"
                            },
                            {
                                "type": "mrkdwn",
                                "text": f"*Branch:*\n{failure.branch}"
                            },
                            {
                                "type": "mrkdwn",
                                "text": f"*Commit:*\n{failure.commit_sha[:8]}"
                            },
                            {
                                "type": "mrkdwn",
                                "text": f"*Reason:*\n{failure.failure_reason[:100]}"
                            }
                        ]
                    }
                ]
            }
            
            response = self.client.chat_postMessage(**message)
            logger.info(f"Initial alert sent for failure {failure.failure_id}")
            return response["ts"]
        except SlackApiError as e:
            logger.error(f"Failed to send initial alert: {e}")
            return None

    def send_analysis_notification(self, failure: FailureRecord, analysis: AnalysisResult) -> Optional[str]:
        """Send analysis results notification"""
        try:
            channel = self.config.get_slack_channel("alerts")
            
            message = {
                "channel": channel,
                "blocks": [
                    {
                        "type": "header",
                        "text": {
                            "type": "plain_text",
                            "text": "📊 Analysis Complete"
                        }
                    },
                    {
                        "type": "section",
                        "fields": [
                            {
                                "type": "mrkdwn",
                                "text": f"*Category:*\n{analysis.category.value}"
                            },
                            {
                                "type": "mrkdwn",
                                "text": f"*Risk Score:*\n{analysis.risk_score}/10"
                            },
                            {
                                "type": "mrkdwn",
                                "text": f"*Confidence:*\n{analysis.confidence}%"
                            },
                            {
                                "type": "mrkdwn",
                                "text": f"*Effort:*\n{analysis.effort_estimate}"
                            }
                        ]
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"*Proposed Fix:*\n{analysis.proposed_fix[:500]}"
                        }
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "*Was this classification correct?*"
                        }
                    },
                    {
                        "type": "actions",
                        "block_id": f"feedback_{failure.failure_id}",
                        "elements": [
                            {
                                "type": "button",
                                "text": {"type": "plain_text", "text": "✅ Yes"},
                                "style": "primary",
                                "action_id": "feedback_correct",
                                "value": "correct"
                            },
                            {
                                "type": "button",
                                "text": {"type": "plain_text", "text": "❌ It's DevOps"},
                                "action_id": "feedback_devops",
                                "value": "devops"
                            },
                            {
                                "type": "button",
                                "text": {"type": "plain_text", "text": "❌ It's Developer"},
                                "action_id": "feedback_developer",
                                "value": "developer"
                            }
                        ]
                    }
                ]
            }
            
            response = self.client.chat_postMessage(**message)
            logger.info(f"Analysis notification sent for failure {failure.failure_id}")
            return response["ts"]
        except SlackApiError as e:
            logger.error(f"Failed to send analysis notification: {e}")
            return None

    def send_approval_request(self, failure: FailureRecord, analysis: AnalysisResult, 
                            request_id: str) -> Optional[str]:
        """Send approval request with interactive buttons"""
        try:
            channel = self.config.get_slack_channel("approvals")
            
            message = {
                "channel": channel,
                "blocks": [
                    {
                        "type": "header",
                        "text": {
                            "type": "plain_text",
                            "text": "⚠️ Approval Required"
                        }
                    },
                    {
                        "type": "section",
                        "fields": [
                            {
                                "type": "mrkdwn",
                                "text": f"*Repository:*\n{failure.repository}"
                            },
                            {
                                "type": "mrkdwn",
                                "text": f"*Risk Score:*\n{analysis.risk_score}/10"
                            }
                        ]
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"*Proposed Fix:*\n{analysis.proposed_fix}"
                        }
                    },
                    {
                        "type": "actions",
                        "elements": [
                            {
                                "type": "button",
                                "text": {
                                    "type": "plain_text",
                                    "text": "Approve"
                                },
                                "value": f"approve_{request_id}",
                                "style": "primary",
                                "action_id": f"approve_{request_id}"
                            },
                            {
                                "type": "button",
                                "text": {
                                    "type": "plain_text",
                                    "text": "Reject"
                                },
                                "value": f"reject_{request_id}",
                                "style": "danger",
                                "action_id": f"reject_{request_id}"
                            }
                        ]
                    }
                ]
            }
            
            response = self.client.chat_postMessage(**message)
            logger.info(f"Approval request sent for failure {failure.failure_id}")
            return response["ts"]
        except SlackApiError as e:
            logger.error(f"Failed to send approval request: {e}")
            return None

    def send_remediation_notification(self, failure: FailureRecord, success: bool, 
                                     result: str) -> Optional[str]:
        """Send remediation result notification"""
        try:
            channel = self.config.get_slack_channel("alerts")
            
            emoji = "✅" if success else "❌"
            status = "Succeeded" if success else "Failed"
            
            message = {
                "channel": channel,
                "blocks": [
                    {
                        "type": "header",
                        "text": {
                            "type": "plain_text",
                            "text": f"{emoji} Remediation {status}"
                        }
                    },
                    {
                        "type": "section",
                        "fields": [
                            {
                                "type": "mrkdwn",
                                "text": f"*Repository:*\n{failure.repository}"
                            },
                            {
                                "type": "mrkdwn",
                                "text": f"*Status:*\n{status}"
                            }
                        ]
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"*Result:*\n{result[:500]}"
                        }
                    }
                ]
            }
            
            response = self.client.chat_postMessage(**message)
            logger.info(f"Remediation notification sent for failure {failure.failure_id}")
            return response["ts"]
        except SlackApiError as e:
            logger.error(f"Failed to send remediation notification: {e}")
            return None

    def send_critical_alert(self, message_text: str) -> Optional[str]:
        """Send critical alert to ops channel"""
        try:
            channel = self.config.get_slack_channel("critical")
            
            message = {
                "channel": channel,
                "blocks": [
                    {
                        "type": "header",
                        "text": {
                            "type": "plain_text",
                            "text": "🔴 CRITICAL ALERT"
                        }
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": message_text
                        }
                    }
                ]
            }
            
            response = self.client.chat_postMessage(**message)
            logger.error(f"Critical alert sent: {message_text}")
            return response["ts"]
        except SlackApiError as e:
            logger.error(f"Failed to send critical alert: {e}")
            return None

    def send_developer_notification(self, failure, analysis) -> Optional[str]:
        """Send notification for developer code issues"""
        try:
            channel = self.config.get_slack_channel("alerts")
            
            message = {
                "channel": channel,
                "blocks": [
                    {
                        "type": "header",
                        "text": {
                            "type": "plain_text",
                            "text": "👨‍💻 Developer Code Issue Detected"
                        }
                    },
                    {
                        "type": "section",
                        "fields": [
                            {
                                "type": "mrkdwn",
                                "text": f"*Repository:*\n{failure.repository}"
                            },
                            {
                                "type": "mrkdwn",
                                "text": f"*Branch:*\n{failure.branch}"
                            },
                            {
                                "type": "mrkdwn",
                                "text": f"*Category:*\n{analysis.category.value}"
                            },
                            {
                                "type": "mrkdwn",
                                "text": f"*Confidence:*\n{analysis.confidence}%"
                            }
                        ]
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"*Issue:*\n{failure.failure_reason}"
                        }
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"*Analysis:*\n{analysis.reasoning}"
                        }
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"*Suggested Fix:*\n{analysis.proposed_fix}"
                        }
                    }
                ]
            }
            
            response = self.client.chat_postMessage(**message)
            logger.info(f"Developer notification sent for failure {failure.failure_id}")
            return response["ts"]
        except SlackApiError as e:
            logger.error(f"Failed to send developer notification: {e}")
            return None

    def send_devops_fix_notification(self, failure, analysis, pr_url: str, success: bool) -> Optional[str]:
        """Send notification for DevOps fixes with PR link"""
        try:
            channel = self.config.get_slack_channel("alerts")
            
            emoji = "✅" if success else "❌"
            status = "PR Created" if success else "PR Creation Failed"
            
            message = {
                "channel": channel,
                "blocks": [
                    {
                        "type": "header",
                        "text": {
                            "type": "plain_text",
                            "text": f"{emoji} DevOps Fix - {status}"
                        }
                    },
                    {
                        "type": "section",
                        "fields": [
                            {
                                "type": "mrkdwn",
                                "text": f"*Repository:*\n{failure.repository}"
                            },
                            {
                                "type": "mrkdwn",
                                "text": f"*Category:*\n{analysis.category.value}"
                            },
                            {
                                "type": "mrkdwn",
                                "text": f"*Risk Score:*\n{analysis.risk_score}/10"
                            },
                            {
                                "type": "mrkdwn",
                                "text": f"*Effort:*\n{analysis.effort_estimate}"
                            }
                        ]
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"*Issue:*\n{failure.failure_reason}"
                        }
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"*Fix:*\n{analysis.proposed_fix}"
                        }
                    }
                ]
            }
            
            if success:
                message["blocks"].append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"<{pr_url}|View Pull Request>"
                    }
                })
            else:
                message["blocks"].append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Error:* {pr_url}"
                    }
                })
            
            response = self.client.chat_postMessage(**message)
            logger.info(f"DevOps fix notification sent for failure {failure.failure_id}")
            return response["ts"]
        except SlackApiError as e:
            logger.error(f"Failed to send DevOps fix notification: {e}")
            return None
