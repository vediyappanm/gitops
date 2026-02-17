# How the CI/CD Failure Monitor & Auto-Remediation Agent Works

## System Overview

The agent is an intelligent system that continuously monitors GitHub Actions workflows, analyzes failures using AI, and automatically fixes safe issues while escalating risky ones for human approval.

```
┌─────────────────────────────────────────────────────────────────┐
│                    CI/CD Failure Monitor Agent                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  GitHub Actions  ──→  Monitor  ──→  Analyzer  ──→  Safety Gate │
│  (Failures)           (Polls)       (GPT-4o)      (Validates)  │
│                                                         │        │
│                                                         ├─→ Safe?
│                                                         │        │
│                                    ┌────────────────────┴────┐   │
│                                    │                         │   │
│                                    ▼                         ▼   │
│                            Executor (Auto-Fix)    Approval Workflow
│                            (Executes Fix)         (Slack Approval)
│                                    │                         │   │
│                                    └────────────────────┬────┘   │
│                                                         │        │
│                                                         ▼        │
│                    Notifier (Slack) ◄─── Audit Logger & Metrics │
│                    (Notifications)      (Logging & Tracking)    │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Step-by-Step Workflow

### 1. **Failure Detection (Monitor Component)**

**What happens:**
- Agent polls GitHub Actions API every 5 minutes
- Looks for workflow runs with "failure" status
- Retrieves complete failure details (logs, commit, branch, etc.)

**Code flow:**
```python
# In monitor.py
monitor.poll_once(repositories)
  ├─ github_client.get_failed_workflow_runs(repo)
  ├─ Check if already processed (deduplication)
  └─ Extract failure reason from logs
     └─ Store in database
```

**Example:**
```
GitHub Actions: Build failed on main branch
  ↓
Monitor detects: "npm test failed - timeout"
  ↓
Creates FailureRecord with:
  - failure_id: "uuid-123"
  - repository: "myapp/repo"
  - branch: "main"
  - commit_sha: "abc123..."
  - failure_reason: "Test timeout after 30s"
  - logs: "[full workflow logs]"
```

---

### 2. **AI-Powered Analysis (Analyzer Component)**

**What happens:**
- Sends failure details to GPT-4o
- AI classifies the failure and assigns risk score
- Proposes specific remediation steps

**Code flow:**
```python
# In analyzer.py
analyzer.analyze_failure(failure)
  ├─ Build prompt with failure details
  ├─ Send to GPT-4o API
  ├─ Parse response (JSON)
  └─ Validate and store analysis
```

**GPT-4o analyzes and returns:**
```json
{
  "category": "timeout",
  "risk_score": 3,
  "confidence": 85,
  "proposed_fix": "Increase test timeout from 30s to 60s in jest.config.js",
  "effort_estimate": "low",
  "affected_components": ["jest", "test-suite"],
  "reasoning": "Tests are timing out due to slow CI environment..."
}
```

**Risk Score Meaning:**
- 0-2: Safe (cosmetic changes)
- 3-4: Low risk (test/dev changes)
- 5-6: Medium risk (feature code)
- 7-8: High risk (core logic)
- 9-10: Critical (security, data loss)

---

### 3. **Safety Validation (Safety Gate Component)**

**What happens:**
- Checks if remediation is safe to auto-execute
- Validates 3 safety gates

**Code flow:**
```python
# In safety_gate.py
safety_gate.validate_remediation(failure, analysis)
  ├─ Gate 1: Risk score < threshold?
  ├─ Gate 2: Not application code?
  └─ Gate 3: Not protected repository?
```

**Three Safety Gates:**

**Gate 1: Risk Score Check**
```
Risk Score: 3
Threshold: 5 (configurable)
Result: ✅ PASS (3 < 5)
```

**Gate 2: Application Code Detection**
```
Logs contain: "jest", "test", "timeout"
App keywords: ["test", "build", "compile"]
Result: ✅ PASS (only test code, not app code)
```

**Gate 3: Protected Repository Check**
```
Repository: "myapp/repo"
Protected repos: ["critical/api", "core/services"]
Result: ✅ PASS (not in protected list)
```

**Decision:**
- ✅ All gates pass → **Auto-remediate**
- ❌ Any gate fails → **Request approval**

---

### 4a. **Auto-Remediation Path (Safe Failures)**

**What happens:**
- Executor automatically applies the fix
- Captures output and verifies success
- Logs everything to audit trail

**Code flow:**
```python
# In executor.py
executor.execute_remediation(failure, analysis)
  ├─ Parse remediation steps
  ├─ Execute each step safely
  ├─ Capture output
  └─ Return success/failure
```

**Example execution:**
```
Proposed Fix: "Increase test timeout from 30s to 60s in jest.config.js"

