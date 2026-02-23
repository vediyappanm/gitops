"""Blast Radius Estimator for analyzing remediation impact"""
import logging
import re
from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


# Constants
HIGH_BLAST_RADIUS_THRESHOLD = 7  # Score >= 7 is high blast radius
MEDIUM_BLAST_RADIUS_THRESHOLD = 4  # Score >= 4 is medium


class ImpactLevel(str, Enum):
    """Impact level classification"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class BlastRadiusAnalysis:
    """Blast radius analysis result"""
    blast_radius_score: int  # 0-10
    impact_level: ImpactLevel
    affected_services: List[str] = field(default_factory=list)
    affected_downstream_repos: List[str] = field(default_factory=list)
    estimated_users_affected: int = 0
    deployment_scope: str = "single_service"  # single_service, multi_service, platform_wide
    reasoning: str = ""
    mitigation_recommendations: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "blast_radius_score": self.blast_radius_score,
            "impact_level": self.impact_level.value,
            "affected_services": self.affected_services,
            "affected_downstream_repos": self.affected_downstream_repos,
            "estimated_users_affected": self.estimated_users_affected,
            "deployment_scope": self.deployment_scope,
            "reasoning": self.reasoning,
            "mitigation_recommendations": self.mitigation_recommendations
        }


class BlastRadiusEstimator:
    """Estimate blast radius of remediations before execution"""

    def __init__(self, github_client, database):
        """
        Initialize blast radius estimator.
        
        Args:
            github_client: GitHub client for repository analysis
            database: Database for historical data
            
        Raises:
            ValueError: If required dependencies are None
        """
        if github_client is None:
            raise ValueError("github_client cannot be None")
        if database is None:
            raise ValueError("database cannot be None")
        
        self.github_client = github_client
        self.database = database
        
        # Critical file patterns that indicate high blast radius
        self.critical_patterns = [
            r'docker-compose\.ya?ml$',
            r'Dockerfile$',
            r'kubernetes/.*\.ya?ml$',
            r'k8s/.*\.ya?ml$',
            r'\.github/workflows/.*\.ya?ml$',
            r'requirements\.txt$',
            r'package\.json$',
            r'go\.mod$',
            r'pom\.xml$',
            r'build\.gradle$',
            r'config/.*\.ya?ml$',
            r'\.env\.production$',
            r'terraform/.*\.tf$',
            r'infrastructure/.*',
        ]
        
        logger.info("BlastRadiusEstimator initialized")

    def estimate_blast_radius(self, repository: str, branch: str, 
                             files_to_modify: List[str],
                             failure_category: str) -> BlastRadiusAnalysis:
        """
        Estimate blast radius of a remediation.
        
        Args:
            repository: Repository name (owner/repo)
            branch: Branch being modified
            files_to_modify: List of files that will be modified
            failure_category: Category of failure being fixed
            
        Returns:
            BlastRadiusAnalysis with estimated impact
            
        Raises:
            ValueError: If inputs are invalid
        """
        if not repository or not isinstance(repository, str):
            raise ValueError(f"repository must be non-empty string, got {type(repository)}")
        if not branch or not isinstance(branch, str):
            raise ValueError(f"branch must be non-empty string, got {type(branch)}")
        if not isinstance(files_to_modify, list):
            raise ValueError(f"files_to_modify must be list, got {type(files_to_modify)}")
        
        try:
            logger.info(f"Estimating blast radius for {repository}#{branch}, "
                       f"{len(files_to_modify)} files to modify")
            
            # Initialize score components
            file_criticality_score = self._analyze_file_criticality(files_to_modify)
            service_impact_score = self._analyze_service_impact(repository, files_to_modify)
            downstream_impact_score = self._analyze_downstream_impact(repository)
            branch_criticality_score = self._analyze_branch_criticality(branch)
            category_risk_score = self._analyze_category_risk(failure_category)
            
            # Calculate weighted blast radius score (0-10)
            blast_radius_score = min(10, int(
                file_criticality_score * 0.3 +
                service_impact_score * 0.25 +
                downstream_impact_score * 0.2 +
                branch_criticality_score * 0.15 +
                category_risk_score * 0.1
            ))
            
            # Determine impact level
            if blast_radius_score >= 9:
                impact_level = ImpactLevel.CRITICAL
            elif blast_radius_score >= HIGH_BLAST_RADIUS_THRESHOLD:
                impact_level = ImpactLevel.HIGH
            elif blast_radius_score >= MEDIUM_BLAST_RADIUS_THRESHOLD:
                impact_level = ImpactLevel.MEDIUM
            else:
                impact_level = ImpactLevel.LOW
            
            # Analyze affected components
            affected_services = self._identify_affected_services(repository, files_to_modify)
            affected_downstream = self._identify_downstream_repos(repository)
            
            # Estimate user impact
            estimated_users = self._estimate_user_impact(
                repository, 
                affected_services, 
                impact_level
            )
            
            # Determine deployment scope
            deployment_scope = self._determine_deployment_scope(
                affected_services,
                affected_downstream,
                files_to_modify
            )
            
            # Generate reasoning
            reasoning = self._generate_reasoning(
                blast_radius_score,
                file_criticality_score,
                service_impact_score,
                downstream_impact_score,
                files_to_modify,
                affected_services
            )
            
            # Generate mitigation recommendations
            recommendations = self._generate_recommendations(
                impact_level,
                deployment_scope,
                affected_services
            )
            
            analysis = BlastRadiusAnalysis(
                blast_radius_score=blast_radius_score,
                impact_level=impact_level,
                affected_services=affected_services,
                affected_downstream_repos=affected_downstream,
                estimated_users_affected=estimated_users,
                deployment_scope=deployment_scope,
                reasoning=reasoning,
                mitigation_recommendations=recommendations
            )
            
            logger.info(f"Blast radius estimated: score={blast_radius_score}, "
                       f"impact={impact_level.value}, services={len(affected_services)}, "
                       f"downstream={len(affected_downstream)}")
            
            return analysis
            
        except Exception as e:
            logger.error(f"Failed to estimate blast radius: {e}")
            raise

    def _analyze_file_criticality(self, files: List[str]) -> float:
        """
        Analyze criticality of files being modified.
        
        Args:
            files: List of file paths
            
        Returns:
            Criticality score (0-10)
        """
        if not files:
            return 0.0
        
        critical_count = 0
        for file_path in files:
            for pattern in self.critical_patterns:
                if re.search(pattern, file_path, re.IGNORECASE):
                    critical_count += 1
                    break
        
        # Score based on percentage of critical files
        critical_ratio = critical_count / len(files)
        score = critical_ratio * 10
        
        logger.debug(f"File criticality: {critical_count}/{len(files)} critical files, score={score:.1f}")
        return score

    def _analyze_service_impact(self, repository: str, files: List[str]) -> float:
        """
        Analyze how many services are affected.
        
        Args:
            repository: Repository name
            files: List of file paths
            
        Returns:
            Service impact score (0-10)
        """
        try:
            # Check for microservices structure
            service_dirs = set()
            for file_path in files:
                parts = file_path.split('/')
                if len(parts) > 1 and parts[0] in ['services', 'apps', 'packages']:
                    service_dirs.add(parts[1])
            
            if not service_dirs:
                # Single service or monolith
                return 3.0
            elif len(service_dirs) == 1:
                # Single service in microservices architecture
                return 5.0
            elif len(service_dirs) <= 3:
                # Multiple services
                return 7.0
            else:
                # Many services affected
                return 9.0
                
        except Exception as e:
            logger.warning(f"Failed to analyze service impact: {e}")
            return 5.0  # Default to medium

    def _analyze_downstream_impact(self, repository: str) -> float:
        """
        Analyze downstream repository dependencies.
        
        Args:
            repository: Repository name
            
        Returns:
            Downstream impact score (0-10)
        """
        try:
            # Check for package.json, setup.py, go.mod etc to see if this is a library
            is_library = self._is_library_repository(repository)
            
            if is_library:
                # Libraries have higher downstream impact
                return 8.0
            else:
                # Application repositories have lower downstream impact
                return 2.0
                
        except Exception as e:
            logger.warning(f"Failed to analyze downstream impact: {e}")
            return 3.0  # Default to low-medium

    def _analyze_branch_criticality(self, branch: str) -> float:
        """
        Analyze criticality of branch being modified.
        
        Args:
            branch: Branch name
            
        Returns:
            Branch criticality score (0-10)
        """
        branch_lower = branch.lower()
        
        # Production branches
        if branch_lower in ['main', 'master', 'production', 'prod']:
            return 10.0
        
        # Staging/release branches
        if any(x in branch_lower for x in ['staging', 'release', 'hotfix']):
            return 7.0
        
        # Development branches
        if any(x in branch_lower for x in ['develop', 'dev', 'integration']):
            return 5.0
        
        # Feature branches (teammate branches)
        return 2.0

    def _analyze_category_risk(self, category: str) -> float:
        """
        Analyze risk based on failure category.
        
        Args:
            category: Failure category
            
        Returns:
            Category risk score (0-10)
        """
        category_lower = category.lower()
        
        high_risk_categories = ['infrastructure', 'config', 'dependency']
        medium_risk_categories = ['timeout', 'build_error']
        low_risk_categories = ['lint_error', 'flaky_test', 'test_failure']
        
        if category_lower in high_risk_categories:
            return 8.0
        elif category_lower in medium_risk_categories:
            return 5.0
        elif category_lower in low_risk_categories:
            return 2.0
        else:
            return 5.0  # Default to medium

    def _identify_affected_services(self, repository: str, files: List[str]) -> List[str]:
        """
        Identify which services are affected by file changes.
        
        Args:
            repository: Repository name
            files: List of file paths
            
        Returns:
            List of affected service names
        """
        services = set()
        
        for file_path in files:
            parts = file_path.split('/')
            
            # Check for microservices structure
            if len(parts) > 1 and parts[0] in ['services', 'apps', 'packages']:
                services.add(parts[1])
            
            # Check for shared/common changes
            if any(x in file_path.lower() for x in ['shared', 'common', 'lib', 'core']):
                services.add('shared-components')
        
        if not services:
            # Extract service name from repository
            repo_name = repository.split('/')[-1]
            services.add(repo_name)
        
        return sorted(list(services))

    def _identify_downstream_repos(self, repository: str) -> List[str]:
        """
        Identify downstream repositories that depend on this one.
        
        Args:
            repository: Repository name
            
        Returns:
            List of downstream repository names
        """
        # In a real implementation, this would query a dependency graph
        # For now, return empty list
        return []

    def _estimate_user_impact(self, repository: str, affected_services: List[str],
                             impact_level: ImpactLevel) -> int:
        """
        Estimate number of users affected.
        
        Args:
            repository: Repository name
            affected_services: List of affected services
            impact_level: Impact level
            
        Returns:
            Estimated number of users affected
        """
        # Base estimate on impact level and number of services
        base_users = {
            ImpactLevel.LOW: 100,
            ImpactLevel.MEDIUM: 1000,
            ImpactLevel.HIGH: 10000,
            ImpactLevel.CRITICAL: 100000
        }
        
        estimate = base_users.get(impact_level, 1000)
        
        # Multiply by number of services
        if len(affected_services) > 1:
            estimate *= len(affected_services)
        
        return estimate

    def _determine_deployment_scope(self, affected_services: List[str],
                                   affected_downstream: List[str],
                                   files: List[str]) -> str:
        """
        Determine deployment scope.
        
        Args:
            affected_services: List of affected services
            affected_downstream: List of downstream repos
            files: List of files being modified
            
        Returns:
            Deployment scope string
        """
        if affected_downstream:
            return "platform_wide"
        elif len(affected_services) > 3:
            return "multi_service"
        else:
            return "single_service"

    def _is_library_repository(self, repository: str) -> bool:
        """
        Check if repository is a library/package.
        
        Args:
            repository: Repository name
            
        Returns:
            True if library, False otherwise
        """
        try:
            # Check for library indicators
            library_files = [
                'setup.py',
                'pyproject.toml',
                'package.json',
                'go.mod',
                'pom.xml',
                'build.gradle'
            ]
            
            for lib_file in library_files:
                try:
                    content = self.github_client.get_file_contents(repository, lib_file)
                    if content:
                        return True
                except Exception:
                    continue
            
            return False
            
        except Exception as e:
            logger.warning(f"Failed to check if library: {e}")
            return False

    def _generate_reasoning(self, total_score: int, file_score: float,
                           service_score: float, downstream_score: float,
                           files: List[str], services: List[str]) -> str:
        """
        Generate human-readable reasoning for blast radius score.
        
        Args:
            total_score: Total blast radius score
            file_score: File criticality score
            service_score: Service impact score
            downstream_score: Downstream impact score
            files: List of files
            services: List of services
            
        Returns:
            Reasoning string
        """
        reasons = []
        
        if file_score >= 7:
            reasons.append(f"Modifying {len(files)} critical infrastructure files")
        elif file_score >= 4:
            reasons.append(f"Modifying {len(files)} files including some critical ones")
        
        if service_score >= 7:
            reasons.append(f"Affects {len(services)} services")
        elif service_score >= 4:
            reasons.append(f"Affects multiple services")
        
        if downstream_score >= 7:
            reasons.append("Repository is a library with downstream dependencies")
        
        if not reasons:
            reasons.append("Limited scope changes to non-critical files")
        
        return ". ".join(reasons) + "."

    def _generate_recommendations(self, impact_level: ImpactLevel,
                                 deployment_scope: str,
                                 services: List[str]) -> List[str]:
        """
        Generate mitigation recommendations.
        
        Args:
            impact_level: Impact level
            deployment_scope: Deployment scope
            services: Affected services
            
        Returns:
            List of recommendations
        """
        recommendations = []
        
        if impact_level in [ImpactLevel.HIGH, ImpactLevel.CRITICAL]:
            recommendations.append("Require manual approval before deployment")
            recommendations.append("Deploy during low-traffic window")
            recommendations.append("Have rollback plan ready")
        
        if deployment_scope == "platform_wide":
            recommendations.append("Coordinate with all affected teams")
            recommendations.append("Stage rollout across environments")
        
        if len(services) > 1:
            recommendations.append(f"Test all {len(services)} affected services")
        
        if impact_level == ImpactLevel.CRITICAL:
            recommendations.append("Consider canary deployment")
            recommendations.append("Monitor metrics closely post-deployment")
        
        if not recommendations:
            recommendations.append("Standard deployment process acceptable")
        
        return recommendations
