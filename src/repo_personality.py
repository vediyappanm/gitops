"""Per-Repository Failure Personality Profiles"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from collections import Counter
import json

logger = logging.getLogger(__name__)


# Constants
LEARNING_WINDOW_DAYS = 30  # Learn from last 30 days
MIN_FAILURES_FOR_PROFILE = 5  # Need at least 5 failures to build profile
FLAKY_TEST_THRESHOLD = 0.3  # 30% of failures are flaky tests
FRIDAY_FAILURE_THRESHOLD = 0.4  # 40% of failures on Fridays


@dataclass
class FailurePattern:
    """Recurring failure pattern"""
    pattern_type: str  # "flaky_test", "friday_spike", "dependency_drift", etc.
    frequency: float  # 0-1, how often this pattern occurs
    description: str
    confidence_adjustment: float  # How much to adjust confidence (-0.2 to +0.2)
    recommended_action: str


@dataclass
class RepositoryPersonality:
    """Personality profile for a repository"""
    repository: str
    total_failures: int
    most_common_category: str
    most_common_day: str
    most_common_hour: int
    flaky_test_rate: float
    avg_resolution_time_minutes: float
    success_rate: float
    patterns: List[FailurePattern] = field(default_factory=list)
    last_updated: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "repository": self.repository,
            "total_failures": self.total_failures,
            "most_common_category": self.most_common_category,
            "most_common_day": self.most_common_day,
            "most_common_hour": self.most_common_hour,
            "flaky_test_rate": self.flaky_test_rate,
            "avg_resolution_time_minutes": self.avg_resolution_time_minutes,
            "success_rate": self.success_rate,
            "patterns": [
                {
                    "pattern_type": p.pattern_type,
                    "frequency": p.frequency,
                    "description": p.description,
                    "confidence_adjustment": p.confidence_adjustment,
                    "recommended_action": p.recommended_action
                }
                for p in self.patterns
            ],
            "last_updated": self.last_updated.isoformat()
        }


class RepositoryPersonalityProfiler:
    """Learn and track per-repository failure patterns"""

    def __init__(self, database):
        """
        Initialize repository personality profiler.
        
        Args:
            database: Database instance
            
        Raises:
            ValueError: If database is None
        """
        if database is None:
            raise ValueError("database cannot be None")
        
        self.database = database
        self.profiles: Dict[str, RepositoryPersonality] = {}
        
        logger.info("RepositoryPersonalityProfiler initialized")

    def learn_repository_personality(self, repository: str, 
                                    force_refresh: bool = False) -> RepositoryPersonality:
        """
        Learn or update personality profile for a repository.
        
        Args:
            repository: Repository name
            force_refresh: Force refresh even if cached
            
        Returns:
            RepositoryPersonality profile
            
        Raises:
            ValueError: If repository is invalid
        """
        if not repository or not isinstance(repository, str):
            raise ValueError(f"repository must be non-empty string, got {type(repository)}")
            
        return self.learn_repository_personality(repository)

    def learn_repository_personality(self, repository: str, 
                                    force_refresh: bool = False) -> RepositoryPersonality:
        """
        Learn or update personality profile for a repository.
        
        Args:
            repository: Repository name
            force_refresh: Force refresh even if cached
            
        Returns:
            RepositoryPersonality profile
            
        Raises:
            ValueError: If repository is invalid
        """
        if not repository or not isinstance(repository, str):
            raise ValueError(f"repository must be non-empty string, got {type(repository)}")
        
        try:
            # Check cache
            if not force_refresh and repository in self.profiles:
                profile = self.profiles[repository]
                # Refresh if older than 1 day
                if (datetime.now(timezone.utc) - profile.last_updated).days < 1:
                    logger.debug(f"Using cached profile for {repository}")
                    return profile
            
            logger.info(f"Learning personality profile for {repository}")
            
            # Get historical data
            cutoff = datetime.now(timezone.utc) - timedelta(days=LEARNING_WINDOW_DAYS)
            all_metrics = self.database.get_metrics({"repository": repository})
            recent_metrics = [m for m in all_metrics if m.recorded_at > cutoff]
            
            if len(recent_metrics) < MIN_FAILURES_FOR_PROFILE:
                logger.warning(f"Insufficient data for {repository}: "
                             f"{len(recent_metrics)} failures (need {MIN_FAILURES_FOR_PROFILE})")
                return self._create_default_profile(repository)
            
            # Analyze patterns
            category_counts = Counter(m.category for m in recent_metrics)
            most_common_category = category_counts.most_common(1)[0][0]
            
            # Analyze temporal patterns
            day_counts = Counter()
            hour_counts = Counter()
            for metric in recent_metrics:
                day_counts[metric.recorded_at.strftime("%A")] += 1
                hour_counts[metric.recorded_at.hour] += 1
            
            most_common_day = day_counts.most_common(1)[0][0] if day_counts else "Unknown"
            most_common_hour = hour_counts.most_common(1)[0][0] if hour_counts else 0
            
            # Calculate flaky test rate
            flaky_count = sum(1 for m in recent_metrics if m.category == "flaky_test")
            flaky_rate = flaky_count / len(recent_metrics)
            
            # Calculate success rate
            successful = sum(1 for m in recent_metrics if m.remediation_success)
            success_rate = successful / len(recent_metrics)
            
            # Calculate avg resolution time
            total_time = sum(m.total_latency_ms for m in recent_metrics)
            avg_time = (total_time / len(recent_metrics)) / 60000  # Convert to minutes
            
            # Detect patterns
            patterns = self._detect_patterns(
                recent_metrics,
                category_counts,
                day_counts,
                hour_counts,
                flaky_rate
            )
            
            # Create profile
            profile = RepositoryPersonality(
                repository=repository,
                total_failures=len(recent_metrics),
                most_common_category=most_common_category,
                most_common_day=most_common_day,
                most_common_hour=most_common_hour,
                flaky_test_rate=flaky_rate,
                avg_resolution_time_minutes=avg_time,
                success_rate=success_rate,
                patterns=patterns,
                last_updated=datetime.now(timezone.utc)
            )
            
            # Cache profile
            self.profiles[repository] = profile
            
            # Store in database
            self.database.store_repository_profile(profile)
            
            logger.info(f"Learned profile for {repository}: "
                       f"{len(patterns)} patterns detected, "
                       f"flaky_rate={flaky_rate:.1%}, "
                       f"success_rate={success_rate:.1%}")
            
            return profile
            
        except Exception as e:
            logger.error(f"Failed to learn repository personality: {e}")
            raise

    def get_adjusted_confidence(self, repository: str, failure_category: str,
                               failure_time: datetime) -> float:
        """
        Get confidence adjustment based on repository personality.
        
        Args:
            repository: Repository name
            failure_category: Category of current failure
            failure_time: When failure occurred
            
        Returns:
            Confidence adjustment (-0.2 to +0.2)
        """
        try:
            # Get or learn profile
            if repository not in self.profiles:
                self.learn_repository_personality(repository)
            
            profile = self.profiles.get(repository)
            if not profile:
                return 0.0  # No adjustment
            
            adjustment = 0.0
            
            # Check for matching patterns
            for pattern in profile.patterns:
                if pattern.pattern_type == "flaky_test_prone" and failure_category == "flaky_test":
                    adjustment += pattern.confidence_adjustment
                    logger.debug(f"Applied flaky test adjustment: {pattern.confidence_adjustment}")
                
                elif pattern.pattern_type == "friday_failures" and failure_time.strftime("%A") == "Friday":
                    adjustment += pattern.confidence_adjustment
                    logger.debug(f"Applied Friday failure adjustment: {pattern.confidence_adjustment}")
                
                elif pattern.pattern_type == "category_specialist" and failure_category == profile.most_common_category:
                    adjustment += pattern.confidence_adjustment
                    logger.debug(f"Applied category specialist adjustment: {pattern.confidence_adjustment}")
            
            # Clamp adjustment
            adjustment = max(-0.2, min(0.2, adjustment))
            
            return adjustment
            
        except Exception as e:
            logger.error(f"Failed to get adjusted confidence: {e}")
            return 0.0

    def get_recommended_actions(self, repository: str, failure_category: str) -> List[str]:
        """
        Get recommended actions based on repository personality.
        
        Args:
            repository: Repository name
            failure_category: Category of current failure
            
        Returns:
            List of recommended actions
        """
        try:
            profile = self.profiles.get(repository)
            if not profile:
                return []
            
            recommendations = []
            
            for pattern in profile.patterns:
                if pattern.pattern_type == "flaky_test_prone" and failure_category == "flaky_test":
                    recommendations.append(pattern.recommended_action)
                
                elif pattern.pattern_type == "friday_failures":
                    recommendations.append(pattern.recommended_action)
                
                elif pattern.pattern_type == "slow_resolution" and profile.avg_resolution_time_minutes > 30:
                    recommendations.append(pattern.recommended_action)
            
            return recommendations
            
        except Exception as e:
            logger.error(f"Failed to get recommended actions: {e}")
            return []

    def _detect_patterns(self, metrics: List, category_counts: Counter,
                        day_counts: Counter, hour_counts: Counter,
                        flaky_rate: float) -> List[FailurePattern]:
        """
        Detect recurring patterns in failure data.
        
        Args:
            metrics: List of metrics
            category_counts: Counter of categories
            day_counts: Counter of days
            hour_counts: Counter of hours
            flaky_rate: Flaky test rate
            
        Returns:
            List of detected patterns
        """
        patterns = []
        
        # Pattern 1: Flaky test prone
        if flaky_rate >= FLAKY_TEST_THRESHOLD:
            patterns.append(FailurePattern(
                pattern_type="flaky_test_prone",
                frequency=flaky_rate,
                description=f"Repository has high flaky test rate ({flaky_rate:.1%})",
                confidence_adjustment=-0.1,  # Lower confidence for flaky tests
                recommended_action="Consider quarantining flaky tests or increasing retry count"
            ))
        
        # Pattern 2: Friday failures
        if day_counts:
            friday_count = day_counts.get("Friday", 0)
            friday_rate = friday_count / len(metrics)
            
            if friday_rate >= FRIDAY_FAILURE_THRESHOLD:
                patterns.append(FailurePattern(
                    pattern_type="friday_failures",
                    frequency=friday_rate,
                    description=f"Repository has spike in Friday failures ({friday_rate:.1%})",
                    confidence_adjustment=-0.05,  # Slightly lower confidence on Fridays
                    recommended_action="Review Friday deployment practices and pre-weekend testing"
                ))
        
        # Pattern 3: Category specialist
        if category_counts:
            most_common = category_counts.most_common(1)[0]
            category_rate = most_common[1] / len(metrics)
            
            if category_rate >= 0.5:  # 50% of failures are same category
                patterns.append(FailurePattern(
                    pattern_type="category_specialist",
                    frequency=category_rate,
                    description=f"Repository primarily fails with {most_common[0]} ({category_rate:.1%})",
                    confidence_adjustment=+0.1,  # Higher confidence for known category
                    recommended_action=f"Focus on preventing {most_common[0]} failures"
                ))
        
        # Pattern 4: Slow resolution
        total_time = sum(m.total_latency_ms for m in metrics)
        avg_time_minutes = (total_time / len(metrics)) / 60000
        
        if avg_time_minutes > 30:  # Slower than 30 minutes
            patterns.append(FailurePattern(
                pattern_type="slow_resolution",
                frequency=1.0,
                description=f"Repository has slow avg resolution time ({avg_time_minutes:.1f} min)",
                confidence_adjustment=0.0,
                recommended_action="Investigate why remediations take longer than average"
            ))
        
        # Pattern 5: Time-of-day pattern
        if hour_counts:
            peak_hour = hour_counts.most_common(1)[0]
            peak_rate = peak_hour[1] / len(metrics)
            
            if peak_rate >= 0.3:  # 30% of failures at same hour
                patterns.append(FailurePattern(
                    pattern_type="time_of_day_pattern",
                    frequency=peak_rate,
                    description=f"Repository has failure spike at {peak_hour[0]}:00 ({peak_rate:.1%})",
                    confidence_adjustment=0.0,
                    recommended_action=f"Investigate what happens around {peak_hour[0]}:00 (deployments, cron jobs?)"
                ))
        
        return patterns

    def _create_default_profile(self, repository: str) -> RepositoryPersonality:
        """
        Create default profile for repository with insufficient data.
        
        Args:
            repository: Repository name
            
        Returns:
            Default RepositoryPersonality
        """
        return RepositoryPersonality(
            repository=repository,
            total_failures=0,
            most_common_category="unknown",
            most_common_day="Unknown",
            most_common_hour=0,
            flaky_test_rate=0.0,
            avg_resolution_time_minutes=0.0,
            success_rate=0.0,
            patterns=[],
            last_updated=datetime.now(timezone.utc)
        )

    def get_all_profiles(self) -> List[RepositoryPersonality]:
        """
        Get all repository profiles.
        
        Returns:
            List of all profiles
        """
        return list(self.profiles.values())

    def refresh_all_profiles(self) -> int:
        """
        Refresh all repository profiles.
        
        Returns:
            Number of profiles refreshed
        """
        try:
            # Get all repositories
            all_metrics = self.database.get_metrics()
            repositories = set(m.repository for m in all_metrics if m.repository != "unknown")
            
            refreshed = 0
            for repo in repositories:
                try:
                    self.learn_repository_personality(repo, force_refresh=True)
                    refreshed += 1
                except Exception as e:
                    logger.error(f"Failed to refresh profile for {repo}: {e}")
            
            logger.info(f"Refreshed {refreshed} repository profiles")
            return refreshed
            
        except Exception as e:
            logger.error(f"Failed to refresh all profiles: {e}")
            return 0
