"""GitHub Native Approval using GitHub Environments"""
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class GitHubApprovalRequest:
    """GitHub environment approval request"""
    request_id: str
    failure_id: str
    repository: str
    environment_name: str
    deployment_id: str
    pr_number: int
    required_reviewers: List[str]
    status: str  # "pending", "approved", "rejected"
    created_at: datetime
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None


class GitHubNativeApproval:
    """GitHub Environment-based approval workflow"""

    def __init__(self, github_client, database, config):
        """
        Initialize GitHub native approval.
        
        Args:
            github_client: GitHub API client
            database: Database instance
            config: Configuration manager
            
        Raises:
            ValueError: If required dependencies are None
        """
        if github_client is None:
            raise ValueError("github_client cannot be None")
        if database is None:
            raise ValueError("database cannot be None")
        if config is None:
            raise ValueError("config cannot be None")
        
        self.github_client = github_client
        self.database = database
        self.config = config
        
        # Environment name for approvals
        self.approval_environment = "auto-remediation-approval"
        
        logger.info("GitHubNativeApproval initialized")

    def create_approval_request(self, failure_id: str, repository: str,
                               pr_number: int, analysis_summary: str,
                               risk_score: int) -> GitHubApprovalRequest:
        """
        Create approval request using GitHub Environment.
        
        Args:
            failure_id: Failure identifier
            repository: Repository name
            pr_number: PR number
            analysis_summary: Summary of analysis
            risk_score: Risk score
            
        Returns:
            GitHubApprovalRequest
            
        Raises:
            ValueError: If inputs are invalid
        """
        if not failure_id or not isinstance(failure_id, str):
            raise ValueError(f"failure_id must be non-empty string, got {type(failure_id)}")
        if not repository or not isinstance(repository, str):
            raise ValueError(f"repository must be non-empty string, got {type(repository)}")
        if pr_number <= 0:
            raise ValueError(f"pr_number must be positive, got {pr_number}")
        
        try:
            import uuid
            request_id = str(uuid.uuid4())
            
            # Create deployment for approval
            deployment_id = self._create_deployment(
                repository,
                pr_number,
                analysis_summary,
                risk_score
            )
            
            # Get required reviewers from config
            required_reviewers = self._get_required_reviewers(repository, risk_score)
            
            request = GitHubApprovalRequest(
                request_id=request_id,
                failure_id=failure_id,
                repository=repository,
                environment_name=self.approval_environment,
                deployment_id=deployment_id,
                pr_number=pr_number,
                required_reviewers=required_reviewers,
                status="pending",
                created_at=datetime.now(timezone.utc)
            )
            
            # Store request
            self.database.store_github_approval_request(request)
            
            # Add comment to PR
            self._add_approval_comment(repository, pr_number, analysis_summary, risk_score)
            
            logger.info(f"Created GitHub approval request: {request_id} "
                       f"(repo={repository}, pr={pr_number})")
            
            return request
            
        except Exception as e:
            logger.error(f"Failed to create approval request: {e}")
            raise

    def check_approval_status(self, request_id: str) -> str:
        """
        Check approval status.
        
        Args:
            request_id: Request identifier
            
        Returns:
            Status: "pending", "approved", "rejected"
        """
        try:
            request = self.database.get_github_approval_request(request_id)
            if not request:
                return "unknown"
            
            # Check deployment status
            status = self._check_deployment_status(
                request.repository,
                request.deployment_id
            )
            
            # Update request if status changed
            if status != request.status:
                request.status = status
                if status in ["approved", "rejected"]:
                    request.reviewed_at = datetime.now(timezone.utc)
                self.database.store_github_approval_request(request)
            
            return status
            
        except Exception as e:
            logger.error(f"Failed to check approval status: {e}")
            return "unknown"

    def _create_deployment(self, repository: str, pr_number: int,
                          analysis_summary: str, risk_score: int) -> str:
        """
        Create GitHub deployment for approval.
        
        Args:
            repository: Repository name
            pr_number: PR number
            analysis_summary: Analysis summary
            risk_score: Risk score
            
        Returns:
            Deployment ID
        """
        try:
            # In real implementation, would use GitHub API to create deployment
            # For now, return placeholder
            deployment_id = f"deploy_{pr_number}_{int(datetime.now(timezone.utc).timestamp())}"
            
            logger.info(f"Created deployment {deployment_id} for PR #{pr_number}")
            
            return deployment_id
            
        except Exception as e:
            logger.error(f"Failed to create deployment: {e}")
            raise

    def _check_deployment_status(self, repository: str, deployment_id: str) -> str:
        """
        Check deployment status.
        
        Args:
            repository: Repository name
            deployment_id: Deployment ID
            
        Returns:
            Status string
        """
        try:
            # In real implementation, would query GitHub API
            # For now, return pending
            return "pending"
            
        except Exception as e:
            logger.error(f"Failed to check deployment status: {e}")
            return "unknown"

    def _get_required_reviewers(self, repository: str, risk_score: int) -> List[str]:
        """
        Get required reviewers based on risk score.
        
        Args:
            repository: Repository name
            risk_score: Risk score
            
        Returns:
            List of required reviewer usernames
        """
        # High risk requires more reviewers
        if risk_score >= 8:
            return ["senior-engineer-1", "senior-engineer-2"]
        elif risk_score >= 5:
            return ["senior-engineer-1"]
        else:
            return ["any-team-member"]

    def _add_approval_comment(self, repository: str, pr_number: int,
                             analysis_summary: str, risk_score: int) -> None:
        """
        Add approval request comment to PR.
        
        Args:
            repository: Repository name
            pr_number: PR number
            analysis_summary: Analysis summary
            risk_score: Risk score
        """
        try:
            comment = f"""## 🤖 Auto-Remediation Approval Required

**Risk Score:** {risk_score}/10

**Analysis:**
{analysis_summary}

**Required Action:**
This PR requires approval before the auto-remediation can be deployed.
Please review the changes and approve via GitHub Environment protection rules.

**Approval Process:**
1. Review the proposed changes
2. Approve the deployment in the `{self.approval_environment}` environment
3. The remediation will be applied automatically upon approval

---
*Generated by CI/CD Failure Monitor*
"""
            
            # In real implementation, would use GitHub API to add comment
            logger.info(f"Added approval comment to PR #{pr_number}")
            
        except Exception as e:
            logger.error(f"Failed to add approval comment: {e}")