Step 1: Parse fix into actionable commands
Step 2: Execute safely (only allowed commands)
Step 3: Capture output
Step 4: Verify fix worked

Result: ✅ SUCCESS
Output: "jest.config.js updated successfully"
```

**Notification sent to Slack:**
```
✅ Remediation Succeeded

Repository: myapp/repo
Workflow: Build
Category: timeout
Risk Score: 3/10

Result: Test timeout fixed by increasing timeout to 60s
```

---

### 4b. **Approval Path (High-Risk Failures)**

**What happens:**
- System sends approval request to Slack
- Includes interactive Approve/Reject buttons
- Waits for human decision

**Code flow:**
```python
# In approval_workflow.py
approval_workflow.request_approval(failure, analysis)
  ├─ Create ApprovalRequest
  ├─ Send Slack notification with buttons
  ├─ Store in database
  └─ Wait for response
```

**Slack Message Example:**
```
⚠️ APPROVAL REQUIRED

Repository: critical/api
Workflow: Deploy
Risk Score: 8/10

Category: Infrastructure
Confidence: 92%

Proposed Fix:
Update deployment timeout from 5m to 10m in terraform config

[✅ Approve]  [❌ Reject]
```

**When user clicks Approve:**
```python
approval_workflow.handle_approval(request_id, approver="user@company.com")
  ├─ Update approval status
  ├─ Record approver and timestamp
  ├─ Execute remediation
  └─ Send completion notification
```

**When user clicks Reject:**
```python
approval_workflow.handle_rejection(request_id, rejected_by="user@company.com")
  ├─ Update rejection status
  ├─ Log rejection reason
  └─ Send notification
```

---

### 5. **Notifications (Slack Notifier)**

**Notifications sent at each stage:**

**Stage 1: Initial Alert**
```
🚨 CI/CD Failure Detected

Repository: myapp/repo
Branch: main
Commit: abc123...
Reason: Test timeout after 30s
```

**Stage 2: Analysis Complete**
```
📊 Analysis Complete

Category: timeout
Risk Score: 3/10
Confidence: 85%
Effort: low

Proposed Fix: Increase test timeout to 60s
```

**Stage 3: Approval Request** (if needed)
```
⚠️ Approval Required

[Interactive buttons for Approve/Reject]
```

**Stage 4: Remediation Result**
```
✅ Remediation Succeeded
or
❌ Remediation Failed
```

---

### 6. **Audit Logging (Audit Logger)**

**Every action is logged:**

```python
# In audit_logger.py
audit_logger.log_action(
    action_type=ActionType.DETECTION,
    actor="monitor",
    details={"repository": "myapp/repo", "branch": "main"},
    outcome="success",
    failure_id="fail-123"
)
```

**Audit Trail Example:**
```
┌─────────────────────────────────────────────────────────────┐
│ Timestamp          │ Actor    │ Action      │ Outcome       │
├─────────────────────────────────────────────────────────────┤
│ 2024-01-15 10:00  │ monitor  │ DETECTION   │ success       │
│ 2024-01-15 10:01  │ analyzer │ ANALYSIS    │ success       │
│ 2024-01-15 10:02  │ safety   │ VALIDATION  │ success       │
│ 2024-01-15 10:03  │ executor │ REMEDIATION │ success       │
└─────────────────────────────────────────────────────────────┘
```

**Query audit logs:**
```python
logs = audit_logger.query_logs({
    "start_date": datetime(2024, 1, 1),
    "action_type": ActionType.REMEDIATION
})
```

---

### 7. **Metrics Tracking (Metrics Tracker)**

**Metrics collected:**

```python
# In metrics_tracker.py
metrics_tracker.record_detection_time(failure_id, 120)      # 120ms
metrics_tracker.record_analysis_time(failure_id, 2500)      # 2.5s
metrics_tracker.record_remediation_time(failure_id, 1000)   # 1s
metrics_tracker.record_remediation_result(
    failure_id, 
    success=True, 
    category="timeout",
    repository="myapp/repo",
    risk_score=3
)
```

**Metrics Dashboard:**
```
Success Rate: 94.2%
Average Resolution Time: 3.6 seconds
Risk Score Distribution:
  0-2:   12 failures (12%)
  3-4:   45 failures (45%)
  5-6:   28 failures (28%)
  7-8:   12 failures (12%)
  9-10:   3 failures (3%)

Category Distribution:
  timeout:       45 (45%)
  dependency:    28 (28%)
  config:        15 (15%)
  flaky_test:    10 (10%)
  infrastructure: 2 (2%)
