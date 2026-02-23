"""Scheduled Health Report Generator"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from apscheduler.schedulers.background import BackgroundScheduler

logger = logging.getLogger(__name__)


@dataclass
class WeeklyHealthReport:
    """Weekly health report"""
    report_id: str
    week_start: datetime
    week_end: datetime
    total_failures: int
    total_remediations: int
    success_rate: float
    avg_fix_time_minutes: float
    top_recurring_failures: List[Dict[str, Any]] = field(default_factory=list)
    riskiest_repositories: List[Dict[str, Any]] = field(default_factory=list)
    ai_confidence_trend: str = ""
    circuit_breakers_triggered: int = 0
    patterns_learned: int = 0
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "report_id": self.report_id,
            "week_start": self.week_start.isoformat(),
            "week_end": self.week_end.isoformat(),
            "total_failures": self.total_failures,
            "total_remediations": self.total_remediations,
            "success_rate": self.success_rate,
            "avg_fix_time_minutes": self.avg_fix_time_minutes,
            "top_recurring_failures": self.top_recurring_failures,
            "riskiest_repositories": self.riskiest_repositories,
            "ai_confidence_trend": self.ai_confidence_trend,
            "circuit_breakers_triggered": self.circuit_breakers_triggered,
            "patterns_learned": self.patterns_learned,
            "generated_at": self.generated_at.isoformat()
        }


class HealthReportGenerator:
    """Generate and send scheduled health reports"""

    def __init__(self, database, metrics_tracker, notifier,
                 circuit_breaker=None, failure_pattern_memory=None):
        """
        Initialize health report generator.
        
        Args:
            database: Database instance
            metrics_tracker: MetricsTracker instance
            notifier: Notifier instance
            circuit_breaker: Optional CircuitBreaker instance
            failure_pattern_memory: Optional FailurePatternMemory instance
            
        Raises:
            ValueError: If required dependencies are None
        """
        if database is None:
            raise ValueError("database cannot be None")
        if metrics_tracker is None:
            raise ValueError("metrics_tracker cannot be None")
        if notifier is None:
            raise ValueError("notifier cannot be None")
        
        self.database = database
        self.metrics_tracker = metrics_tracker
        self.notifier = notifier
        self.circuit_breaker = circuit_breaker
        self.failure_pattern_memory = failure_pattern_memory
        
        # Setup scheduler for Monday mornings
        self.scheduler = BackgroundScheduler()
        self.scheduler.add_job(
            self._generate_and_send_weekly_report,
            'cron',
            day_of_week='mon',
            hour=9,
            minute=0,
            id='weekly_health_report',
            replace_existing=True
        )
        self.scheduler.start()
        
        logger.info("HealthReportGenerator initialized: reports scheduled for Monday 9:00 AM")

    def generate_weekly_report(self, week_offset: int = 0) -> WeeklyHealthReport:
        """
        Generate weekly health report.
        
        Args:
            week_offset: Weeks to offset (0=current week, -1=last week)
            
        Returns:
            WeeklyHealthReport
            
        Raises:
            ValueError: If week_offset is invalid
        """
        if not isinstance(week_offset, int):
            raise ValueError(f"week_offset must be int, got {type(week_offset)}")
        
        try:
            import uuid
            from collections import Counter
            
            # Calculate week boundaries
            today = datetime.now(timezone.utc)
            week_start = today - timedelta(days=today.weekday() + (7 * abs(week_offset)))
            week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
            week_end = week_start + timedelta(days=7)
            
            logger.info(f"Generating health report for week {week_start.date()} to {week_end.date()}")
            
            # Get metrics for the week
            all_metrics = self.database.get_metrics()
            week_metrics = [
                m for m in all_metrics
                if week_start <= m.recorded_at < week_end
            ]
            
            if not week_metrics:
                logger.warning(f"No metrics found for week {week_start.date()}")
                return self._create_empty_report(str(uuid.uuid4()), week_start, week_end)
            
            # Calculate basic stats
            total_failures = len(week_metrics)
            successful = sum(1 for m in week_metrics if m.remediation_success)
            success_rate = (successful / total_failures) * 100
            
            total_time = sum(m.total_latency_ms for m in week_metrics)
            avg_fix_time = (total_time / total_failures) / 60000  # Convert to minutes
            
            # Top recurring failures
            category_counts = Counter(m.category for m in week_metrics)
            top_recurring = [
                {
                    "category": category,
                    "count": count,
                    "percentage": (count / total_failures) * 100
                }
                for category, count in category_counts.most_common(5)
            ]
            
            # Riskiest repositories
            repo_risk = {}
            for metric in week_metrics:
                if metric.repository not in repo_risk:
                    repo_risk[metric.repository] = []
                repo_risk[metric.repository].append(metric.risk_score)
            
            riskiest_repos = [
                {
                    "repository": repo,
                    "avg_risk_score": sum(scores) / len(scores),
                    "failure_count": len(scores)
                }
                for repo, scores in repo_risk.items()
            ]
            riskiest_repos.sort(key=lambda x: x["avg_risk_score"], reverse=True)
            riskiest_repos = riskiest_repos[:5]
            
            # AI confidence trend
            confidence_trend = self._calculate_confidence_trend(week_metrics)
            
            # Circuit breakers triggered
            circuit_breakers_triggered = 0
            if self.circuit_breaker:
                # Would need to track circuit breaker events
                circuit_breakers_triggered = len(self.circuit_breaker.list_open_circuits())
            
            # Patterns learned
            patterns_learned = 0
            if self.failure_pattern_memory:
                stats = self.failure_pattern_memory.get_statistics()
                patterns_learned = stats.get("total_patterns", 0)
            
            report = WeeklyHealthReport(
                report_id=str(uuid.uuid4()),
                week_start=week_start,
                week_end=week_end,
                total_failures=total_failures,
                total_remediations=successful,
                success_rate=success_rate,
                avg_fix_time_minutes=avg_fix_time,
                top_recurring_failures=top_recurring,
                riskiest_repositories=riskiest_repos,
                ai_confidence_trend=confidence_trend,
                circuit_breakers_triggered=circuit_breakers_triggered,
                patterns_learned=patterns_learned
            )
            
            logger.info(f"Generated health report: {total_failures} failures, "
                       f"{success_rate:.1f}% success rate")
            
            return report
            
        except Exception as e:
            logger.error(f"Failed to generate weekly report: {e}")
            raise

    def format_report_for_slack(self, report: WeeklyHealthReport) -> str:
        """
        Format report for Slack/Telegram.
        
        Args:
            report: WeeklyHealthReport
            
        Returns:
            Formatted message string
        """
        try:
            week_str = f"{report.week_start.strftime('%b %d')} - {report.week_end.strftime('%b %d, %Y')}"
            
            message = f"""📊 **Weekly CI/CD Health Report**
