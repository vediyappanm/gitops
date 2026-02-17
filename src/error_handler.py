"""Error handling and recovery for CI/CD Failure Monitor"""
import logging
import time
from typing import Callable, Any, Optional
from src.notifier import SlackNotifier

logger = logging.getLogger(__name__)


class ErrorHandler:
    """Handle errors and implement recovery strategies"""

    def __init__(self, notifier: Optional[SlackNotifier] = None):
        """Initialize error handler"""
        self.notifier = notifier

    def handle_error(self, error: Exception, context: str, actor: str) -> None:
        """Handle an error with logging and alerting"""
        logger.error(f"Error in {actor} ({context}): {error}", exc_info=True)
        
        # Send critical alert for critical errors
        if self._is_critical_error(error):
            self._send_critical_alert(error, context, actor)

    def _is_critical_error(self, error: Exception) -> bool:
        """Determine if error is critical"""
        critical_keywords = [
            "database", "connection", "authentication", "auth", "token",
            "permission", "denied", "unauthorized"
        ]
        
        error_str = str(error).lower()
        return any(keyword in error_str for keyword in critical_keywords)

    def _send_critical_alert(self, error: Exception, context: str, actor: str) -> None:
        """Send critical alert to Slack"""
        if self.notifier:
            message = f"Critical error in {actor} ({context}): {error}"
            self.notifier.send_critical_alert(message)

    def retry_with_backoff(self, func: Callable, max_retries: int = 3, 
                          initial_backoff: int = 1, max_backoff: int = 60) -> Any:
        """Retry a function with exponential backoff"""
        backoff = initial_backoff
        last_error = None
        
        for attempt in range(max_retries):
            try:
                return func()
            except Exception as e:
                last_error = e
                logger.warning(f"Attempt {attempt + 1} failed: {e}")
                
                if attempt < max_retries - 1:
                    wait_time = min(backoff, max_backoff)
                    logger.info(f"Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                    backoff *= 2
        
        logger.error(f"All {max_retries} attempts failed")
        raise last_error

    def handle_service_failure(self, service_name: str, restart_func: Callable) -> None:
        """Handle service failure with automatic restart"""
        logger.error(f"Service {service_name} failed")
        
        backoff = 1
        max_backoff = 60
        
        for attempt in range(5):
            try:
                logger.info(f"Attempting to restart {service_name} (attempt {attempt + 1})")
                restart_func()
                logger.info(f"Service {service_name} restarted successfully")
                return
            except Exception as e:
                logger.error(f"Failed to restart {service_name}: {e}")
                
                if attempt < 4:
                    wait_time = min(backoff, max_backoff)
                    logger.info(f"Retrying restart in {wait_time} seconds...")
                    time.sleep(wait_time)
                    backoff *= 2
        
        logger.critical(f"Failed to restart service {service_name} after 5 attempts")
        if self.notifier:
            self.notifier.send_critical_alert(
                f"Service {service_name} failed to restart after 5 attempts"
            )
