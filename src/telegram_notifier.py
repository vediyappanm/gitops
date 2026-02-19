"""Telegram Notifier component for sending notifications"""
import logging
import requests
from typing import Dict, Any, Optional, List
from src.models import FailureRecord, AnalysisResult, ApprovalRequest
from src.config_manager import ConfigurationManager

logger = logging.getLogger(__name__)


class TelegramNotifier:
    """Send Telegram notifications at each stage"""

    def __init__(self, telegram_token: str, config: ConfigurationManager):
        """Initialize Telegram notifier"""
        self.token = telegram_token
        self.config = config
        self.api_url = f"https://api.telegram.org/bot{self.token}"

    def _send_message(self, chat_id: str, text: str, reply_markup: Optional[Dict] = None) -> Optional[str]:
        """Helper to send message via Telegram API"""
        if not chat_id:
            logger.warning("Telegram chat ID not configured, skipping notification")
            return None
            
        url = f"{self.api_url}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML"
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup
            
        try:
            response = requests.post(url, json=payload, timeout=10)
            if response.status_code != 200:
                logger.error(f"Telegram API error: {response.status_code} - {response.text}")
                return None
            result = response.json()
            if result.get("ok"):
                return str(result["result"]["message_id"])
            logger.error(f"Telegram API error: {result.get('description')}")
        except Exception as e:
            logger.error(f"Failed to send Telegram message: {e}")
        return None

    def _escape(self, text: str) -> str:
        """Escape special characters for Telegram HTML"""
        if not text:
            return ""
        return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    def send_initial_alert(self, failure: FailureRecord) -> Optional[str]:
        """Send initial alert when failure is detected"""
        chat_id = self.config.get_telegram_chat_id("alerts")
        
        text = (
            f"🚨 <b>CI/CD Failure Detected</b>\n\n"
            f"<b>Repository:</b> {self._escape(failure.repository)}\n"
            f"<b>Branch:</b> {self._escape(failure.branch)}\n"
            f"<b>Commit:</b> {self._escape(failure.commit_sha[:8])}\n"
            f"<b>Reason:</b> {self._escape(failure.failure_reason[:100])}"
        )
        
        return self._send_message(chat_id, text)

    def send_analysis_notification(self, failure: FailureRecord, analysis: AnalysisResult) -> Optional[str]:
        """Send analysis results notification"""
        chat_id = self.config.get_telegram_chat_id("alerts")
        
        text = (
            f"📊 <b>Analysis Complete</b>\n\n"
            f"<b>Category:</b> {self._escape(analysis.category.value)}\n"
            f"<b>Risk Score:</b> {self._escape(str(analysis.risk_score))}/10\n"
            f"<b>Confidence:</b> {self._escape(str(analysis.confidence))}%\n"
            f"<b>Effort:</b> {self._escape(analysis.effort_estimate)}\n\n"
            f"<b>Proposed Fix:</b>\n<pre>{self._escape(analysis.proposed_fix[:500])}</pre>\n\n"
            f"<b>Was this classification correct?</b>"
        )
        
        reply_markup = {
            "inline_keyboard": [[
                {"text": "✅ Yes", "callback_data": f"feedback_correct_{failure.failure_id}"},
                {"text": "❌ DevOps", "callback_data": f"feedback_devops_{failure.failure_id}"},
                {"text": "❌ Developer", "callback_data": f"feedback_developer_{failure.failure_id}"}
            ]]
        }
        
        return self._send_message(chat_id, text, reply_markup)

    def send_approval_request(self, failure: FailureRecord, analysis: AnalysisResult, 
                            request_id: str) -> Optional[str]:
        """Send approval request with interactive buttons"""
        chat_id = self.config.get_telegram_chat_id("approvals")
        
        text = (
            f"⚠️ <b>Approval Required</b>\n\n"
            f"<b>Repository:</b> {self._escape(failure.repository)}\n"
            f"<b>Risk Score:</b> {self._escape(str(analysis.risk_score))}/10\n\n"
            f"<b>Proposed Fix:</b>\n<pre>{self._escape(analysis.proposed_fix)}</pre>"
        )
        
        reply_markup = {
            "inline_keyboard": [[
                {"text": "✅ Approve", "callback_data": f"approve_{request_id}"},
                {"text": "❌ Reject", "callback_data": f"reject_{request_id}"}
            ]]
        }
        
        return self._send_message(chat_id, text, reply_markup)

    def send_remediation_notification(self, failure: FailureRecord, success: bool, 
                                     result: str) -> Optional[str]:
        """Send remediation result notification"""
        chat_id = self.config.get_telegram_chat_id("alerts")
        
        emoji = "✅" if success else "❌"
        status = "Succeeded" if success else "Failed"
        
        text = (
            f"{emoji} <b>Remediation {status}</b>\n\n"
            f"<b>Repository:</b> {self._escape(failure.repository)}\n"
            f"<b>Status:</b> {self._escape(status)}\n"
            f"<b>Result:</b> {self._escape(result[:500])}"
        )
        
        return self._send_message(chat_id, text)

    def send_critical_alert(self, message_text: str) -> Optional[str]:
        """Send critical alert to ops channel"""
        chat_id = self.config.get_telegram_chat_id("critical")
        
        text = f"🔴 <b>CRITICAL ALERT</b>\n\n{self._escape(message_text)}"
        
        return self._send_message(chat_id, text)

    def send_developer_notification(self, failure, analysis) -> Optional[str]:
        """Send notification for developer code issues"""
        chat_id = self.config.get_telegram_chat_id("alerts")
        
        text = (
            f"👨‍💻 <b>Developer Code Issue Detected</b>\n\n"
            f"<b>Repository:</b> {self._escape(failure.repository)}\n"
            f"<b>Branch:</b> {self._escape(failure.branch)}\n"
            f"<b>Category:</b> {self._escape(analysis.category.value)}\n"
            f"<b>Confidence:</b> {self._escape(str(analysis.confidence))}%\n\n"
            f"<b>Issue:</b> {self._escape(failure.failure_reason)}\n\n"
            f"<b>Analysis:</b> {self._escape(analysis.reasoning)}\n\n"
            f"<b>Suggested Fix:</b> <pre>{self._escape(analysis.proposed_fix)}</pre>"
        )
        
        return self._send_message(chat_id, text)

    def send_devops_fix_notification(self, failure, analysis, pr_url: str, success: bool) -> Optional[str]:
        """Send notification for DevOps fixes with PR link"""
        chat_id = self.config.get_telegram_chat_id("alerts")
        
        emoji = "✅" if success else "❌"
        status = "PR Created" if success else "PR Creation Failed"
        
        text = (
            f"{emoji} <b>DevOps Fix - {status}</b>\n\n"
            f"<b>Repository:</b> {self._escape(failure.repository)}\n"
            f"<b>Category:</b> {self._escape(analysis.category.value)}\n"
            f"<b>Risk Score:</b> {self._escape(str(analysis.risk_score))}/10\n"
            f"<b>Effort:</b> {self._escape(analysis.effort_estimate)}\n\n"
            f"<b>Issue:</b> {self._escape(failure.failure_reason)}\n\n"
            f"<b>Fix:</b> <pre>{self._escape(analysis.proposed_fix)}</pre>"
        )
        
        reply_markup = None
        if success:
            reply_markup = {
                "inline_keyboard": [[
                    {"text": "🔗 View Pull Request", "url": pr_url}
                ]]
            }
        else:
            text += f"\n\n<b>Error:</b> {self._escape(pr_url)}"
            
        return self._send_message(chat_id, text, reply_markup)
