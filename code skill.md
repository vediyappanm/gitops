# 🏭 PRODUCTION-GRADE CODE SKILL
> Give this file to any AI (Claude, Kiro, Copilot) before writing code.
> This skill enforces production-grade standards on every file generated.

---

## 🎯 WHO THIS IS FOR
This project is a **CI/CD Failure Monitor & Auto-Remediation Agent** built in Python.
- Multi-teammate GitHub repo environment (main + feature branches per teammate)
- Agent watches teammate branches, detects errors, creates fix branches, raises PRs
- Uses: GPT-4o / Claude for AI analysis, GitHub API, Slack, SQLAlchemy, SQLite/Postgres

---

## ⚙️ CORE RULE — NEVER VIOLATE THESE

```
1. NEVER write placeholder code. No "# TODO", no "pass", no "In a real implementation..."
2. NEVER leave a function body empty or with just a log statement
3. EVERY function must be fully implemented, end-to-end, working code only
4. EVERY error path must be handled — not just the happy path
5. NEVER assume a method exists on another class — define it or show the interface
6. ALWAYS write type hints on every function signature
7. ALWAYS write docstrings on every class and public method
8. NEVER use print() — always use the logging module
9. ALWAYS use dataclasses or Pydantic models for structured data — no raw dicts
10. ALWAYS validate inputs at the top of every function before doing any work
```

---

## 📁 FILE STRUCTURE RULES

Every file you write MUST follow this structure — no exceptions:

```python
"""Module docstring — one line summary of what this file does"""
# Standard library imports
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

# Third party imports
from github import Github  # example

# Local imports
from src.models import MyModel

# Logger — always at module level, never inside functions
logger = logging.getLogger(__name__)


# Constants — UPPERCASE, at top of file
MAX_RETRIES = 3
DEFAULT_TIMEOUT = 30


class MyClass:
    """
    One-line summary.
    
    Longer description if needed. Explain what this class owns,
    what it does, and what it does NOT do.
    """

    def __init__(self, dependency_a, dependency_b):
        """Initialize with injected dependencies — never instantiate deps inside __init__"""
        self.dep_a = dependency_a
        self.dep_b = dependency_b
        logger.info(f"MyClass initialized")

    def my_method(self, param: str) -> Optional[str]:
        """
        One-line summary of what this method does.
        
        Args:
            param: What this parameter is
            
        Returns:
            What this returns, and when it returns None
            
        Raises:
            ValueError: When param is invalid
            RuntimeError: When something goes wrong at runtime
        """
        # 1. Always validate inputs first
        if not param or not isinstance(param, str):
            raise ValueError(f"param must be a non-empty string, got: {type(param)}")
        
        # 2. Do the actual work
        try:
            result = self.dep_a.do_something(param)
            logger.info(f"my_method succeeded for param={param!r}")
            return result
        except SpecificException as e:
            logger.error(f"my_method failed for param={param!r}: {e}")
            raise RuntimeError(f"Failed to process {param}") from e
```

---

## 🌿 BRANCH-AWARE CODE RULES (Project Specific)

This project operates on **teammate branches**, NOT main. Every component that touches GitHub MUST:

```python
# ❌ WRONG — never branch from main
ref = repo.get_branch("main")

# ✅ CORRECT — always branch from the broken teammate branch
def create_fix_branch(self, repo_name: str, broken_branch: str) -> str:
    """Create agent fix branch from broken teammate branch — NOT from main."""
    repo = self.github.get_repo(repo_name)
    broken_ref = repo.get_branch(broken_branch)
    broken_sha = broken_ref.commit.sha  # SHA from BROKEN branch
    
    fix_branch = f"agent-fix/{broken_branch}-{int(time.time())}"
    repo.create_git_ref(
        ref=f"refs/heads/{fix_branch}",
        sha=broken_sha  # ← from broken branch, not main
    )
    return fix_branch

# ❌ WRONG — never PR back to main
pr = repo.create_pull(base="main", head=fix_branch)

# ✅ CORRECT — PR back to teammate's branch
pr = repo.create_pull(
    base=broken_branch,   # ← back to teammate branch
    head=fix_branch,
    title=f"🤖 Agent Fix: {broken_branch}"
)
```

