import os
import logging
import uuid
from datetime import datetime
from dotenv import load_dotenv
from src.telegram_notifier import TelegramNotifier
from src.config_manager import ConfigurationManager
from src.models import FailureRecord, AnalysisResult, FailureStatus, FailureCategory

# Setup logging
logging.basicConfig(level=logging.INFO)

load_dotenv()

config = ConfigurationManager()
notifier = TelegramNotifier(os.getenv("TELEGRAM_BOT_TOKEN"), config)

# 1. Simulate a DEVELOPER issue (e.g., Code Bug)
dev_failure = FailureRecord(
    failure_id=f"dev-{str(uuid.uuid4())[:8]}",
    repository="vediyappanm/gitops",
    workflow_run_id="998877",
    branch="feature-login",
    commit_sha="dev123456",
    failure_reason="ValueError: invalid literal for int() with base 10: 'abc'",
    logs="Traceback: line 42, in process_data...",
    status=FailureStatus.ANALYZED,
    created_at=datetime.utcnow()
)

dev_analysis = AnalysisResult(
    failure_id=dev_failure.failure_id,
    error_type="DEVELOPER",
    category=FailureCategory.BUILD_ERROR,
    reasoning="The code is trying to convert a non-numeric string 'abc' into an integer without validation.",
    proposed_fix="Add a check for numeric strings before conversion: `if data.isdigit(): data = int(data)`",
    files_to_modify=["src/utils.py"],
    affected_components=["Core Logic"],
    fix_commands=[],
    risk_score=2,
    confidence=95,
    effort_estimate="Low",
    created_at=datetime.utcnow()
)

# 2. Simulate a DEVOPS issue (e.g., Missing Secret) - Auto-fixed
ops_failure = FailureRecord(
    failure_id=f"ops-{str(uuid.uuid4())[:8]}",
    repository="vediyappanm/gitops",
    workflow_run_id="554433",
    branch="main",
    commit_sha="ops654321",
    failure_reason="Error: GITHUB_TOKEN is not authorized to create tags",
    logs="Process exited with code 1...",
    status=FailureStatus.REMEDIATED,
    created_at=datetime.utcnow()
)

ops_analysis = AnalysisResult(
    failure_id=ops_failure.failure_id,
    error_type="DEVOPS",
    category=FailureCategory.CONFIG,
    reasoning="The workflow job lacks the necessary 'contents: write' permission to create a tag.",
    proposed_fix="Add `permissions: contents: write` to the workflow yaml file.",
    files_to_modify=[".github/workflows/ci.yml"],
    affected_components=["CI Pipeline"],
    fix_commands=[],
    risk_score=1,
    confidence=100,
    effort_estimate="Medium",
    created_at=datetime.utcnow()
)

# 3. Simulate an APPROVAL Request (High Risk DevOps fix)
risk_failure = FailureRecord(
    failure_id=f"risk-{str(uuid.uuid4())[:8]}",
    repository="vediyappanm/gitops",
    workflow_run_id="112233",
    branch="production",
    commit_sha="risk999",
    failure_reason="Critical dependency 'vulnerable-lib' needs update to v2.0",
    logs="Dependency check failed...",
    status=FailureStatus.ANALYZED,
    created_at=datetime.utcnow()
)

risk_analysis = AnalysisResult(
    failure_id=risk_failure.failure_id,
    error_type="DEVOPS",
    category=FailureCategory.DEPENDENCY,
    reasoning="Updating core dependency in production branch is high risk.",
    proposed_fix="Update `vulnerable-lib` in requirements.txt and run regression tests.",
    files_to_modify=["requirements.txt"],
    affected_components=["Production Env"],
    fix_commands=["pip install --upgrade vulnerable-lib"],
    risk_score=8,
    confidence=90,
    effort_estimate="High",
    created_at=datetime.utcnow()
)

print("--- Testing Developer Notification ---")
notifier.send_developer_notification(dev_failure, dev_analysis)

print("\n--- Testing DevOps Auto-fix Notification ---")
notifier.send_devops_fix_notification(ops_failure, ops_analysis, pr_url="https://github.com/vediyappanm/gitops/pull/1", success=True)

print("\n--- Testing High-Risk Approval Request ---")
notifier.send_approval_request(risk_failure, risk_analysis, request_id="req-456")

print("\n✅ Scenarios sent to Telegram. Please check your bot!")
