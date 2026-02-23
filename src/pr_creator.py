"""GitHub Pull Request Creator for automated fixes"""
import logging
import base64
from typing import Optional, Tuple
from src.github_client import GitHubClient
from src.analyzer import Analyzer
from src.models import FailureRecord, AnalysisResult

logger = logging.getLogger(__name__)


class PRCreator:
    """Create pull requests for DevOps fixes"""

    def __init__(self, github_client: GitHubClient, analyzer: Analyzer = None):
        """Initialize PR creator"""
        self.github_client = github_client
        self.analyzer = analyzer

    def create_fix_pr(self, failure: FailureRecord, analysis: AnalysisResult) -> Tuple[bool, str]:
        """Create a pull request with the fix"""
        try:
            if not analysis.files_to_modify:
                logger.warning(f"No files to modify for failure {failure.failure_id}")
                return False, "No files specified for modification"
            
            # Create a new branch
            branch_name = self._create_branch(failure, analysis)
            if not branch_name:
                return False, "Failed to create branch"
            
            # Modify files using AI-generated fixes
            success = self._modify_files(failure, analysis, branch_name)
            if not success:
                return False, "Failed to modify files"
            
            # Create pull request
            pr_url = self._create_pull_request(failure, analysis, branch_name)
            if not pr_url:
                return False, "Failed to create pull request"
            
            logger.info(f"Pull request created: {pr_url}")
            return True, pr_url
        except Exception as e:
            logger.error(f"Error creating PR: {e}")
            return False, str(e)

    def _create_branch(self, failure: FailureRecord, analysis: AnalysisResult) -> Optional[str]:
        """Create a new branch for the fix"""
        return self.github_client.create_fix_branch_from_broken(
            failure.repository, failure.branch
        )

    def _modify_files(self, failure: FailureRecord, analysis: AnalysisResult, branch_name: str) -> bool:
        """Modify files with the AI-generated fix"""
        try:
            files_modified = 0
            
            for file_path in analysis.files_to_modify:
                # Get current file content
                current_content = self.github_client.get_file_contents(
                    failure.repository, file_path, ref=branch_name
                )
                
                if current_content is None:
                    logger.warning(f"File not found in repo: {file_path}, skipping")
                    continue
                
                # Get SHA for update (we need to get details again because we need the SHA)
                url = f"https://api.github.com/repos/{failure.repository}/contents/{file_path}"
                params = {"ref": branch_name}
                response = self.github_client.session.get(url, params=params)
                response.raise_for_status()
                sha = response.json().get("sha")
                
                # Use AI to generate the actual fixed content
                if self.analyzer:
                    new_content = self.analyzer.generate_file_fix(
                        failure, analysis, file_path, current_content
                    )
                else:
                    # Fallback: apply simple heuristic fixes
                    new_content = self._apply_heuristic_fix(current_content, analysis.proposed_fix)
                
                # Only update if content actually changed
                if new_content.strip() == current_content.strip():
                    logger.warning(f"No changes generated for file {file_path}, skipping")
                    continue
                
                # Update file on the branch
                message = f"fix: {analysis.category.value} - {analysis.reasoning[:80]}"
                success = self.github_client.update_file(
                    failure.repository, file_path, new_content, message, branch_name, sha
                )
                
                if success:
                    files_modified += 1
                    logger.info(f"Updated file: {file_path}")
            
            if files_modified == 0:
                logger.warning("No files were actually modified")
                return False
            
            logger.info(f"Successfully modified {files_modified} file(s)")
            return True
        except Exception as e:
            logger.error(f"Failed to modify files: {e}")
            return False

    def _apply_heuristic_fix(self, content: str, proposed_fix: str) -> str:
        """Fallback: apply simple heuristic fixes when AI is unavailable"""
        fix_lower = proposed_fix.lower()
        
        if "timeout" in fix_lower:
            content = content.replace("timeout: 30", "timeout: 60")
            content = content.replace("timeout: 5", "timeout: 10")
            content = content.replace("timeout-minutes: 5", "timeout-minutes: 10")
            content = content.replace("timeout-minutes: 10", "timeout-minutes: 20")
        
        if "retry" in fix_lower:
            if "retries:" not in content and "retry" not in content:
                content = content.replace("timeout:", "retries: 3\n  timeout:")
        
        if "cache" in fix_lower:
            if "actions/cache" not in content:
                content = content.replace(
                    "steps:\n",
                    "steps:\n    - uses: actions/cache@v4\n      with:\n        path: ~/.cache\n        key: ${{ runner.os }}-cache\n"
                )
        
        return content

    def _create_pull_request(self, failure: FailureRecord, analysis: AnalysisResult, 
                            branch_name: str) -> Optional[str]:
        """Create a pull request targeting the teammate's branch"""
        title = f"🤖 Agent Fix: {failure.branch}"
        body = self._build_pr_description(failure, analysis)
        
        return self.github_client.create_pull_request(
            failure.repository, title, body, branch_name, failure.branch
        )

    def _build_pr_description(self, failure: FailureRecord, analysis: AnalysisResult) -> str:
        """Build pull request description with comprehensive metadata"""
        run_url = f"https://github.com/{failure.repository}/actions/runs/{failure.workflow_run_id}"
        commit_url = f"https://github.com/{failure.repository}/commit/{failure.commit_sha}"
        timestamp = failure.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')
        
        files_list = "\n".join([f"- `{f}`" for f in analysis.files_to_modify])
        commands_list = "\n".join([f"- `{c}`" for c in analysis.fix_commands]) if analysis.fix_commands else "- *None*"
        components_list = ", ".join([f"`{c}`" for c in analysis.affected_components]) if analysis.affected_components else "*None*"

        return f"""## 🔧 Automated CI Failure Fix

### 📊 Analysis Summary
| Metric | Value |
| :--- | :--- |
| **Failure Type** | {analysis.error_type} |
| **Category** | `{analysis.category.value}` |
| **Risk Score** | `{analysis.risk_score}/10` |
| **Confidence** | `{analysis.confidence}%` |
| **Effort Estimate** | `{analysis.effort_estimate}` |
| **Detected At** | {timestamp} |

### 🔗 Context Links
- **Failed Workflow Run:** [View Run Logs]({run_url})
- **Triggering Commit:** [`{failure.commit_sha[:8]}`]({commit_url})
- **Target Branch:** `{failure.branch}`
- **Affected Components:** {components_list}

### 📝 Problem Statement
> {failure.failure_reason}

### 🧠 AI Analysis & Reasoning
{analysis.reasoning}

### ✅ Proposed Remediation
{analysis.proposed_fix}

### 🛠️ Change Details
**Files to be modified:**
{files_list}

**Commands to run (if applicable):**
{commands_list}

---
*This PR was automatically created by the **CI/CD Failure Monitor Agent** using AI analysis.*  
*Please review the proposed changes carefully and verify they address the root cause without introducing regressions.*
"""
