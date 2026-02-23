"""Explainability Layer for AI decision tracking"""
import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class DecisionType(str, Enum):
    """Type of AI decision"""
    CLASSIFICATION = "classification"
    FIX_GENERATION = "fix_generation"
    RISK_ASSESSMENT = "risk_assessment"
    FILE_SELECTION = "file_selection"


@dataclass
class Alternative:
    """Alternative option that was considered"""
    option: str
    reasoning: str
    score: float
    rejected_reason: str


@dataclass
class DecisionExplanation:
    """Detailed explanation of an AI decision"""
    decision_id: str
    failure_id: str
    decision_type: DecisionType
    chosen_option: str
    chosen_reasoning: str
    confidence_score: float
    alternatives_considered: List[Alternative] = field(default_factory=list)
    context_used: Dict[str, Any] = field(default_factory=dict)
    model_used: str = ""
    prompt_summary: str = ""
    response_time_ms: int = 0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "decision_id": self.decision_id,
            "failure_id": self.failure_id,
            "decision_type": self.decision_type.value,
            "chosen_option": self.chosen_option,
            "chosen_reasoning": self.chosen_reasoning,
            "confidence_score": self.confidence_score,
            "alternatives_considered": [
                {
                    "option": alt.option,
                    "reasoning": alt.reasoning,
                    "score": alt.score,
                    "rejected_reason": alt.rejected_reason
                }
                for alt in self.alternatives_considered
            ],
            "context_used": self.context_used,
            "model_used": self.model_used,
            "prompt_summary": self.prompt_summary,
            "response_time_ms": self.response_time_ms,
            "timestamp": self.timestamp.isoformat()
        }


@dataclass
class PostMortemReport:
    """Post-mortem analysis report"""
    failure_id: str
    repository: str
    branch: str
    failure_summary: str
    decisions_made: List[DecisionExplanation] = field(default_factory=list)
    outcome: str = ""
    lessons_learned: List[str] = field(default_factory=list)
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "failure_id": self.failure_id,
            "repository": self.repository,
            "branch": self.branch,
            "failure_summary": self.failure_summary,
            "decisions_made": [d.to_dict() for d in self.decisions_made],
            "outcome": self.outcome,
            "lessons_learned": self.lessons_learned,
            "generated_at": self.generated_at.isoformat()
        }


