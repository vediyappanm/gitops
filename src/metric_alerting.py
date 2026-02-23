"""Metric Threshold Alerting component for monitoring system health"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from enum import Enum
from apscheduler.schedulers.background import BackgroundScheduler

logger = logging.getLogger(__name__)


# Constants
SUCCESS_RATE_THRESHOLD = 80.0  # Alert if below 80%
RESOLUTION_TIME_SPIKE_MULTIPLIER = 2.0  # Alert if 2x baseline
BASELINE_WINDOW_DAYS = 7  # Calculate baseline from last 7 days
CHECK_INTERVAL_MINUTES = 15  # Check metrics every 15 minutes


class AlertSeverity(str, Enum):
    """Alert severity levels"""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class MetricAlert:
    """Metric threshold alert"""
    alert_id: str
    severity: AlertSeverity
    metric_name: str
    current_value: float
    threshold_value: float
    message: str
    repository: Optional[str] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "alert_id": self.alert_id,
            "severity": self.severity.value,
            "metric_name": self.metric_name,
            "current_value": self.current_value,
            "threshold_value": self.threshold_value,
            "message": self.message,
            "repository": self.repository,
            "timestamp": self.timestamp.isoformat()
        }


@dataclass
class MetricBaseline:
    """Baseline metrics for comparison"""
    success_rate: float
    avg_resolution_time_ms: float
    total_failures: int
    calculated_at: datetime
    window_days: int


class MetricAlertingEngine:
    """Monitor metrics and fire alerts when thresholds are breached"""

    def __init__(self, database, notifier, metrics_tracker, 
                 success_rate_threshold: float = SUCCESS_RATE_THRESHOLD,
                 resolution_time_multiplier: float = RESOLUTION_TIME_SPIKE_MULTIPLIER):
        """
        Initialize metric alerting engine.
        
        Args:
            database: Database instance for querying metrics
            notifier: Notifier instance for sending alerts
            metrics_tracker: MetricsTracker instance for calculating metrics
            success_rate_threshold: Minimum acceptable success rate (0-100)
            resolution_time_multiplier: Multiplier for resolution time spike detection
            
        Raises:
            ValueError: If thresholds are invalid
        """
        if not (0 <= success_rate_threshold <= 100):
            raise ValueError(f"success_rate_threshold must be 0-100, got {success_rate_threshold}")
        if resolution_time_multiplier <= 0:
            raise ValueError(f"resolution_time_multiplier must be positive, got {resolution_time_multiplier}")
        
        self.database = database
        self.notifier = notifier
        self.metrics_tracker = metrics_tracker
        self.success_rate_threshold = success_rate_threshold
        self.resolution_time_multiplier = resolution_time_multiplier
        
        # Store baselines per repository
        self.baselines: Dict[str, MetricBaseline] = {}
        
        # Alert history to prevent spam
        self.recent_alerts: List[MetricAlert] = []
        self.alert_cooldown_minutes = 60  # Don't re-alert same issue within 60 min
        
        # Setup scheduler for periodic checks
        self.scheduler = BackgroundScheduler()
        self.scheduler.add_job(
            self._check_all_metrics,
            'interval',
            minutes=CHECK_INTERVAL_MINUTES,
            id='metric_alerting',
            replace_existing=True
        )
        self.scheduler.start()
        
        logger.info(f"MetricAlertingEngine initialized: success_rate_threshold={success_rate_threshold}%, "
                   f"resolution_time_multiplier={resolution_time_multiplier}x, "
                   f"check_interval={CHECK_INTERVAL_MINUTES}min")

    def calculate_baseline(self, repository: Optional[str] = None, 
                          window_days: int = BASELINE_WINDOW_DAYS) -> MetricBaseline:
        """
        Calculate baseline metrics for comparison.
        
        Args:
            repository: Optional repository to calculate baseline for
            window_days: Number of days to look back for baseline
            
        Returns:
            MetricBaseline with calculated values
        """
        try:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=window_days)
            
            # Get metrics from database
            filters = {}
            if repository:
                filters["repository"] = repository
            
            all_metrics = self.database.get_metrics(filters)
            recent_metrics = [m for m in all_metrics if m.recorded_at > cutoff_date]
            
            if not recent_metrics:
                logger.warning(f"No metrics found for baseline calculation (repo={repository}, window={window_days}d)")
                return MetricBaseline(
                    success_rate=100.0,
                    avg_resolution_time_ms=0.0,
                    total_failures=0,
                    calculated_at=datetime.now(timezone.utc),
                    window_days=window_days
                )
            
            # Calculate success rate
            successful = sum(1 for m in recent_metrics if m.remediation_success)
            success_rate = (successful / len(recent_metrics)) * 100
            
            # Calculate average resolution time
            total_time = sum(m.total_latency_ms for m in recent_metrics)
            avg_resolution_time = total_time / len(recent_metrics)
            
            baseline = MetricBaseline(
                success_rate=success_rate,
                avg_resolution_time_ms=avg_resolution_time,
                total_failures=len(recent_metrics),
                calculated_at=datetime.now(timezone.utc),
                window_days=window_days
            )
            
            # Store baseline
            key = repository or "global"
            self.baselines[key] = baseline
            
            logger.info(f"Baseline calculated for {key}: success_rate={success_rate:.1f}%, "
                       f"avg_resolution_time={avg_resolution_time:.0f}ms, "
                       f"failures={len(recent_metrics)}")
            
            return baseline
            
        except Exception as e:
            logger.error(f"Failed to calculate baseline: {e}")
            raise

    def check_success_rate(self, repository: Optional[str] = None) -> Optional[MetricAlert]:
        """
        Check if success rate is below threshold.
        
        Args:
            repository: Optional repository to check
            
        Returns:
            MetricAlert if threshold breached, None otherwise
        """
        try:
            # Get current success rate (last 24 hours)
            cutoff_date = datetime.now(timezone.utc) - timedelta(hours=24)
            filters = {}
            if repository:
                filters["repository"] = repository
            
            all_metrics = self.database.get_metrics(filters)
            recent_metrics = [m for m in all_metrics if m.recorded_at > cutoff_date]
            
            if not recent_metrics:
                logger.debug(f"No recent metrics for success rate check (repo={repository})")
                return None
            
            successful = sum(1 for m in recent_metrics if m.remediation_success)
            current_rate = (successful / len(recent_metrics)) * 100
            
            if current_rate < self.success_rate_threshold:
                import uuid
                alert = MetricAlert(
                    alert_id=str(uuid.uuid4()),
                    severity=AlertSeverity.CRITICAL,
                    metric_name="success_rate",
                    current_value=current_rate,
                    threshold_value=self.success_rate_threshold,
                    message=f"Remediation success rate dropped to {current_rate:.1f}% "
                           f"(threshold: {self.success_rate_threshold}%) in last 24h. "
                           f"Successful: {successful}/{len(recent_metrics)}",
                    repository=repository
                )
                
                logger.warning(f"SUCCESS RATE ALERT: {alert.message}")
                return alert
            
            logger.debug(f"Success rate OK: {current_rate:.1f}% >= {self.success_rate_threshold}% (repo={repository})")
            return None
            
        except Exception as e:
            logger.error(f"Failed to check success rate: {e}")
            return None

    def check_resolution_time_spike(self, repository: Optional[str] = None) -> Optional[MetricAlert]:
        """
        Check if resolution time has spiked compared to baseline.
        
        Args:
            repository: Optional repository to check
            
        Returns:
            MetricAlert if spike detected, None otherwise
        """
        try:
            # Get or calculate baseline
            key = repository or "global"
            if key not in self.baselines:
                self.calculate_baseline(repository)
            
            baseline = self.baselines.get(key)
            if not baseline or baseline.avg_resolution_time_ms == 0:
                logger.debug(f"No baseline for resolution time check (repo={repository})")
                return None
            
            # Get current resolution time (last 6 hours)
            cutoff_date = datetime.now(timezone.utc) - timedelta(hours=6)
            filters = {}
            if repository:
                filters["repository"] = repository
            
            all_metrics = self.database.get_metrics(filters)
            recent_metrics = [m for m in all_metrics if m.recorded_at > cutoff_date]
            
            if not recent_metrics:
                logger.debug(f"No recent metrics for resolution time check (repo={repository})")
                return None
            
            total_time = sum(m.total_latency_ms for m in recent_metrics)
            current_avg = total_time / len(recent_metrics)
            
            threshold = baseline.avg_resolution_time_ms * self.resolution_time_multiplier
            
            if current_avg > threshold:
                import uuid
                alert = MetricAlert(
                    alert_id=str(uuid.uuid4()),
                    severity=AlertSeverity.CRITICAL,
                    metric_name="resolution_time_spike",
                    current_value=current_avg,
                    threshold_value=threshold,
                    message=f"Resolution time spiked to {current_avg:.0f}ms "
                           f"(baseline: {baseline.avg_resolution_time_ms:.0f}ms, "
                           f"threshold: {threshold:.0f}ms) in last 6h. "
                           f"Spike: {(current_avg / baseline.avg_resolution_time_ms):.1f}x",
                    repository=repository
                )
                
                logger.warning(f"RESOLUTION TIME SPIKE ALERT: {alert.message}")
                return alert
            
            logger.debug(f"Resolution time OK: {current_avg:.0f}ms <= {threshold:.0f}ms (repo={repository})")
            return None
            
        except Exception as e:
            logger.error(f"Failed to check resolution time spike: {e}")
            return None

    def _check_all_metrics(self) -> None:
        """Periodic check of all metrics - called by scheduler"""
        try:
            logger.info("Running periodic metric checks...")
            
            # Check global metrics
            alerts = []
            
            success_rate_alert = self.check_success_rate()
            if success_rate_alert:
                alerts.append(success_rate_alert)
            
            resolution_time_alert = self.check_resolution_time_spike()
            if resolution_time_alert:
                alerts.append(resolution_time_alert)
            
            # Check per-repository metrics
            all_metrics = self.database.get_metrics()
            repositories = set(m.repository for m in all_metrics if m.repository != "unknown")
            
            for repo in repositories:
                repo_success_alert = self.check_success_rate(repository=repo)
                if repo_success_alert:
                    alerts.append(repo_success_alert)
                
                repo_time_alert = self.check_resolution_time_spike(repository=repo)
                if repo_time_alert:
                    alerts.append(repo_time_alert)
            
            # Fire alerts (with cooldown check)
            for alert in alerts:
                if self._should_fire_alert(alert):
                    self._fire_alert(alert)
            
            logger.info(f"Periodic metric check completed: {len(alerts)} alerts generated")
            
        except Exception as e:
            logger.error(f"Error in periodic metric check: {e}")

    def _should_fire_alert(self, alert: MetricAlert) -> bool:
        """
        Check if alert should be fired based on cooldown.
        
        Args:
            alert: Alert to check
            
        Returns:
            True if alert should be fired, False if in cooldown
        """
        cooldown_cutoff = datetime.now(timezone.utc) - timedelta(minutes=self.alert_cooldown_minutes)
        
        # Check if similar alert was fired recently
        for recent_alert in self.recent_alerts:
            if (recent_alert.metric_name == alert.metric_name and
                recent_alert.repository == alert.repository and
                recent_alert.timestamp > cooldown_cutoff):
                logger.debug(f"Alert in cooldown: {alert.metric_name} for {alert.repository}")
                return False
        
        return True

    def _fire_alert(self, alert: MetricAlert) -> None:
        """
        Fire alert by sending notification.
        
        Args:
            alert: Alert to fire
        """
        try:
            # Send critical alert
            self.notifier.send_metric_alert(alert)
            
            # Add to recent alerts
            self.recent_alerts.append(alert)
            
            # Cleanup old alerts (keep last 100)
            if len(self.recent_alerts) > 100:
                self.recent_alerts = self.recent_alerts[-100:]
            
            logger.info(f"Alert fired: {alert.metric_name} - {alert.message}")
            
        except Exception as e:
            logger.error(f"Failed to fire alert: {e}")

    def get_recent_alerts(self, hours: int = 24) -> List[MetricAlert]:
        """
        Get recent alerts.
        
        Args:
            hours: Number of hours to look back
            
        Returns:
            List of recent alerts
        """
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        return [a for a in self.recent_alerts if a.timestamp > cutoff]

    def shutdown(self) -> None:
        """Shutdown the alerting engine and cleanup scheduler"""
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("Metric alerting scheduler stopped")
