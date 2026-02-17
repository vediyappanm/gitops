"""Safety Gate component for validating remediations"""
import logging
from typing import Tuple
from src.models import FailureRecord, AnalysisResult
from src.config_manager import ConfigurationManager

logger = logging.getLogger(__name__)


class SafetyGate:
    """Validate that remediations are safe before execution"""

    def __init__(self, config: ConfigurationManager):
        """Initialize safety gate"""
        self.config = config

    def validate_remediation(self, failure: FailureRecord, analysis: AnalysisResult) -> Tuple[bool, str]:
        """Run all safety checks"""
        checks = [
            self._check_risk_score(failure, analysis),
            self._check_protected_repository(failure),
            self._check_has_files_to_modify(analysis),
        ]
        
        for passed, reason in checks:
            if not passed:
                logger.warning(f"Safety gate BLOCKED: {reason}")
                return False, reason
        
        logger.info(f"Safety gate PASSED for failure {failure.failure_id} "
                    f"(risk={analysis.risk_score}, category={analysis.category.value})")
        return True, "All safety checks passed"

    def _check_risk_score(self, failure: FailureRecord, analysis: AnalysisResult) -> Tuple[bool, str]:
        """Check if risk score is below threshold"""
        threshold = self.config.get_repo_risk_threshold(failure.repository)
        
        if analysis.risk_score >= threshold:
            return False, f"Risk score {analysis.risk_score} >= threshold {threshold}"
        
        return True, f"Risk score {analysis.risk_score} < threshold {threshold}"

    def _check_protected_repository(self, failure: FailureRecord) -> Tuple[bool, str]:
        """Check if repository is protected"""
        if self.config.is_protected_repository(failure.repository):
            return False, f"Repository {failure.repository} is protected"
        
        return True, f"Repository {failure.repository} is not protected"

    def _check_has_files_to_modify(self, analysis: AnalysisResult) -> Tuple[bool, str]:
        """Check that the AI identified specific files to modify"""
        if not analysis.files_to_modify:
            return False, "No files identified for modification - manual review needed"
        
        return True, f"Files to modify: {', '.join(analysis.files_to_modify)}"