---

## 🔁 ERROR HANDLING RULES

Every function that calls an external service (GitHub API, OpenAI, Slack, DB) MUST use this pattern:

```python
import time
from functools import wraps

def retry_with_backoff(max_retries: int = 3, backoff_factor: float = 2.0):
    """Decorator for exponential backoff retry."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except RateLimitException as e:
                    wait = backoff_factor ** attempt
                    logger.warning(f"Rate limited on attempt {attempt+1}, waiting {wait}s")
                    time.sleep(wait)
                    last_exception = e
                except AuthenticationError as e:
                    logger.error(f"Auth error — not retrying: {e}")
                    raise  # Never retry auth errors
                except Exception as e:
                    wait = backoff_factor ** attempt
                    logger.warning(f"Attempt {attempt+1} failed: {e}, retrying in {wait}s")
                    time.sleep(wait)
                    last_exception = e
            raise RuntimeError(f"All {max_retries} attempts failed") from last_exception
        return wrapper
    return decorator
```

---

---

## 🕒 DATE & TIME HANDLING RULES

**Strictly Enforced Rule:** ALL timestamp operations must be timezone-aware (UTC).

*   **❌ BANNED:** `datetime.utcnow()` (Deprecated, returns naive datetime)
*   **❌ BANNED:** `datetime.now()` (Returns naive local time)
*   **❌ BANNED:** `Column(DateTime)` (Stores naive timestamp, breaks in Postgres)

*   **✅ REQUIRED:**

```python
from datetime import datetime, timezone

# Current time
now_utc = datetime.now(timezone.utc)

# Database Columns
created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
```

---

## 🗄️ DATABASE RULES

Every database method MUST be fully implemented — no stubs:

```python
def store_snapshot(self, snapshot: Snapshot) -> bool:
    """Persist snapshot to database."""
    try:
        with self.session_factory() as session:
            record = SnapshotRecord(
                id=snapshot.id,
                repository_id=snapshot.repository_id,
                remediation_id=snapshot.remediation_id,
                commit_sha=snapshot.commit_sha,
                branch_name=snapshot.branch_name,
                data=json.dumps(snapshot.to_dict()),
                created_at=snapshot.created_at,
                expires_at=snapshot.expires_at,
                status=snapshot.status.value
            )
            session.merge(record)  # upsert
            session.commit()
            logger.debug(f"Snapshot {snapshot.id} stored")
            return True
    except SQLAlchemyError as e:
        logger.error(f"Failed to store snapshot {snapshot.id}: {e}")
        return False
```

---

## 🔒 SAFETY GATE RULES

Every remediation MUST pass through this checklist before execution:

```python
@dataclass
class SafetyCheckResult:
    allowed: bool
    reason: str
    risk_score: int
    checks_passed: List[str]
    checks_failed: List[str]

# MANDATORY checks before any remediation:
# 1. risk_score <= threshold for that repo
# 2. circuit breaker is CLOSED or HALF_OPEN
# 3. branch is NOT main, master, or protected
# 4. dry_run mode is OFF
# 5. snapshot created successfully before execution
```

---

## 📊 STATE MACHINE RULES

Every state machine MUST implement ALL transitions — no missing edges:

```python
# CircuitBreaker MUST implement:
# CLOSED  → OPEN      (on failure_count >= threshold)
# OPEN    → HALF_OPEN (on auto_reset timer expiry)
# HALF_OPEN → CLOSED  (on successful remediation)  ← DON'T FORGET THIS
# HALF_OPEN → OPEN    (on failure during half-open) ← DON'T FORGET THIS
# ANY     → CLOSED    (on manual reset by human)

def record_success(self, sig: FailureSignature) -> None:
    """On success: reset count AND close circuit if HALF_OPEN."""
    state = self.get_state(sig)
    state.failure_count = 0
    # ✅ Must transition HALF_OPEN → CLOSED on success
    if state.state == CircuitState.HALF_OPEN:
        state.state = CircuitState.CLOSED
        logger.info(f"Circuit CLOSED after successful remediation: {state.repository_id}")
    self.database.store_circuit_breaker_state(state)
```

