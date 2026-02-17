"""Metrics Tracker component for collecting system metrics"""
import logging
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from src.models import MetricsRecord
from src.database import Database

logger = logging.getLogger(__name__)


class MetricsTracker:
    """Collect and track system metrics"""

    def __init__(self, database: Database):
        """Initialize metrics tracker"""
        self.database = database

    def record_detection_time(self, failure_id: str, detection_latency_ms: int) -> str:
        """Record time to detect failure"""
        metric_id = str(uuid.uuid4())
        
        metrics = MetricsRecord(
            metric_id=metric_id,
            failure_id=failure_id,
            detection_latency_ms=detection_latency_ms,
            analysis_latency_ms=0,
            remediation_latency_ms=0,
            total_latency_ms=detection_latency_ms,
            remediation_success=False,
            category="unknown",
            repository="unknown",
            risk_score=0
        )
        
        self.database.store_metrics(metrics)
        logger.debug(f"Recorded detection time: {detection_latency_ms}ms")
        
        return metric_id

    def record_analysis_time(self, failure_id: str, analysis_latency_ms: int) -> None:
        """Record time to analyze"""
        metrics = self.database.get_metrics({"failure_id": failure_id})
        if metrics:
            metrics[0].analysis_latency_ms = analysis_latency_ms
            metrics[0].total_latency_ms += analysis_latency_ms
            self.database.store_metrics(metrics[0])
            logger.debug(f"Recorded analysis time: {analysis_latency_ms}ms")

    def record_remediation_time(self, failure_id: str, remediation_latency_ms: int) -> None:
        """Record time to remediate"""
        metrics = self.database.get_metrics({"failure_id": failure_id})
        if metrics:
            metrics[0].remediation_latency_ms = remediation_latency_ms
            metrics[0].total_latency_ms += remediation_latency_ms
            self.database.store_metrics(metrics[0])
            logger.debug(f"Recorded remediation time: {remediation_latency_ms}ms")

    def record_remediation_result(self, failure_id: str, success: bool, category: str, 
                                 repository: str, risk_score: int) -> None:
        """Record remediation success/failure"""
        metrics = self.database.get_metrics({"failure_id": failure_id})
        if metrics:
            metrics[0].remediation_success = success
            metrics[0].category = category
            metrics[0].repository = repository
            metrics[0].risk_score = risk_score
            self.database.store_metrics(metrics[0])
            logger.debug(f"Recorded remediation result: success={success}")

    def get_success_rate(self, repository: Optional[str] = None, 
                        category: Optional[str] = None) -> float:
        """Calculate remediation success rate"""
        filters = {}
        if repository:
            filters["repository"] = repository
        if category:
            filters["category"] = category
        
        metrics = self.database.get_metrics(filters)
        
        if not metrics:
            return 0.0
        
        successful = sum(1 for m in metrics if m.remediation_success)
        return (successful / len(metrics)) * 100

    def get_average_resolution_time(self, repository: Optional[str] = None) -> float:
        """Calculate average time to resolution"""
        filters = {}
        if repository:
            filters["repository"] = repository
        
        metrics = self.database.get_metrics(filters)
        
        if not metrics:
            return 0.0
        
        total_time = sum(m.total_latency_ms for m in metrics)
        return total_time / len(metrics)

    def get_risk_score_distribution(self) -> Dict[str, int]:
        """Get distribution of risk scores"""
        metrics = self.database.get_metrics()
        
        distribution = {
            "0-2": 0,
            "3-4": 0,
            "5-6": 0,
            "7-8": 0,
            "9-10": 0
        }
        
        for metric in metrics:
            if metric.risk_score <= 2:
                distribution["0-2"] += 1
            elif metric.risk_score <= 4:
                distribution["3-4"] += 1
            elif metric.risk_score <= 6:
                distribution["5-6"] += 1
            elif metric.risk_score <= 8:
                distribution["7-8"] += 1
            else:
                distribution["9-10"] += 1
        
        return distribution

    def get_category_distribution(self) -> Dict[str, int]:
        """Get distribution of failure categories"""
        metrics = self.database.get_metrics()
        
        distribution = {}
        for metric in metrics:
            distribution[metric.category] = distribution.get(metric.category, 0) + 1
        
        return distribution
class PerformanceMetrics:
    """Calculate high-level performance metrics and KPIs"""

    def __init__(self, database: Database):
        self.database = database

    def calculate_kpis(self) -> Dict[str, Any]:
        """Calculate key performance indicators for the last 30 days"""
        last_30_days = datetime.utcnow() - timedelta(days=30)
        
        metrics = self.database.get_metrics()
        recent_metrics = [m for m in metrics if m.recorded_at > last_30_days]
        
        if not recent_metrics:
            return {
                "total_failures": 0,
                "auto_fix_rate": 0,
                "avg_detection_time_minutes": 0,
                "avg_fix_time_minutes": 0,
                "time_saved_hours": 0
            }
            
        total_failures = len(recent_metrics)
        auto_fixed = sum(1 for m in recent_metrics if m.remediation_success)
        
        # Average Detection Time (ms to minutes)
        avg_det_ms = sum(m.detection_latency_ms for m in recent_metrics) / total_failures
        # Average Fix Time (Time from detection to PR completion, ms to minutes)
        avg_fix_ms = sum(m.remediation_latency_ms for m in recent_metrics if m.remediation_latency_ms > 0)
        fix_count = sum(1 for m in recent_metrics if m.remediation_latency_ms > 0)
        avg_fix_val = (avg_fix_ms / fix_count) if fix_count > 0 else 0

        return {
            "total_failures": total_failures,
            "auto_fix_rate": (auto_fixed / total_failures) if total_failures else 0,
            "avg_detection_time_minutes": round(avg_det_ms / 60000, 2),
            "avg_fix_time_minutes": round(avg_fix_val / 60000, 2),
            "time_saved_hours": round((auto_fixed * 30) / 60, 2)  # Est 30 min saved per auto-fix
        }


class ClassificationFeedback:
    """Handle and analyze classification feedback"""

    def __init__(self, database: Database):
        self.database = database

    def record_feedback(self, failure_id: str, predicted: str, actual: str):
        """Record when classification was wrong"""
        from src.models import Feedback
        feedback = Feedback(
            failure_id=failure_id,
            predicted_category=predicted,
            actual_category=actual
        )
        self.database.store_feedback(feedback)
        
    def analyze_patterns(self) -> Dict[str, int]:
        """Find patterns in misclassifications"""
        feedbacks = self.database.get_feedback()
        
        patterns = {}
        for f in feedbacks:
            key = f"{f.predicted_category} -> {f.actual_category}"
            patterns[key] = patterns.get(key, 0) + 1
        
        return patterns