Week: {week_str}

**Overview:**
• Total Failures: {report.total_failures}
• Successful Remediations: {report.total_remediations}
• Success Rate: {report.success_rate:.1f}%
• Avg Fix Time: {report.avg_fix_time_minutes:.1f} minutes

**Top 5 Recurring Failures:**
"""
            
            for i, failure in enumerate(report.top_recurring_failures, 1):
                message += f"{i}. {failure['category']}: {failure['count']} occurrences ({failure['percentage']:.1f}%)\n"
            
            message += "\n**Riskiest Repositories:**\n"
            for i, repo in enumerate(report.riskiest_repositories, 1):
                message += f"{i}. {repo['repository']}: Avg Risk {repo['avg_risk_score']:.1f}/10 ({repo['failure_count']} failures)\n"
            
            message += f"\n**AI Performance:**\n"
            message += f"• Confidence Trend: {report.ai_confidence_trend}\n"
            message += f"• Patterns Learned: {report.patterns_learned}\n"
            
            if report.circuit_breakers_triggered > 0:
                message += f"\n⚠️ **Circuit Breakers Triggered:** {report.circuit_breakers_triggered}\n"
            
            message += "\n---\n*Generated automatically every Monday*"
            
            return message
            
        except Exception as e:
            logger.error(f"Failed to format report: {e}")
            return "Error formatting report"

    def _generate_and_send_weekly_report(self) -> None:
        """Generate and send weekly report (called by scheduler)"""
        try:
            logger.info("Generating scheduled weekly health report...")
            
            # Generate report for last week
            report = self.generate_weekly_report(week_offset=-1)
            
            # Format message
            message = self.format_report_for_slack(report)
            
            # Send to Slack/Telegram
            try:
                self.notifier.send_health_report(message)
                logger.info("Weekly health report sent successfully")
            except Exception as e:
                logger.error(f"Failed to send health report: {e}")
            
            # Store report in database
            self.database.store_health_report(report)
            
        except Exception as e:
            logger.error(f"Failed to generate and send weekly report: {e}")

    def _calculate_confidence_trend(self, metrics: List) -> str:
        """
        Calculate AI confidence trend.
        
        Args:
            metrics: List of metrics
            
        Returns:
            Trend description
        """
        try:
            # Get analyses for these metrics
            confidences = []
            for metric in metrics:
                analysis = self.database.get_analysis(metric.failure_id)
                if analysis:
                    confidences.append(analysis.confidence)
            
            if not confidences:
                return "No data"
            
            avg_confidence = sum(confidences) / len(confidences)
            
            # Compare to previous week
            # (Simplified - would need historical comparison)
            if avg_confidence >= 85:
                return f"High ({avg_confidence:.0f}% avg) ✅"
            elif avg_confidence >= 70:
                return f"Good ({avg_confidence:.0f}% avg)"
            else:
                return f"Needs improvement ({avg_confidence:.0f}% avg) ⚠️"
            
        except Exception as e:
            logger.error(f"Failed to calculate confidence trend: {e}")
            return "Unknown"

    def _create_empty_report(self, report_id: str, week_start: datetime,
                            week_end: datetime) -> WeeklyHealthReport:
        """
        Create empty report for weeks with no data.
        
        Args:
            report_id: Report ID
            week_start: Week start date
            week_end: Week end date
            
        Returns:
            Empty WeeklyHealthReport
        """
        return WeeklyHealthReport(
            report_id=report_id,
            week_start=week_start,
            week_end=week_end,
            total_failures=0,
            total_remediations=0,
            success_rate=0.0,
            avg_fix_time_minutes=0.0,
            top_recurring_failures=[],
            riskiest_repositories=[],
            ai_confidence_trend="No data",
            circuit_breakers_triggered=0,
            patterns_learned=0
        )

    def shutdown(self) -> None:
        """Shutdown the health report scheduler"""
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("Health report scheduler stopped")