```

---

## Configuration Management

**Configuration sources (in order of precedence):**

1. **Environment Variables** (highest priority)
   ```bash
   export GITHUB_TOKEN="ghp_..."
   export OPENAI_API_KEY="sk-..."
   export SLACK_BOT_TOKEN="xoxb-..."
   ```

2. **Configuration File** (config.json)
   ```json
   {
     "risk_threshold": 5,
     "protected_repositories": ["critical/api"],
     "slack_channels": {
       "alerts": "#ci-cd-alerts",
       "approvals": "#ci-cd-approvals",
       "critical": "#critical-alerts"
     },
     "approval_timeout_hours": 24,
     "polling_interval_minutes": 5
   }
   ```

3. **Per-Repository Overrides**
   ```json
   {
     "repository_configs": {
       "critical/api": {
         "risk_threshold": 3,
         "protected": true
       }
     }
   }
   ```

**Dynamic Reload:**
```python
config_manager.reload_configuration()  # Reloads without restart
```

---

## Error Handling & Recovery

**Error handling strategy:**

```python
# In error_handler.py
error_handler.retry_with_backoff(
    func=github_client.get_failed_workflow_runs,
    max_retries=3,
    initial_backoff=1,
    max_backoff=60
)
```

**Retry Logic:**
```
Attempt 1: FAIL (network timeout)
  ↓ Wait 1 second
Attempt 2: FAIL (rate limited)
  ↓ Wait 2 seconds
Attempt 3: SUCCESS ✅
```

**Critical Error Handling:**
```
Database connection fails
  ↓
Error detected as critical
  ↓
Send Slack alert: "🔴 CRITICAL: Database connection failed"
  ↓
Attempt automatic restart with exponential backoff
```

---

## Complete End-to-End Example

**Scenario: Test timeout in production API**

```
TIME: 10:00:00
┌─ GitHub Actions detects test timeout
│
├─ 10:00:05 Monitor polls and finds failure
│  └─ Creates FailureRecord
│
├─ 10:00:10 Analyzer sends to GPT-4o
│  └─ Returns: timeout, risk_score=3, "increase timeout"
│
├─ 10:00:15 Safety Gate validates
│  ├─ Risk score 3 < threshold 5 ✅
│  ├─ Not app code ✅
│  └─ Not protected repo ✅
│
├─ 10:00:20 Executor auto-fixes
│  └─ Updates jest.config.js timeout
│
├─ 10:00:25 Audit Logger records all actions
│  └─ 4 entries: detection, analysis, validation, remediation
│
├─ 10:00:30 Metrics Tracker updates
│  └─ Detection: 5ms, Analysis: 5s, Remediation: 10s
│
└─ 10:00:35 Slack notifications sent
   ├─ Initial alert
   ├─ Analysis result
   └─ Success notification
```

**Total time: 35 seconds from failure to fix**

---

## Key Design Principles

1. **Safety First**: Multiple validation gates prevent dangerous changes
2. **Transparency**: Every action logged and auditable
3. **Resilience**: Exponential backoff retry for transient failures
4. **Configurability**: Per-repository overrides and dynamic reload
5. **Observability**: Comprehensive metrics and audit trails
6. **Correctness**: 66 property-based tests validate system behavior

---

## Data Flow Diagram

```
GitHub Actions
     │
     ▼
┌─────────────┐
│   Monitor   │ ──→ Polls every 5 minutes
└─────────────┘
     │
     ▼ (FailureRecord)
┌─────────────┐
│  Database   │ ──→ Stores failures
└─────────────┘
     │
     ▼
┌─────────────┐
│  Analyzer   │ ──→ Sends to GPT-4o
└─────────────┘
     │
     ▼ (AnalysisResult)
┌─────────────┐
│ Safety Gate │ ──→ Validates safety
└─────────────┘
     │
     ├─→ Safe? ──→ Executor ──→ Auto-fix
     │
     └─→ Unsafe? ──→ Approval Workflow ──→ Slack approval
                           │
                           ▼
                    User clicks button
                           │
                    ┌──────┴──────┐
                    ▼             ▼
                 Approve       Reject
                    │             │
                    ▼             ▼
                 Executor      Log rejection
                    │
                    ▼
            ┌──────────────────┐
            │ Audit Logger     │ ──→ Log all actions
            │ Metrics Tracker  │ ──→ Track metrics
            │ Notifier         │ ──→ Send Slack alerts
            └──────────────────┘
```

---

## Summary

The agent works by:

1. **Detecting** failures via GitHub API polling
2. **Analyzing** failures using GPT-4o AI
3. **Validating** safety through multiple gates
4. **Deciding** whether to auto-fix or request approval
5. **Executing** fixes safely with output capture
6. **Notifying** teams via Slack at each stage
7. **Logging** everything for audit and compliance
8. **Tracking** metrics for monitoring and improvement

All components work together to provide intelligent, safe, and transparent CI/CD failure remediation.
