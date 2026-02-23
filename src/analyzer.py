"""Analyzer component for AI-powered failure analysis"""
import logging
import json
import re
from typing import Dict, Any, Optional, List
import requests
from src.models import AnalysisResult, FailureRecord, FailureCategory
from src.database import Database

logger = logging.getLogger(__name__)


class Analyzer:
    """Analyze failures using Groq API"""

    def __init__(self, groq_api_key: str, database: Database, github_client=None,
                 failure_pattern_memory=None):
        """Initialize analyzer"""
        self.api_key = groq_api_key.strip()
        self.database = database
        self.github_client = github_client
        self.failure_pattern_memory = failure_pattern_memory
        self.model = "llama-3.3-70b-versatile"  # Groq model
        self.api_url = "https://api.groq.com/openai/v1/chat/completions"

    def analyze_failure(self, failure: FailureRecord) -> AnalysisResult:
        """Send failure to Groq for analysis"""
        try:
            prompt = self._build_analysis_prompt(failure)
            
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": self.model,
                "messages": [
                    {
                        "role": "system",
                        "content": """You are a CI/CD failure analysis expert. You output ONLY valid JSON.
Example valid response:
{
    "error_type": "DEVOPS",
    "category": "config",
    "risk_score": 3,
    "confidence": 95,
    "proposed_fix": "Fix typo in workflow yaml",
    "effort_estimate": "low",
    "affected_components": ["workflow"],
    "reasoning": "The job failed because of a syntax error in ci.yml",
    "files_to_modify": [".github/workflows/ci.yml"],
    "fix_commands": []
}"""
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "temperature": 0.1,
                "max_tokens": 2000
            }
            
            logger.info(f"Sending analysis request to Groq for failure {failure.failure_id}")
            response = requests.post(self.api_url, headers=headers, json=payload, timeout=60)
            
            if response.status_code != 200:
                logger.error(f"Groq API error: {response.status_code} - {response.text}")
                response.raise_for_status()
            
            response_data = response.json()
            response_text = response_data["choices"][0]["message"]["content"]
            logger.info(f"Received analysis response for failure {failure.failure_id}")
            
            analysis = self._parse_analysis_response(response_text)
            analysis.failure_id = failure.failure_id
            
            # Store analysis result
            self.database.store_analysis(analysis)
            
            logger.info(f"Analysis completed for failure {failure.failure_id}: "
                       f"type={analysis.error_type}, category={analysis.category.value}, "
                       f"risk={analysis.risk_score}")
            
            return analysis
            
        except Exception as e:
            logger.error(f"Error in analyze_failure: {e}")
            # Return a default "failed" analysis
            return AnalysisResult(
                failure_id=failure.failure_id,
                error_type="DEVOPS",
                category=FailureCategory.INFRASTRUCTURE,
                risk_score=8,
                confidence=50,
                proposed_fix="Manual investigation required",
                effort_estimate="high",
                affected_components=["unknown"],
                reasoning=f"Analysis failed: {str(e)}",
                files_to_modify=[]
            )

    def generate_file_fix(self, failure: FailureRecord, analysis: AnalysisResult, 
                          file_path: str, current_content: str) -> str:
        """Generate a fix for a specific file"""
        try:
            prompt = f"""Target File: {file_path}
Current Content:
```
{current_content}
```

Failure Context:
Reason: {failure.failure_reason}
Analysis: {analysis.reasoning}
Proposed Plan: {analysis.proposed_fix}

Output only the full fixed file content. No markdown, no explanations."""
            
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": self.model,
                "messages": [
                    {
                        "role": "system",
                        "content": "You are a specialized code repair tool."
                    },
                    {
                        "role": "user",
                        "content": f"{prompt}\n\nIMPORTANT: Output ONLY the raw fixed file content. NO markdown fences, NO explanations, NO text other than the literal file content."
                    }
                ],
                "temperature": 0.1,
                "max_tokens": 4000
            }
            
            response = requests.post(self.api_url, headers=headers, json=payload, timeout=60)
            response.raise_for_status()
            
            response_data = response.json()
            fixed_content = response_data["choices"][0]["message"]["content"]
            
            # Clean up potential markdown fences
            if fixed_content.startswith("```"):
                lines = fixed_content.split('\n')
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].startswith("```"):
                    lines = lines[:-1]
                fixed_content = '\n'.join(lines)
            
            return fixed_content.strip()
            
        except Exception as e:
            logger.error(f"Failed to generate file fix for {file_path}: {e}")
            return current_content

    def _build_analysis_prompt(self, failure: FailureRecord) -> str:
        """Build analysis prompt for Groq"""
        repo_structure = self._get_repo_structure(failure.repository)
        
        # Get historical context if available
        historical_context = ""
        if self.failure_pattern_memory:
            try:
                historical_context = self.failure_pattern_memory.get_historical_context(
                    failure.failure_reason,
                    "unknown",  # Category not known yet
                    failure.repository
                )
            except Exception as e:
                logger.warning(f"Failed to get historical context: {e}")
                historical_context = ""
        
        prompt = f"""Analyze this CI/CD workflow failure. 

Repository: {failure.repository}
Branch: {failure.branch}
Commit: {failure.commit_sha}
Failure Reason: {failure.failure_reason}

Repository Structure (Key Files):
{repo_structure}"""
        
        if historical_context:
            prompt += f"\n\n{historical_context}"
        
        prompt += """

CLASSIFICATION RULES:
- DEVOPS: Infrastructure, deployment, CI/CD config (.github/workflows/*.yml, Dockerfile, docker-compose.yml, requirements.txt, package.json), dependencies, timeouts, environment issues.
- DEVELOPER: Application code bugs, failing unit/integration tests, syntax errors in application code (.py, .js, .ts, etc. in src/).

REQUIRED JSON structure:
{{
    "error_type": "DEVOPS or DEVELOPER",
    "category": "dependency, timeout, config, flaky_test, infrastructure, test_failure, build_error, or lint_error",
    "risk_score": 0-10,
    "confidence": 0-100,
    "proposed_fix": "description",
    "effort_estimate": "low, medium, or high",
    "affected_components": ["components"],
    "reasoning": "explanation",
    "files_to_modify": ["EXACT/path/to/files"],
    "fix_commands": ["commands"]
}}

Logs (last part):
{failure.logs[-5000:]}

OUTPUT ONLY THE JSON OBJECT. NO MARKDOWN. NO PREAMBLE. NO FENCES."""
        
        return prompt

    def _get_repo_structure(self, repo: str) -> str:
        """Get flattened repository structure for key areas"""
        if not self.github_client:
            return "Unknown"
            
        structure = []
        try:
            dirs_to_check = ["", ".github/workflows", "configs", "scripts", "src", "tests"]
            for path in dirs_to_check:
                try:
                    contents = self.github_client.get_repository_contents(repo, path)
                    if isinstance(contents, list):
                        structure.append(f"/{path}:")
                        for item in contents:
                            prefix = "  - " if path else "- "
                            file_type = "[DIR]" if item["type"] == "dir" else "[FILE]"
                            structure.append(f"{prefix}{item['name']} {file_type}")
                except Exception:
                    continue
            return "\n".join(structure)
        except Exception as e:
            logger.warning(f"Failed to get repo structure: {e}")
            return "Unknown"

    def _parse_analysis_response(self, response_text: str) -> AnalysisResult:
        """Parse AI response with robust multi-strategy JSON extraction"""
        logger.debug(f"Parsing Groq response ({len(response_text)} chars)")
        
        # Strategy 1: Direct parse
        try:
            data = json.loads(response_text.strip())
            return self._validate_and_finalize_analysis(data)
        except json.JSONDecodeError:
            pass
            
        # Strategy 2: Extract all {...} blocks and try them
        # Note: replace newlines as re.findall might have issues with non-greedy match across lines without DOTALL
        json_blocks = re.findall(r'(\{.*?\})', response_text.replace('\n', ' '), re.DOTALL)
        
        # Also try more greedy extraction if simple one fails
        if not json_blocks:
             start = response_text.find('{')
             end = response_text.rfind('}')
             if start != -1 and end != -1:
                 json_blocks = [response_text[start:end+1]]

        for block in json_blocks:
            try:
                # Need to handle potential nested braces or unescaped quotes if we did a simple regex
                data = json.loads(block)
                if isinstance(data, list) and len(data) > 0 and isinstance(data[0], dict):
                    data = data[0]
                if isinstance(data, dict):
                    return self._validate_and_finalize_analysis(data)
            except json.JSONDecodeError:
                continue
                
        # Strategy 3: Search for keys in text (super fallback)
        logger.warning(f"All JSON parse strategies failed. Using fallback. Raw: {response_text[:200]}...")
        fallback_data = {
            "error_type": "DEVOPS" if "DEVOPS" in response_text.upper() else "DEVELOPER",
            "category": "infrastructure",
            "risk_score": 8,
            "confidence": 50,
            "proposed_fix": "Analysis parsing failed, fallback used.",
            "effort_estimate": "medium",
            "affected_components": ["unknown"],
            "reasoning": f"Could not parse AI response",
            "files_to_modify": []
        }
        return self._validate_and_finalize_analysis(fallback_data)

    def _validate_and_finalize_analysis(self, data: Dict[str, Any]) -> AnalysisResult:
        """Ensure all required fields exist and have correct types"""
        if not isinstance(data, dict):
            data = {}

        defaults = {
            "error_type": "DEVOPS",
            "category": "infrastructure",
            "risk_score": 5,
            "confidence": 50,
            "proposed_fix": "Not provided",
            "effort_estimate": "medium",
            "affected_components": [],
            "reasoning": "No reasoning provided",
            "files_to_modify": [],
            "fix_commands": []
        }
        
        for key, val in defaults.items():
            if key not in data:
                data[key] = val
                
        # Type conversions and clamping
        try:
            risk = int(data.get("risk_score", 5))
            conf = int(data.get("confidence", 50))
        except (ValueError, TypeError):
            risk = 5
            conf = 50
            
        risk = max(0, min(10, risk))
        conf = max(0, min(100, conf))
        
        # Enum validation
        valid_categories = [c.value for c in FailureCategory]
        cat_str = str(data.get("category", "infrastructure")).lower()
        if cat_str not in valid_categories:
            cat_str = "infrastructure"
        
        return AnalysisResult(
            failure_id="", 
            error_type=str(data.get("error_type", "DEVOPS")).upper(),
            category=FailureCategory(cat_str),
            risk_score=risk,
            confidence=conf,
            proposed_fix=str(data.get("proposed_fix", "")),
            effort_estimate=str(data.get("effort_estimate", "medium")),
            affected_components=data.get("affected_components", []) if isinstance(data.get("affected_components"), list) else [],
            reasoning=str(data.get("reasoning", "")),
            files_to_modify=data.get("files_to_modify", []) if isinstance(data.get("files_to_modify"), list) else [],
            fix_commands=data.get("fix_commands", []) if isinstance(data.get("fix_commands"), list) else []
        )
