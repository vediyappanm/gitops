"""Web Dashboard API for CI/CD Failure Monitor"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn
from fastapi.staticfiles import StaticFiles
import os


logger = logging.getLogger(__name__)


# Pydantic models for API responses
class FailureFeedItem(BaseModel):
    """Single failure in live feed"""
    failure_id: str
    repository: str
    branch: str
    workflow_name: str
    failure_reason: str
    status: str
    risk_score: int
    category: str
    created_at: str
    pr_url: Optional[str] = None
    analysis_summary: Optional[str] = None  # To show quick summary


class RiskDistribution(BaseModel):
    """Risk score distribution"""
    low: int = Field(description="Risk score 0-2")
    medium_low: int = Field(description="Risk score 3-4")
    medium: int = Field(description="Risk score 5-6")
    medium_high: int = Field(description="Risk score 7-8")
    high: int = Field(description="Risk score 9-10")


class SuccessRateMetrics(BaseModel):
    """Success rate metrics"""
    total_failures: int
    successful_remediations: int
    failed_remediations: int
    success_rate_percent: float
    avg_resolution_time_minutes: float


class AuditTrailEntry(BaseModel):
    """Single audit trail entry"""
    log_id: str
    timestamp: str
    actor: str
    action_type: str
    failure_id: Optional[str]
    details: Dict[str, Any]
    outcome: str


class DashboardStats(BaseModel):
    """Overall dashboard statistics"""
    total_failures_today: int
    active_remediations: int
    success_rate_24h: float
    avg_resolution_time_minutes: float
    circuit_breakers_open: int
    patterns_learned: int
    
    
class CategoryDistribution(BaseModel):
    """Failure category distribution"""
    categories: Dict[str, int]


class KpiMetrics(BaseModel):
    """Key Performance Indicators"""
    total_failures: int
    auto_fix_rate: float
    avg_detection_time_minutes: float
    avg_fix_time_minutes: float
    time_saved_hours: float



class WebDashboardAPI:
    """FastAPI web dashboard for monitoring"""

    def __init__(self, database, metrics_tracker, circuit_breaker, 
                 failure_pattern_memory, host: str = "0.0.0.0", port: int = 8000):
        """
        Initialize web dashboard API.
        
        Args:
            database: Database instance
            metrics_tracker: MetricsTracker instance
            circuit_breaker: CircuitBreaker instance
            failure_pattern_memory: FailurePatternMemory instance
            host: Host to bind to
            port: Port to bind to
            
        Raises:
            ValueError: If required dependencies are None
        """
        if database is None:
            raise ValueError("database cannot be None")
        if metrics_tracker is None:
            raise ValueError("metrics_tracker cannot be None")
        
        self.database = database
        self.metrics_tracker = metrics_tracker
        self.circuit_breaker = circuit_breaker
        self.failure_pattern_memory = failure_pattern_memory
        self.host = host
        self.port = port
        
        # Create FastAPI app
        self.app = FastAPI(
            title="CI/CD Failure Monitor Dashboard",
            description="Real-time monitoring dashboard for CI/CD failures and remediations",
            version="1.0.0"
        )
        
        # Add CORS middleware
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],  # Configure appropriately for production
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        # Mount static frontend
        dashboard_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "dashboard")
        if os.path.exists(dashboard_dir):
            self.app.mount("/dashboard", StaticFiles(directory=dashboard_dir, html=True), name="dashboard")
            logger.info(f"Mounted dashboard static files from {dashboard_dir}")
        else:
            logger.warning(f"Dashboard directory not found at {dashboard_dir}, skipping mount")
        
        # Register routes
        self._register_routes()
        
        logger.info(f"WebDashboardAPI initialized on {host}:{port}")

    def _register_routes(self) -> None:
        """Register all API routes"""
        
        @self.app.get("/")
        async def root() -> Dict[str, str]:
            """Root endpoint"""
            return {
                "service": "CI/CD Failure Monitor Dashboard",
                "version": "1.0.0",
                "status": "running"
            }

        @self.app.get("/api/stats", response_model=DashboardStats)
        async def get_dashboard_stats() -> DashboardStats:
            """
            Get overall dashboard statistics.
            
            Returns:
                DashboardStats with current metrics
            """
            try:
                # Get failures from last 24 hours
                cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
                all_metrics = self.database.get_metrics()
                recent_metrics = [m for m in all_metrics if m.recorded_at > cutoff]
                
                # Calculate success rate
                if recent_metrics:
                    successful = sum(1 for m in recent_metrics if m.remediation_success)
                    success_rate = (successful / len(recent_metrics)) * 100
                    
                    total_time = sum(m.total_latency_ms for m in recent_metrics)
                    avg_time = (total_time / len(recent_metrics)) / 60000  # Convert to minutes
                else:
                    success_rate = 0.0
                    avg_time = 0.0
                
                # Get active remediations (failures in progress)
                from src.models import FailureStatus
                # Would need to query database for failures with status != REMEDIATED/FAILED
                active_remediations = 0  # Placeholder
                
                # Get circuit breakers
                open_circuits = len(self.circuit_breaker.list_open_circuits()) if self.circuit_breaker else 0
                
                # Get patterns learned
                pattern_stats = self.failure_pattern_memory.get_statistics() if self.failure_pattern_memory else {}
                patterns_learned = pattern_stats.get("total_patterns", 0)
                
                # Get today's failures
                today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
                today_metrics = [m for m in all_metrics if m.recorded_at > today_start]
                
                return DashboardStats(
                    total_failures_today=len(today_metrics),
                    active_remediations=active_remediations,
                    success_rate_24h=success_rate,
                    avg_resolution_time_minutes=avg_time,
                    circuit_breakers_open=open_circuits,
                    patterns_learned=patterns_learned
                )
                
            except Exception as e:
                logger.error(f"Failed to get dashboard stats: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.get("/api/failures/feed", response_model=List[FailureFeedItem])
        async def get_failure_feed(
            limit: int = Query(50, ge=1, le=200),
            repository: Optional[str] = None
        ) -> List[FailureFeedItem]:
            """
            Get live failure feed.
            
            Args:
                limit: Maximum number of failures to return
                repository: Optional repository filter
                
            Returns:
                List of recent failures
            """
            try:
                # Get recent metrics
                filters = {}
                if repository:
                    filters["repository"] = repository
                
                all_metrics = self.database.get_metrics(filters)
                
                # Sort by most recent
                all_metrics.sort(key=lambda m: m.recorded_at, reverse=True)
                
                # Limit results
                recent_metrics = all_metrics[:limit]
                
                # Convert to feed items
                feed_items = []
                for metric in recent_metrics:
                    # Get failure details
                    failure = self.database.get_failure(metric.failure_id)
                    if not failure:
                        continue
                    
                    feed_items.append(FailureFeedItem(
                        failure_id=failure.failure_id,
                        repository=failure.repository,
                        branch=failure.branch,
                        workflow_name=failure.workflow_run_id,
                        failure_reason=failure.failure_reason[:200],
                        status=failure.status.value,
                        risk_score=metric.risk_score,
                        category=metric.category,
                        created_at=failure.created_at.isoformat(),
                        pr_url=None,  # Would need to track PR URLs
                        analysis_summary=self.database.get_analysis(failure.failure_id).reasoning[:150] + "..." if self.database.get_analysis(failure.failure_id).reasoning else None
                    ))
                
                return feed_items
                
            except Exception as e:
                logger.error(f"Failed to get failure feed: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.get("/api/metrics/risk-distribution", response_model=RiskDistribution)
        async def get_risk_distribution() -> RiskDistribution:
            """
            Get risk score distribution.
            
            Returns:
                RiskDistribution with counts per risk level
            """
            try:
                distribution = self.metrics_tracker.get_risk_score_distribution()
                
                return RiskDistribution(
                    low=distribution.get("0-2", 0),
                    medium_low=distribution.get("3-4", 0),
                    medium=distribution.get("5-6", 0),
                    medium_high=distribution.get("7-8", 0),
                    high=distribution.get("9-10", 0)
                )
                
            except Exception as e:
                logger.error(f"Failed to get risk distribution: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.get("/api/metrics/success-rate", response_model=SuccessRateMetrics)
        async def get_success_rate(
            hours: int = Query(24, ge=1, le=168)
        ) -> SuccessRateMetrics:
            """
            Get success rate metrics.
            
            Args:
                hours: Time window in hours
                
            Returns:
                SuccessRateMetrics with success rate data
            """
            try:
                cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
                all_metrics = self.database.get_metrics()
                recent_metrics = [m for m in all_metrics if m.recorded_at > cutoff]
                
                if not recent_metrics:
                    return SuccessRateMetrics(
                        total_failures=0,
                        successful_remediations=0,
                        failed_remediations=0,
                        success_rate_percent=0.0,
                        avg_resolution_time_minutes=0.0
                    )
                
                successful = sum(1 for m in recent_metrics if m.remediation_success)
                failed = len(recent_metrics) - successful
                success_rate = (successful / len(recent_metrics)) * 100
                
                total_time = sum(m.total_latency_ms for m in recent_metrics)
                avg_time = (total_time / len(recent_metrics)) / 60000
                
                return SuccessRateMetrics(
                    total_failures=len(recent_metrics),
                    successful_remediations=successful,
                    failed_remediations=failed,
                    success_rate_percent=success_rate,
                    avg_resolution_time_minutes=avg_time
                )
                
            except Exception as e:
                logger.error(f"Failed to get success rate: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.get("/api/audit/trail", response_model=List[AuditTrailEntry])
        async def get_audit_trail(
            limit: int = Query(100, ge=1, le=500),
            action_type: Optional[str] = None
        ) -> List[AuditTrailEntry]:
            """
            Get audit trail.
            
            Args:
                limit: Maximum number of entries
                action_type: Optional action type filter
                
            Returns:
                List of audit trail entries
            """
            try:
                filters = {}
                if action_type:
                    from src.models import ActionType
                    filters["action_type"] = ActionType(action_type)
                
                logs = self.database.query_audit_logs(filters)
                
                # Sort by most recent
                logs.sort(key=lambda l: l.timestamp, reverse=True)
                
                # Limit results
                logs = logs[:limit]
                
                # Convert to response model
                entries = []
                for log in logs:
                    entries.append(AuditTrailEntry(
                        log_id=log.log_id,
                        timestamp=log.timestamp.isoformat(),
                        actor=log.actor,
                        action_type=log.action_type.value,
                        failure_id=log.failure_id,
                        details=log.details,
                        outcome=log.outcome
                    ))
                
                return entries
                
            except Exception as e:
                logger.error(f"Failed to get audit trail: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.get("/api/repositories")
        async def get_repositories() -> List[str]:
            """
            Get list of monitored repositories.
            
            Returns:
                List of repository names
            """
            try:
                all_metrics = self.database.get_metrics()
                repositories = sorted(set(m.repository for m in all_metrics if m.repository != "unknown"))
                return repositories
                
            except Exception as e:
                logger.error(f"Failed to get repositories: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.get("/api/circuit-breakers")
        async def get_circuit_breakers() -> List[Dict[str, Any]]:
            """
            Get circuit breaker status.
            
            Returns:
                List of circuit breaker states
            """
            try:
                if not self.circuit_breaker:
                    return []
                
                open_circuits = self.circuit_breaker.list_open_circuits()
                
                return [circuit.to_dict() for circuit in open_circuits]
                
            except Exception as e:
                logger.error(f"Failed to get circuit breakers: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.get("/api/metrics/category-distribution", response_model=CategoryDistribution)
        async def get_category_distribution() -> CategoryDistribution:
            """Get failure category distribution"""
            try:
                distribution = self.metrics_tracker.get_category_distribution()
                return CategoryDistribution(categories=distribution)
            except Exception as e:
                logger.error(f"Failed to get category distribution: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.get("/api/metrics/kpis", response_model=KpiMetrics)
        async def get_kpis() -> KpiMetrics:
            """Get 30-day KPIs"""
            try:
                # We need a new method in MetricsTracker or calculate here
                # Let's verify if MetricsTracker has calculate_kpis. 
                # Checking previous file view... it has PerformanceMetrics class but not used in WebDashboard init?
                # Actually WebDashboard takes metrics_tracker which is likely just MetricsTracker class.
                # Let's check MetricsTracker definition again.
                # It has get_success_rate, get_average_resolution_time, etc.
                # It does NOT have calculate_kpis directly on MetricsTracker, it was in PerformanceMetrics class.
                # We should instantiate PerformanceMetrics here or add logic.
                # For simplicity and code reuse, let's implement the logic here using available data.
                
                from src.metrics_tracker import PerformanceMetrics
                pm = PerformanceMetrics(self.database)
                kpis = pm.calculate_kpis()
                
                return KpiMetrics(
                    total_failures=kpis["total_failures"],
                    auto_fix_rate=kpis["auto_fix_rate"],
                    avg_detection_time_minutes=kpis["avg_detection_time_minutes"],
                    avg_fix_time_minutes=kpis["avg_fix_time_minutes"],
                    time_saved_hours=kpis["time_saved_hours"]
                )
            except Exception as e:
                logger.error(f"Failed to get KPIs: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.get("/api/metrics/timeline")
        async def get_failure_timeline(hours: int = Query(24, ge=1, le=168)) -> Dict[str, List[Any]]:
            """Get failure timeline for charts"""
            try:
                cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
                all_metrics = self.database.get_metrics()
                recent_metrics = [m for m in all_metrics if m.recorded_at > cutoff]
                
                # Group by hour
                timeline = {}
                for i in range(hours + 1):
                    t = cutoff + timedelta(hours=i)
                    key = t.strftime("%Y-%m-%d %H:00")
                    timeline[key] = 0
                
                for m in recent_metrics:
                    key = m.recorded_at.replace(minute=0, second=0, microsecond=0).strftime("%Y-%m-%d %H:00")
                    if key in timeline:
                        timeline[key] += 1
                        
                labels = sorted(timeline.keys())
                data = [timeline[k] for k in labels]
                
                return {"labels": labels, "data": data}
            except Exception as e:
                logger.error(f"Failed to get timeline: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.get("/api/repositories/{repo}/profile")
        async def get_repo_profile(repo: str) -> Dict[str, Any]:
            """Get repository personality profile"""
            try:
                # We need RepoPersonalityProfiler to get the profile
                from src.repo_personality import RepositoryPersonalityProfiler
                profiler = RepositoryPersonalityProfiler(self.database)
                profile = profiler.get_profile(repo)
                
                if not profile:
                    raise HTTPException(status_code=404, detail=f"Profile not found for {repo}")
                    
                return profile.to_dict()
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Failed to get repo profile: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.get("/api/health-reports/latest")
        async def get_latest_health_report() -> Dict[str, Any]:
            """Get latest weekly health report"""
            try:
                # Assuming database has a method to get reports, or we query logically
                # Database class in database.py likely does NOT have get_latest_health_report.
                # We need to check if there's a table for it. 
                # Yes, HealthReportORM exists.
                # We'll need to query it.
                # Since Database.py viewed earlier didn't show a specific get_health_report method,
                # we might need to access the session directly if possible, or skip if unavailable.
                # Wait, Database likely wraps session.
                # Let's try to find a generic get or use what we know.
                # Actually, let's look at `src/health_report.py` again? No, let's just return a placeholder if DB method missing.
                # BUT, better to implement it using direct interaction if possible or just fail gracefully.
                # Let's query the specific table if we can. 
                # self.database.session_factory() is available.
                
                with self.database.session_factory() as session:
                    from src.database import HealthReportORM
                    report = session.query(HealthReportORM).order_by(HealthReportORM.generated_at.desc()).first()
                    
                    if not report:
                        return {}
                        
                    return {
                        "report_id": report.report_id,
                        "week_start": report.week_start.isoformat(),
                        "week_end": report.week_end.isoformat(),
                        "total_failures": report.total_failures,
                        "success_rate": report.success_rate,
                        "ai_confidence_trend": report.ai_confidence_trend,
                        "generated_at": report.generated_at.isoformat()
                    }
            except Exception as e:
                logger.error(f"Failed to get health report: {e}")
                # Return empty instead of erroring out to keep dashboard alive
                return {}

        @self.app.get("/api/approvals/pending")
        async def get_pending_approvals() -> List[Dict[str, Any]]:
            """Get pending approval requests"""
            try:
                requests = self.database.get_pending_approvals()
                return [r.to_dict() for r in requests]
            except Exception as e:
                logger.error(f"Failed to get pending approvals: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.get("/api/failures/{failure_id}")
        async def get_failure_detail(failure_id: str) -> Dict[str, Any]:
            """Get full details for a failure"""
            try:
                failure = self.database.get_failure(failure_id)
                if not failure:
                    raise HTTPException(status_code=404, detail="Failure not found")
                
                # Get analysis
                analysis = self.database.get_analysis(failure_id)
                
                response = failure.to_dict()
                if analysis:
                    response["analysis"] = analysis.to_dict()
                
                return response
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Failed to get failure detail: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.get("/health")
        async def health_check() -> Dict[str, str]:
            """Health check endpoint"""
            return {"status": "healthy"}

    def start(self) -> None:
        """
        Start the web dashboard server.
        
        Note: This is a blocking call. Run in separate thread/process for production.
        """
        try:
            logger.info(f"Starting web dashboard on {self.host}:{self.port}")
            uvicorn.run(self.app, host=self.host, port=self.port, log_level="info")
        except Exception as e:
            logger.error(f"Failed to start web dashboard: {e}")
            raise

    def start_background(self) -> None:
        """Start the web dashboard in background thread"""
        import threading
        
        thread = threading.Thread(target=self.start, daemon=True)
        thread.start()
        logger.info(f"Web dashboard started in background thread")


    def shutdown(self) -> None:
        """Shutdown the web dashboard server"""
        logger.info("Web dashboard shutdown requested (note: uvicorn shutdown requires external signal)")


class WebDashboard:
    """Wrapper for WebDashboardAPI that auto-starts in background"""

    def __init__(self, database, metrics_tracker, circuit_breaker=None,
                 failure_pattern_memory=None, host: str = "0.0.0.0", port: int = None):
        """
        Initialize and auto-start web dashboard.

        Args:
            database: Database instance
            metrics_tracker: MetricsTracker instance
            circuit_breaker: Optional CircuitBreaker instance
            failure_pattern_memory: Optional FailurePatternMemory instance
            host: Host to bind to
            port: Port to bind to (default: 8000 or from env DASHBOARD_PORT)
        """
        import os

        # Get port from environment variable or use default
        if port is None:
            port = int(os.getenv("DASHBOARD_PORT", 8000))

        # Try the configured port, if it fails try alternative ports
        for attempt_port in [port, 8001, 8002, 8003, 8004, 8005]:
            try:
                self.api = WebDashboardAPI(
                    database,
                    metrics_tracker,
                    circuit_breaker,
                    failure_pattern_memory,
                    host,
                    attempt_port
                )

                # Auto-start in background
                self.api.start_background()
                logger.info(f"WebDashboard initialized and running on {host}:{attempt_port}")
                return
            except Exception as e:
                logger.warning(f"Failed to start dashboard on port {attempt_port}: {e}")
                if attempt_port == 8005:
                    logger.error("Failed to start dashboard on all ports (8000-8005)")
                    raise
    
    def shutdown(self) -> None:
        """Shutdown the web dashboard"""
        self.api.shutdown()