---

## 🔔 NOTIFICATION RULES

Every Slack notification MUST include:
- Which repo and which branch had the issue
- Which teammate owns that branch
- What the AI decided and why (brief)
- Risk score
- What action was taken (or blocked)
- Link to the PR or audit log

```python
def build_alert_message(self, failure: WorkflowFailure, analysis: Analysis) -> str:
    return (
        f"*🚨 CI Failure Detected*\n"
        f"*Repo:* `{failure.repository}`\n"
        f"*Branch:* `{failure.branch}` (owner: {failure.branch_owner})\n"
        f"*Workflow:* `{failure.workflow_name}`\n"
        f"*Risk Score:* {analysis.risk_score}/10\n"
        f"*AI Decision:* {analysis.category} — {analysis.summary}\n"
        f"*Action:* {analysis.proposed_action}\n"
        f"*PR:* {failure.pr_url or 'Pending'}"
    )
```

---

## ✅ CHECKLIST — Before Submitting Any File

Run through this mentally before finishing any file:

```
[ ] Every function is FULLY implemented — zero placeholders
[ ] Every function has type hints on all params and return type
[ ] Every function has a docstring
[ ] Every external call is wrapped in try/except with specific exception types
[ ] Every state machine has ALL transitions implemented
[ ] Every DB method is real SQL/ORM — not a stub
[ ] Branch operations use teammate branch SHA — not main
[ ] PRs target teammate branch — not main
[ ] logging used everywhere — no print()
[ ] Input validation at top of every function
[ ] Dataclasses/Pydantic used for all structured data
[ ] No raw Dict[str, Any] passed between components — use typed models
[ ] circuit breaker HALF_OPEN → CLOSED transition on success is present
[ ] Rollback uses real github_client.update_file() — not a comment
[ ] DryRunMode has intercept_file_modification() method defined
```

---

## 🚫 BANNED PATTERNS — NEVER WRITE THESE

```python
# ❌ BANNED
pass

# ❌ BANNED  
# TODO: implement this

# ❌ BANNED
# In a real implementation, this would...

# ❌ BANNED
raise NotImplementedError

# ❌ BANNED
print(f"something happened")

# ❌ BANNED — branching from main
repo.get_branch("main").commit.sha

# ❌ BANNED — PR to main
repo.create_pull(base="main", ...)

# ❌ BANNED — bare except
try:
    ...
except:
    pass

# ❌ BANNED — swallowing exceptions silently
except Exception:
    return None

# ❌ BANNED — missing HALF_OPEN → CLOSED transition
def record_success(self):
    self.failure_count = 0  # ← missing state transition!
```

---

## 📦 APPROVED LIBRARIES FOR THIS PROJECT

```
openai          → GPT-4o analysis
anthropic       → Claude fallback analyzer  
litellm         → Multi-LLM router (OpenAI + Claude + Gemini)
PyGithub        → GitHub API client
slack-sdk       → Slack notifications
sqlalchemy      → Database ORM
alembic         → DB migrations
pinecone-client → Vector DB for failure pattern memory
apscheduler     → Background job scheduling (cleanup, health reports)
httpx           → Async HTTP with timeout/retry
pydantic        → Data validation and models
pytest          → Testing
hypothesis      → Property-based testing
python-dotenv   → Environment variable management
```

---

## 🧪 TESTING RULES

Every new component MUST have:

```python
# 1. Unit test for happy path
def test_create_fix_branch_success():
    ...

# 2. Unit test for each error path
def test_create_fix_branch_rate_limited():
    ...

# 3. Property-based test for invariants
@given(st.text(min_size=1))
def test_fix_branch_always_targets_broken_branch_not_main(branch_name):
    ...
    assert result.base != "main"
    assert result.base != "master"
```

---

*Last updated: 2026 | Project: CI/CD Failure Monitor & Auto-Remediation Agent*
*Use with: Claude Sonnet 4.6, Claude Haiku 4.5, Kiro Code, GitHub Copilot*