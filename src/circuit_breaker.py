"""Circuit Breaker for preventing infinite retry storms"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from enum import Enum
import hashlib

logger = logging.getLogger(__name__)


class CircuitState(str, Enum):
    """Circuit breaker state"""
    CLOSED = "closed"  # Normal operation
    OPEN = "open"      # Circuit breaker triggered
    HALF_OPEN = "half_open"  # Auto-reset period


@dataclass
class StateTransition:
    """Record of a state transition"""
    timestamp: datetime
    from_state: CircuitState
    to_state: CircuitState
    reason: str
    triggered_by: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "from_state": self.from_state.value,
            "to_state": self.to_state.value,
            "reason": self.reason,
            "triggered_by": self.triggered_by
        }


@dataclass
class CircuitBreakerState:
    """State of a circuit breaker"""
    failure_signature: str
    repository_id: str
    workflow_name: str
    error_pattern: str
    branch: str = "main"
    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    last_failure_at: Optional[datetime] = None
    opened_at: Optional[datetime] = None
    auto_reset_at: Optional[datetime] = None
    manually_reset_at: Optional[datetime] = None
    manually_reset_by: Optional[str] = None
    history: List[StateTransition] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "failure_signature": self.failure_signature,
            "repository_id": self.repository_id,
            "workflow_name": self.workflow_name,
            "error_pattern": self.error_pattern,
            "branch": self.branch,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "last_failure_at": self.last_failure_at.isoformat() if self.last_failure_at else None,
            "opened_at": self.opened_at.isoformat() if self.opened_at else None,
            "auto_reset_at": self.auto_reset_at.isoformat() if self.auto_reset_at else None,
            "manually_reset_at": self.manually_reset_at.isoformat() if self.manually_reset_at else None,
            "manually_reset_by": self.manually_reset_by,
            "history": [t.to_dict() for t in self.history]
        }


class FailureSignature:
    """Unique identifier for a failure pattern"""

    def __init__(self, repository_id: str, workflow_name: str, error_pattern: str, branch: str = None):
        self.repository_id = repository_id
        self.workflow_name = workflow_name
        self.error_pattern = self._normalize_error(error_pattern)
        self.branch = branch or "main"  # Default to main if not specified

    def _normalize_error(self, error: str) -> str:
        """Normalize error message for pattern matching"""
        # Remove timestamps, line numbers, file paths, memory addresses, UUIDs, and other variable parts
        import re
        normalized = error.lower()
        
        # Remove dates (YYYY-MM-DD)
        normalized = re.sub(r'\d{4}-\d{2}-\d{2}', '', normalized)
        
        # Remove times (HH:MM:SS)
        normalized = re.sub(r'\d{2}:\d{2}:\d{2}', '', normalized)
        
        # Normalize line numbers
        normalized = re.sub(r'line \d+', 'line X', normalized)
        normalized = re.sub(r':\d+:', ':X:', normalized)
        
        # Remove file paths (Unix and Windows)
        normalized = re.sub(r'/[\w/.-]+\.(py|js|ts|java|go|rb|cpp|c|h)', '/path/file.ext', normalized)
        normalized = re.sub(r'[A-Z]:\\[\w\\.-]+\.(py|js|ts|java|go|rb|cpp|c|h)', 'C:/path/file.ext', normalized)
        
        # Remove temp file paths
        normalized = re.sub(r'/tmp/[\w-]+', '/tmp/X', normalized)
        normalized = re.sub(r'\\temp\\[\w-]+', '/temp/X', normalized)
        
        # Remove memory addresses (0x...)
        normalized = re.sub(r'0x[0-9a-f]+', '0xADDR', normalized)
        
        # Remove UUIDs
        normalized = re.sub(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', 'UUID', normalized)
        
        # Remove port numbers
        normalized = re.sub(r':\d{2,5}\b', ':PORT', normalized)
        
        # Normalize whitespace
        normalized = re.sub(r'\s+', ' ', normalized).strip()
        
        return normalized[:200]  # Limit length

    def to_key(self) -> str:
        """Generate unique key for this failure signature"""
        content = f"{self.repository_id}:{self.branch}:{self.workflow_name}:{self.error_pattern}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]


class CircuitBreaker:
    """Manages circuit breaker state for repositories"""

    def __init__(self, database, failure_threshold: int = 3, auto_reset_hours: int = 24):
        """Initialize circuit breaker"""
        self.database = database
        self.failure_threshold = failure_threshold
        self.auto_reset_hours = auto_reset_hours
        self.circuits: Dict[str, CircuitBreakerState] = {}
        logger.info(f"CircuitBreaker initialized: threshold={failure_threshold}, "
                   f"auto_reset={auto_reset_hours}h")

    def get_state(self, failure_signature: FailureSignature) -> CircuitBreakerState:
        """Get circuit breaker state for a failure signature"""
        key = failure_signature.to_key()
        
        if key not in self.circuits:
            # Load from database or create new
            state = self.database.get_circuit_breaker_state(key)
            if not state:
                state = CircuitBreakerState(
                    failure_signature=key,
                    repository_id=failure_signature.repository_id,
                    workflow_name=failure_signature.workflow_name,
                    error_pattern=failure_signature.error_pattern,
                    branch=failure_signature.branch,
                    state=CircuitState.CLOSED,
                    failure_count=0
                )
            self.circuits[key] = state
        
        return self.circuits[key]

    def record_failure(self, failure_signature: FailureSignature) -> StateTransition:
        """Record a failure and update circuit breaker state"""
        state = self.get_state(failure_signature)
        key = failure_signature.to_key()
        
        # Increment failure count
        state.failure_count += 1
        state.last_failure_at = datetime.now(timezone.utc)
        
        logger.info(f"Circuit breaker: Recorded failure {state.failure_count}/{self.failure_threshold} "
                   f"for {state.repository_id}")
        
        # Check if threshold reached
        if state.failure_count >= self.failure_threshold and state.state == CircuitState.CLOSED:
            # Open circuit
            previous_state = state.state
            state.state = CircuitState.OPEN
            state.opened_at = datetime.now(timezone.utc)
            state.auto_reset_at = datetime.now(timezone.utc) + timedelta(hours=self.auto_reset_hours)
            
            transition = StateTransition(
                timestamp=datetime.now(timezone.utc),
                from_state=previous_state,
                to_state=CircuitState.OPEN,
                reason=f"Failure threshold reached ({state.failure_count} failures)",
                triggered_by="system"
            )
            state.history.append(transition)
            
            logger.warning(f"CIRCUIT BREAKER OPENED for {state.repository_id} - "
                          f"Auto-remediation FROZEN until {state.auto_reset_at}")
            
            # Persist state
            self.database.store_circuit_breaker_state(state)
            
            return transition
        
        # Persist state
        self.database.store_circuit_breaker_state(state)
        
        return StateTransition(
            timestamp=datetime.now(timezone.utc),
            from_state=state.state,
            to_state=state.state,
            reason=f"Failure recorded ({state.failure_count}/{self.failure_threshold})",
            triggered_by="system"
        )

    def record_success(self, failure_signature: FailureSignature) -> None:
        """Record a successful remediation"""
        state = self.get_state(failure_signature)
        
        # Reset failure count on success
        if state.failure_count > 0:
            logger.info(f"Circuit breaker: Success recorded for {state.repository_id}, "
                       f"resetting failure count from {state.failure_count} to 0")
            state.failure_count = 0
            state.last_failure_at = None
        
        # Transition HALF_OPEN back to CLOSED on success
        if state.state == CircuitState.HALF_OPEN:
            previous_state = state.state
            state.state = CircuitState.CLOSED
            state.opened_at = None
            state.auto_reset_at = None
            
            transition = StateTransition(
                timestamp=datetime.now(timezone.utc),
                from_state=previous_state,
                to_state=CircuitState.CLOSED,
                reason="Successful remediation after auto-reset",
                triggered_by="system"
            )
            state.history.append(transition)
            
            logger.info(f"Circuit breaker transitioned HALF_OPEN → CLOSED for {state.repository_id}")
        
        # Persist state
        self.database.store_circuit_breaker_state(state)

    def manual_reset(self, failure_signature: FailureSignature, reset_by: str) -> bool:
        """Manually reset circuit breaker"""
        state = self.get_state(failure_signature)
        
        if state.state != CircuitState.OPEN:
            logger.warning(f"Cannot reset circuit breaker for {state.repository_id} - "
                          f"not in OPEN state (current: {state.state})")
            return False
        
        previous_state = state.state
        state.state = CircuitState.CLOSED
        state.failure_count = 0
        state.manually_reset_at = datetime.now(timezone.utc)
        state.manually_reset_by = reset_by
        state.opened_at = None
        state.auto_reset_at = None
        
        transition = StateTransition(
            timestamp=datetime.now(timezone.utc),
            from_state=previous_state,
            to_state=CircuitState.CLOSED,
            reason="Manual reset",
            triggered_by=reset_by
        )
        state.history.append(transition)
        
        logger.info(f"Circuit breaker MANUALLY RESET for {state.repository_id} by {reset_by}")
        
        # Persist state
        self.database.store_circuit_breaker_state(state)
        
        return True

    def is_remediation_allowed(self, failure_signature: FailureSignature) -> bool:
        """Check if remediation is allowed for this failure"""
        state = self.get_state(failure_signature)
        
        # Check for auto-reset
        if state.state == CircuitState.OPEN and state.auto_reset_at:
            # Ensure safe comparison with potential naive datetimes from legacy data
            reset_at = state.auto_reset_at
            if reset_at.tzinfo is None:
                reset_at = reset_at.replace(tzinfo=timezone.utc)
            
            if datetime.now(timezone.utc) >= reset_at:
                # Auto-reset to HALF_OPEN
                previous_state = state.state
                state.state = CircuitState.HALF_OPEN
                
                transition = StateTransition(
                    timestamp=datetime.now(timezone.utc),
                    from_state=previous_state,
                    to_state=CircuitState.HALF_OPEN,
                    reason=f"Auto-reset after {self.auto_reset_hours} hours",
                    triggered_by="system"
                )
                state.history.append(transition)
                
                logger.info(f"Circuit breaker AUTO-RESET to HALF_OPEN for {state.repository_id}")
                
                # Persist state
                self.database.store_circuit_breaker_state(state)
        
        # Allow remediation if circuit is CLOSED or HALF_OPEN
        allowed = state.state in [CircuitState.CLOSED, CircuitState.HALF_OPEN]
        
        if not allowed:
            logger.warning(f"Remediation BLOCKED by circuit breaker for {state.repository_id} "
                          f"(state: {state.state}, failures: {state.failure_count})")
        
        return allowed

    def get_failure_count(self, failure_signature: FailureSignature) -> int:
        """Get current failure count"""
        state = self.get_state(failure_signature)
        return state.failure_count

    def list_open_circuits(self) -> List[CircuitBreakerState]:
        """List all open circuit breakers"""
        return [state for state in self.circuits.values() if state.state == CircuitState.OPEN]

    def get_circuit_status(self, repository: str) -> Dict[str, Any]:
        """Get circuit breaker status for a repository"""
        repo_circuits = [
            state for state in self.circuits.values()
            if state.repository_id == repository
        ]
        
        if not repo_circuits:
            return {
                "repository": repository,
                "status": "no_circuits",
                "message": "No circuit breakers active"
            }
        
        open_circuits = [c for c in repo_circuits if c.state == CircuitState.OPEN]
        
        return {
            "repository": repository,
            "total_circuits": len(repo_circuits),
            "open_circuits": len(open_circuits),
            "status": "frozen" if open_circuits else "active",
            "circuits": [c.to_dict() for c in repo_circuits]
        }