class ExplainabilityLayer:
    """Track and explain AI decisions for transparency and post-mortems"""

    def __init__(self, database):
        """
        Initialize explainability layer.
        
        Args:
            database: Database instance for storage
            
        Raises:
            ValueError: If database is None
        """
        if database is None:
            raise ValueError("database cannot be None")
        
        self.database = database
        self.decisions_cache: Dict[str, List[DecisionExplanation]] = {}
        
        logger.info("ExplainabilityLayer initialized")

    def record_classification_decision(self, failure_id: str, 
                                      chosen_category: str,
                                      chosen_error_type: str,
                                      confidence: float,
                                      reasoning: str,
                                      alternatives: List[Dict[str, Any]],
                                      context: Dict[str, Any],
                                      model: str,
                                      response_time_ms: int) -> DecisionExplanation:
        """
        Record a classification decision.
        
        Args:
            failure_id: Failure identifier
            chosen_category: Chosen failure category
            chosen_error_type: Chosen error type (DEVOPS/DEVELOPER)
            confidence: Confidence score (0-100)
            reasoning: Why this classification was chosen
            alternatives: List of alternative classifications considered
            context: Context used for decision (logs, repo structure, etc.)
            model: AI model used
            response_time_ms: Time taken to make decision
            
        Returns:
            DecisionExplanation record
            
        Raises:
            ValueError: If required fields are invalid
        """
        if not failure_id or not isinstance(failure_id, str):
            raise ValueError(f"failure_id must be non-empty string, got {type(failure_id)}")
        if not (0 <= confidence <= 100):
            raise ValueError(f"confidence must be 0-100, got {confidence}")
        
        try:
            decision_id = str(uuid.uuid4())
            
            # Parse alternatives
            alternative_objs = []
            for alt in alternatives:
                alternative_objs.append(Alternative(
                    option=alt.get("category", "unknown"),
                    reasoning=alt.get("reasoning", ""),
                    score=alt.get("score", 0.0),
                    rejected_reason=alt.get("rejected_reason", "Lower confidence")
                ))
            
            decision = DecisionExplanation(
                decision_id=decision_id,
                failure_id=failure_id,
                decision_type=DecisionType.CLASSIFICATION,
                chosen_option=f"{chosen_error_type}: {chosen_category}",
                chosen_reasoning=reasoning,
                confidence_score=confidence / 100.0,
                alternatives_considered=alternative_objs,
                context_used=context,
                model_used=model,
                prompt_summary=f"Classify failure in {context.get('repository', 'unknown')}",
                response_time_ms=response_time_ms
            )
            
            # Store decision
            self._store_decision(decision)
            
            logger.info(f"Recorded classification decision: {decision_id} "
                       f"(chosen={chosen_category}, confidence={confidence}%)")
            
            return decision
            
        except Exception as e:
            logger.error(f"Failed to record classification decision: {e}")
            raise

    def record_fix_generation_decision(self, failure_id: str,
                                      chosen_fix: str,
                                      files_to_modify: List[str],
                                      reasoning: str,
                                      alternatives: List[Dict[str, Any]],
                                      context: Dict[str, Any],
                                      model: str,
                                      response_time_ms: int) -> DecisionExplanation:
        """
        Record a fix generation decision.
        
        Args:
            failure_id: Failure identifier
            chosen_fix: Chosen fix approach
            files_to_modify: Files that will be modified
            reasoning: Why this fix was chosen
            alternatives: Alternative fixes considered
            context: Context used (historical patterns, repo structure)
            model: AI model used
            response_time_ms: Time taken
            
        Returns:
            DecisionExplanation record
            
        Raises:
            ValueError: If required fields are invalid
        """
        if not failure_id or not isinstance(failure_id, str):
            raise ValueError(f"failure_id must be non-empty string, got {type(failure_id)}")
        
        try:
            decision_id = str(uuid.uuid4())
            
            # Parse alternatives
            alternative_objs = []
            for alt in alternatives:
                alternative_objs.append(Alternative(
                    option=alt.get("fix", "unknown"),
                    reasoning=alt.get("reasoning", ""),
                    score=alt.get("score", 0.0),
                    rejected_reason=alt.get("rejected_reason", "Lower effectiveness score")
                ))
            
            decision = DecisionExplanation(
                decision_id=decision_id,
                failure_id=failure_id,
                decision_type=DecisionType.FIX_GENERATION,
                chosen_option=chosen_fix[:200],
                chosen_reasoning=reasoning,
                confidence_score=0.8,  # Default confidence for fix generation
                alternatives_considered=alternative_objs,
                context_used={
                    **context,
                    "files_to_modify": files_to_modify
                },
                model_used=model,
                prompt_summary=f"Generate fix for {len(files_to_modify)} files",
                response_time_ms=response_time_ms
            )
            
            # Store decision
            self._store_decision(decision)
            
            logger.info(f"Recorded fix generation decision: {decision_id} "
                       f"(files={len(files_to_modify)})")
            
            return decision
            
        except Exception as e:
            logger.error(f"Failed to record fix generation decision: {e}")
            raise

    def record_risk_assessment_decision(self, failure_id: str,
                                       risk_score: int,
                                       reasoning: str,
                                       factors: Dict[str, Any],
                                       model: str) -> DecisionExplanation:
        """
        Record a risk assessment decision.
        
        Args:
            failure_id: Failure identifier
            risk_score: Assigned risk score (0-10)
            reasoning: Why this risk score
            factors: Factors considered (complexity, blast radius, etc.)
            model: AI model or algorithm used
            
        Returns:
            DecisionExplanation record
            
        Raises:
            ValueError: If required fields are invalid
        """
        if not failure_id or not isinstance(failure_id, str):
            raise ValueError(f"failure_id must be non-empty string, got {type(failure_id)}")
        if not (0 <= risk_score <= 10):
            raise ValueError(f"risk_score must be 0-10, got {risk_score}")
        
        try:
            decision_id = str(uuid.uuid4())
            
            decision = DecisionExplanation(
                decision_id=decision_id,
                failure_id=failure_id,
                decision_type=DecisionType.RISK_ASSESSMENT,
                chosen_option=f"Risk Score: {risk_score}/10",
                chosen_reasoning=reasoning,
                confidence_score=0.9,
                alternatives_considered=[],
                context_used=factors,
                model_used=model,
                prompt_summary="Assess remediation risk",
                response_time_ms=0
            )
            
            # Store decision
            self._store_decision(decision)
            
            logger.info(f"Recorded risk assessment decision: {decision_id} "
                       f"(risk={risk_score})")
            
            return decision
            
        except Exception as e:
            logger.error(f"Failed to record risk assessment decision: {e}")
            raise

    def generate_post_mortem(self, failure_id: str) -> PostMortemReport:
        """
        Generate post-mortem report for a failure.
        
        Args:
            failure_id: Failure identifier
            
        Returns:
            PostMortemReport with all decisions and analysis
            
        Raises:
            ValueError: If failure_id is invalid
        """
        if not failure_id or not isinstance(failure_id, str):
            raise ValueError(f"failure_id must be non-empty string, got {type(failure_id)}")
        
        try:
            # Get failure details
            failure = self.database.get_failure(failure_id)
            if not failure:
                raise ValueError(f"Failure {failure_id} not found")
            
            # Get all decisions for this failure
            decisions = self._get_decisions_for_failure(failure_id)
            
            # Determine outcome
            outcome = "Unknown"
            if failure.status.value == "remediated":
                outcome = "Successfully remediated"
            elif failure.status.value == "failed":
                outcome = "Remediation failed"
            elif failure.status.value == "analyzed":
                outcome = "Awaiting approval"
            
            # Generate lessons learned
            lessons = self._extract_lessons_learned(failure, decisions)
            
            report = PostMortemReport(
                failure_id=failure_id,
                repository=failure.repository,
                branch=failure.branch,
                failure_summary=failure.failure_reason[:500],
                decisions_made=decisions,
                outcome=outcome,
                lessons_learned=lessons
            )
            
            logger.info(f"Generated post-mortem for {failure_id}: "
                       f"{len(decisions)} decisions, outcome={outcome}")
            
            return report
            
        except Exception as e:
            logger.error(f"Failed to generate post-mortem: {e}")
            raise

    def get_decision_chain(self, failure_id: str) -> List[DecisionExplanation]:
        """
        Get complete decision chain for a failure.
        
        Args:
            failure_id: Failure identifier
            
        Returns:
            List of decisions in chronological order
        """
        try:
            decisions = self._get_decisions_for_failure(failure_id)
            decisions.sort(key=lambda d: d.timestamp)
            return decisions
        except Exception as e:
            logger.error(f"Failed to get decision chain: {e}")
            return []

    def _store_decision(self, decision: DecisionExplanation) -> None:
        """
        Store decision in database and cache.
        
        Args:
            decision: Decision to store
        """
        try:
            # Store in database
            self.database.store_decision_explanation(decision)
            
            # Add to cache
            if decision.failure_id not in self.decisions_cache:
                self.decisions_cache[decision.failure_id] = []
            self.decisions_cache[decision.failure_id].append(decision)
            
        except Exception as e:
            logger.error(f"Failed to store decision: {e}")
            raise

    def _get_decisions_for_failure(self, failure_id: str) -> List[DecisionExplanation]:
        """
        Get all decisions for a failure.
        
        Args:
            failure_id: Failure identifier
            
        Returns:
            List of decisions
        """
        # Check cache first
        if failure_id in self.decisions_cache:
            return self.decisions_cache[failure_id]
        
        # Load from database
        try:
            decisions = self.database.get_decisions_for_failure(failure_id)
            self.decisions_cache[failure_id] = decisions
            return decisions
        except Exception as e:
            logger.warning(f"Failed to load decisions from database: {e}")
            return []

    def _extract_lessons_learned(self, failure, decisions: List[DecisionExplanation]) -> List[str]:
        """
        Extract lessons learned from failure and decisions.
        
        Args:
            failure: Failure record
            decisions: List of decisions made
            
        Returns:
            List of lessons learned
        """
        lessons = []
        
        # Check if classification was correct
        classification_decisions = [d for d in decisions if d.decision_type == DecisionType.CLASSIFICATION]
        if classification_decisions:
            decision = classification_decisions[0]
            if decision.confidence_score < 0.7:
                lessons.append(f"Low confidence classification ({decision.confidence_score:.0%}) - "
                             "consider manual review for similar failures")
        
        # Check if fix was successful
        if failure.status.value == "failed":
            lessons.append("Remediation failed - review fix generation approach")
            
            fix_decisions = [d for d in decisions if d.decision_type == DecisionType.FIX_GENERATION]
            if fix_decisions and fix_decisions[0].alternatives_considered:
                lessons.append(f"Consider alternative fixes: "
                             f"{[alt.option[:50] for alt in fix_decisions[0].alternatives_considered[:2]]}")
        
        # Check risk assessment
        risk_decisions = [d for d in decisions if d.decision_type == DecisionType.RISK_ASSESSMENT]
        if risk_decisions:
            risk_score = int(risk_decisions[0].chosen_option.split(":")[1].split("/")[0].strip())
            if risk_score >= 7:
                lessons.append(f"High risk remediation (score={risk_score}) - "
                             "ensure proper testing and rollback plan")
        
        if not lessons:
            lessons.append("No specific lessons - remediation followed standard process")
        
        return lessons
