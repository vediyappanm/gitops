"""GitHub API client for CI/CD Failure Monitor"""
import logging
import time
from typing import List, Dict, Any, Optional
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)


class GitHubClient:
    """GitHub API client with authentication and retry logic"""

    def __init__(self, token: str, retry_count: int = 3, retry_backoff: int = 1):
        """Initialize GitHub API client"""
        self.token = token
        self.base_url = "https://api.github.com"
        self.retry_count = retry_count
        self.retry_backoff = retry_backoff
        self.session = self._create_session()
        self._verify_authentication()

    def _create_session(self) -> requests.Session:
        """Create a requests session with retry logic"""
        session = requests.Session()
        
        # Configure retry strategy
        retry_strategy = Retry(
            total=self.retry_count,
            backoff_factor=self.retry_backoff,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST", "PUT", "DELETE"]
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        # Set authentication header
        session.headers.update({
            "Authorization": f"token {self.token}",
            "Accept": "application/vnd.github.v3+json"
        })
        
        return session

    def _verify_authentication(self) -> None:
        """Verify GitHub authentication"""
        try:
            response = self.session.get(f"{self.base_url}/user")
            if response.status_code == 401:
                raise ValueError("Invalid GitHub token")
            response.raise_for_status()
            logger.info("GitHub authentication verified")
        except Exception as e:
            logger.error(f"GitHub authentication failed: {e}")
            raise

    def _handle_rate_limit(self, response: requests.Response) -> None:
        """Handle GitHub API rate limiting"""
        if response.status_code == 403:
            remaining = response.headers.get("X-RateLimit-Remaining", "0")
            reset_time = response.headers.get("X-RateLimit-Reset", "0")
            
            if remaining == "0":
                wait_time = int(reset_time) - int(time.time())
                if wait_time > 0:
                    logger.warning(f"Rate limit reached. Waiting {wait_time} seconds")
                    time.sleep(wait_time + 1)

    def get_failed_workflow_runs(self, repo: str, branch: Optional[str] = None, per_page: int = 30) -> List[Dict[str, Any]]:
        """Fetch failed workflow runs from a repository"""
        try:
            url = f"{self.base_url}/repos/{repo}/actions/runs"
            params = {
                "status": "failure",
                "per_page": per_page
            }
            if branch:
                params["branch"] = branch
            
            response = self.session.get(url, params=params)
            self._handle_rate_limit(response)
            response.raise_for_status()
            
            data = response.json()
            logger.info(f"Retrieved {len(data.get('workflow_runs', []))} failed runs from {repo}")
            
            return data.get("workflow_runs", [])
        except Exception as e:
            logger.error(f"Failed to fetch workflow runs from {repo}: {e}")
            raise

    def get_workflow_run_details(self, repo: str, run_id: int) -> Dict[str, Any]:
        """Get complete workflow run details"""
        try:
            url = f"{self.base_url}/repos/{repo}/actions/runs/{run_id}"
            
            response = self.session.get(url)
            self._handle_rate_limit(response)
            response.raise_for_status()
            
            logger.debug(f"Retrieved details for run {run_id}")
            return response.json()
        except Exception as e:
            logger.error(f"Failed to fetch run details for {run_id}: {e}")
            raise

    def get_workflow_run_jobs(self, repo: str, run_id: int) -> List[Dict[str, Any]]:
        """Get jobs for a workflow run"""
        try:
            url = f"{self.base_url}/repos/{repo}/actions/runs/{run_id}/jobs"
            response = self.session.get(url)
            self._handle_rate_limit(response)
            response.raise_for_status()
            return response.json().get("jobs", [])
        except Exception as e:
            logger.error(f"Failed to fetch jobs for run {run_id}: {e}")
            raise

    def get_job_logs(self, repo: str, job_id: int) -> str:
        """Get logs for a specific job"""
        try:
            url = f"{self.base_url}/repos/{repo}/actions/jobs/{job_id}/logs"
            response = self.session.get(url)
            self._handle_rate_limit(response)
            
            if response.status_code == 404:
                return ""
                
            response.raise_for_status()
            return response.text
        except Exception as e:
            logger.error(f"Failed to fetch logs for job {job_id}: {e}")
            return ""

    def get_workflow_run_logs(self, repo: str, run_id: int) -> str:
        """Get logs from all failed jobs in a workflow run"""
        try:
            jobs = self.get_workflow_run_jobs(repo, run_id)
            failed_jobs = [j for j in jobs if j.get("conclusion") == "failure"]
            
            all_logs = []
            for job in failed_jobs:
                job_name = job.get("name", "Unknown Job")
                logs = self.get_job_logs(repo, job["id"])
                if logs:
                    all_logs.append(f"--- LOGS FOR JOB: {job_name} ---")
                    # Take last 5000 chars of job logs as they are usually most relevant
                    all_logs.append(logs[-5000:])
            
            return "\n".join(all_logs)
        except Exception as e:
            logger.error(f"Failed to aggregate logs for run {run_id}: {e}")
            return ""

    def get_commit_details(self, repo: str, commit_sha: str) -> Dict[str, Any]:
        """Get commit details"""
        try:
            url = f"{self.base_url}/repos/{repo}/commits/{commit_sha}"
            
            response = self.session.get(url)
            self._handle_rate_limit(response)
            response.raise_for_status()
            
            logger.debug(f"Retrieved commit details for {commit_sha}")
            return response.json()
        except Exception as e:
            logger.error(f"Failed to fetch commit details for {commit_sha}: {e}")
            raise

    def get_repository_contents(self, repo: str, path: str = "") -> List[Dict[str, Any]]:
        """Get repository contents at path"""
        try:
            url = f"{self.base_url}/repos/{repo}/contents/{path}"
            response = self.session.get(url)
            self._handle_rate_limit(response)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get contents for {repo}/{path}: {e}")
            raise

    def get_file_contents(self, repo: str, path: str, ref: Optional[str] = None) -> Optional[str]:
        """Get file contents from repository"""
        try:
            url = f"{self.base_url}/repos/{repo}/contents/{path}"
            params = {}
            if ref:
                params["ref"] = ref
                
            response = self.session.get(url, params=params)
            self._handle_rate_limit(response)
            
            if response.status_code == 404:
                return None
                
            response.raise_for_status()
            data = response.json()
            
            if isinstance(data, dict) and data.get("type") == "file":
                import base64
                content = base64.b64decode(data["content"]).decode("utf-8")
                return content
            return None
        except Exception as e:
            logger.error(f"Failed to get file contents for {repo}/{path}: {e}")
            raise

    def get_file_metadata(self, repo: str, path: str, ref: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Get file metadata including SHA from repository"""
        try:
            url = f"{self.base_url}/repos/{repo}/contents/{path}"
            params = {}
            if ref:
                params["ref"] = ref
                
            response = self.session.get(url, params=params)
            self._handle_rate_limit(response)
            
            if response.status_code == 404:
                return None
                
            response.raise_for_status()
            data = response.json()
            
            if isinstance(data, dict) and data.get("type") == "file":
                import base64
                content = base64.b64decode(data["content"]).decode("utf-8")
                return {
                    "content": content,
                    "sha": data.get("sha"),
                    "path": data.get("path"),
                    "size": data.get("size")
                }
            return None
        except Exception as e:
            logger.error(f"Failed to get file metadata for {repo}/{path}: {e}")
            raise

    def get_rate_limit_status(self) -> Dict[str, Any]:
        """Get current rate limit status"""
        try:
            url = f"{self.base_url}/rate_limit"
            
            response = self.session.get(url)
            response.raise_for_status()
            
            return response.json()
        except Exception as e:
            logger.error(f"Failed to fetch rate limit status: {e}")
            raise

    def update_file(self, repo: str, path: str, content: str, message: str, 
                   branch: str, sha: str) -> bool:
        """Update a file in the repository"""
        try:
            import base64
            
            url = f"{self.base_url}/repos/{repo}/contents/{path}"
            
            # Encode content to base64
            content_bytes = content.encode('utf-8')
            content_base64 = base64.b64encode(content_bytes).decode('utf-8')
            
            payload = {
                "message": message,
                "content": content_base64,
                "sha": sha,
                "branch": branch
            }
            
            response = self.session.put(url, json=payload)
            self._handle_rate_limit(response)
            
            if response.status_code in [200, 201]:
                logger.info(f"Successfully updated file {path} in {repo}")
                return True
            else:
                logger.error(f"Failed to update file {path}: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            logger.error(f"Failed to update file {repo}/{path}: {e}")
            return False

    def create_file(self, repo: str, path: str, content: str, message: str, 
                   branch: str) -> bool:
        """Create a new file in the repository"""
        try:
            import base64
            
            url = f"{self.base_url}/repos/{repo}/contents/{path}"
            
            # Encode content to base64
            content_bytes = content.encode('utf-8')
            content_base64 = base64.b64encode(content_bytes).decode('utf-8')
            
            payload = {
                "message": message,
                "content": content_base64,
                "branch": branch
            }
            
            response = self.session.put(url, json=payload)
            self._handle_rate_limit(response)
            
            if response.status_code in [200, 201]:
                logger.info(f"Successfully created file {path} in {repo}")
                return True
            else:
                logger.error(f"Failed to create file {path}: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            logger.error(f"Failed to create file {repo}/{path}: {e}")
            return False

    def create_fix_branch_from_broken(self, repo: str, broken_branch: str) -> Optional[str]:
        """Create a new branch starting from the broken branch"""
        try:
            # Get latest SHA from the broken branch
            url = f"{self.base_url}/repos/{repo}/git/refs/heads/{broken_branch}"
            response = self.session.get(url)
            self._handle_rate_limit(response)
            response.raise_for_status()
            
            latest_sha = response.json()["object"]["sha"]
            
            # Use naming convention: agent-fix/<broken-branch>-<timestamp>
            fix_branch_name = f"agent-fix/{broken_branch}-{int(time.time())}"
            
            create_branch_url = f"{self.base_url}/repos/{repo}/git/refs"
            payload = {
                "ref": f"refs/heads/{fix_branch_name}",
                "sha": latest_sha
            }
            
            response = self.session.post(create_branch_url, json=payload)
            self._handle_rate_limit(response)
            response.raise_for_status()
            
            logger.info(f"Created fix branch {fix_branch_name} from {broken_branch}")
            return fix_branch_name
        except Exception as e:
            logger.error(f"Failed to create fix branch from {broken_branch}: {e}")
            return None

    def create_pull_request(self, repo: str, title: str, body: str, 
                           head: str, base: str) -> Optional[str]:
        """Create a pull request"""
        try:
            url = f"{self.base_url}/repos/{repo}/pulls"
            payload = {
                "title": title,
                "body": body,
                "head": head,
                "base": base
            }
            
            response = self.session.post(url, json=payload)
            self._handle_rate_limit(response)
            response.raise_for_status()
            
            pr_url = response.json()["html_url"]
            logger.info(f"Created pull request: {pr_url}")
            return pr_url
        except Exception as e:
            logger.error(f"Failed to create PR: {e}")
            return None

    def close(self) -> None:
        """Close the session"""
        self.session.close()
        logger.info("GitHub client session closed")
