# Your Goal: DevOps vs Developer Issue Detection & Auto-Fix

## Overview

Your system now automatically:
1. **Detects** if an error is a DevOps issue or Developer code issue
2. **For Developer issues**: Sends notification to Slack (no auto-fix)
3. **For DevOps issues**: Auto-fixes and creates a pull request on GitHub

---

## How It Works

### Step 1: Error Detection & Analysis

When a GitHub Actions workflow fails:

```
GitHub Actions Failure
    ↓
Monitor detects failure
    ↓
GPT-4o analyzes the error
    ↓
Classifies as: DEVOPS or DEVELOPER
```

### Step 2: Classification Logic

**GPT-4o determines error type based on:**

**DEVOPS Issues:**
- Infrastructure/deployment problems
- CI/CD configuration errors
- Dependency/package issues
- Timeout problems
- Environment configuration
- Docker/Kubernetes issues
- GitHub Actions workflow issues

Examples:
- "npm install timeout"
- "Docker build failed"
- "Kubernetes deployment timeout"
- "GitHub Actions runner out of memory"
- "Database connection timeout"

**DEVELOPER Issues:**
- Application code bugs
- Test failures
- Linting errors
- Compilation errors
- Logic errors in code

Examples:
- "Unit test failed: expected 5 but got 3"
- "TypeScript compilation error"
- "ESLint error: unused variable"
- "Jest test timeout"
- "Application crash in production"

---

## Workflow Paths

### Path A: Developer Issue Detected

```
Error occurs in GitHub Actions
    ↓
GPT-4o analyzes: "This is a DEVELOPER issue"
    ↓
Send Slack notification to developers
    ↓
Developers fix the code
    ↓
Push fix to repository
```

**Slack Notification Example:**
```
👨‍💻 Developer Code Issue Detected

Repository: myapp/repo
Branch: main
Category: test_failure
Confidence: 95%

Issue:
Unit test failed: expected 5 but got 3

Analysis:
The test is checking the sum function but the implementation 
returns incorrect value. This is a logic error in the code.

Suggested Fix:
Fix the sum function in src/utils/math.ts to return correct value
```

### Path B: DevOps Issue Detected

```
Error occurs in GitHub Actions
    ↓
GPT-4o analyzes: "This is a DEVOPS issue"
    ↓
Check safety gates (risk score, etc.)
    ↓
If safe: Create PR with fix
If risky: Request approval
    ↓
PR created on GitHub
    ↓
Developers review and merge
```

**Slack Notification Example:**
```
✅ DevOps Fix - PR Created

Repository: myapp/repo
Category: timeout
Risk Score: 3/10
Effort: low

Issue:
npm install timeout after 30 seconds

Fix:
Increase npm install timeout from 30s to 60s in .github/workflows/build.yml

View Pull Request: https://github.com/myapp/repo/pull/123
```

---

## Implementation Details

### 1. Error Type Detection (in Analyzer)

```python
# In src/analyzer.py
analysis = analyzer.analyze_failure(failure)

# Returns:
{
    "error_type": "DEVOPS",  # or "DEVELOPER"
    "category": "timeout",
    "risk_score": 3,
    "confidence": 92,
    "proposed_fix": "Increase timeout to 60s",
    "files_to_modify": [".github/workflows/build.yml"],
    "fix_commands": ["sed -i 's/timeout: 30/timeout: 60/' .github/workflows/build.yml"]
}
```

### 2. Decision Logic (in Agent)

```python
# In src/agent.py
if analysis.error_type == "DEVELOPER":
    # Send notification only
    agent._handle_developer_issue(failure, analysis)
else:
    # Auto-fix and create PR
    agent._handle_devops_issue(failure, analysis)
```

### 3. Developer Issue Handling

```python
def _handle_developer_issue(self, failure, analysis):
    # Send Slack notification
    notifier.send_developer_notification(failure, analysis)
    
    # Log action
    audit_logger.log_action(
        action_type=ActionType.DETECTION,
        actor="agent",
        details={
            "error_type": "DEVELOPER",
            "category": analysis.category.value
        },
        outcome="success"
    )
    
    # Update status
    failure.status = FailureStatus.ANALYZED
    db.store_failure(failure)
```

### 4. DevOps Issue Handling

```python
def _handle_devops_issue(self, failure, analysis):
    # Check safety gates
    safe, reason = safety_gate.validate_remediation(failure, analysis)
    
    if safe:
        # Create PR with fix
        success, pr_url = pr_creator.create_fix_pr(failure, analysis)
        
        # Send notification with PR link
        notifier.send_devops_fix_notification(failure, analysis, pr_url, success)
        
        # Update status
        failure.status = FailureStatus.REMEDIATED if success else FailureStatus.FAILED
    else:
        # Request approval for high-risk issues
        approval_workflow.request_approval(failure, analysis)
```

### 5. PR Creation (in PRCreator)

```python
# In src/pr_creator.py
def create_fix_pr(self, failure, analysis):
    # 1. Create new branch
    branch_name = self._create_branch(failure, analysis)
    
    # 2. Modify files with fix
    self._modify_files(failure, analysis, branch_name)
    
    # 3. Create pull request
    pr_url = self._create_pull_request(failure, analysis, branch_name)
    
    return True, pr_url
```

**PR Details:**
```
Title: 🔧 Fix CI failure: timeout

Body:
## Automated CI Failure Fix

**Failure Type:** DevOps Issue
**Category:** timeout
**Risk Score:** 3/10
**Confidence:** 92%

### Problem
npm install timeout after 30 seconds

### Root Cause
The npm install command is timing out because the CI environment 
is slow and 30 seconds is not enough time.

### Solution
Increase npm install timeout from 30s to 60s in .github/workflows/build.yml

### Files Modified
- .github/workflows/build.yml

---
This PR was automatically created by the CI/CD Failure Monitor Agent
Please review and merge if the fix looks correct
```

---

## Configuration

### Environment Variables

```bash
export GITHUB_TOKEN="ghp_..."           # GitHub token with repo access
export OPENAI_API_KEY="sk-..."          # OpenAI API key for GPT-4o
export SLACK_BOT_TOKEN="xoxb-..."       # Slack bot token
export REPOSITORIES="org/repo1,org/repo2"  # Repositories to monitor
```

### Config File (config.json)

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

---

## Complete End-to-End Examples

### Example 1: Developer Issue (Test Failure)

```
TIME: 10:00:00
┌─ GitHub Actions: Jest test failed
│
├─ 10:00:05 Monitor detects failure
│  └─ "Unit test failed: expected 5 but got 3"
│
├─ 10:00:10 Analyzer sends to GPT-4o
│  └─ Returns: error_type="DEVELOPER", category="test_failure"
│
├─ 10:00:15 Agent routes to developer handler
│  └─ Sends Slack notification to developers
│
└─ 10:00:20 Developers receive notification
   └─ Fix the test in their code and push
```

**Slack Message:**
```
👨‍💻 Developer Code Issue Detected

Repository: myapp/repo
Branch: main
Category: test_failure
Confidence: 95%

Issue:
Unit test failed: expected 5 but got 3

Analysis:
The test is checking the sum function but the implementation 
returns incorrect value. This is a logic error in the code.

Suggested Fix:
Fix the sum function in src/utils/math.ts to return correct value
```

---

### Example 2: DevOps Issue (Timeout)

```
TIME: 10:00:00
┌─ GitHub Actions: npm install timeout
│
├─ 10:00:05 Monitor detects failure
│  └─ "npm install timeout after 30 seconds"
│
├─ 10:00:10 Analyzer sends to GPT-4o
│  └─ Returns: error_type="DEVOPS", category="timeout", risk_score=3
│
├─ 10:00:15 Agent routes to DevOps handler
│  ├─ Safety gates: ✅ All pass
│  └─ Create PR with fix
│
├─ 10:00:20 PR Creator:
│  ├─ Creates branch: fix/ci-failure-abc123
│  ├─ Modifies .github/workflows/build.yml
│  │  └─ Changes: timeout: 30 → timeout: 60
│  └─ Creates pull request
│
└─ 10:00:25 Slack notification sent
   └─ ✅ DevOps Fix - PR Created
      View Pull Request: https://github.com/myapp/repo/pull/123
```

**Slack Message:**
```
✅ DevOps Fix - PR Created

Repository: myapp/repo
Category: timeout
Risk Score: 3/10
Effort: low

Issue:
npm install timeout after 30 seconds

Fix:
Increase npm install timeout from 30s to 60s in .github/workflows/build.yml

View Pull Request: https://github.com/myapp/repo/pull/123
```

---

### Example 3: High-Risk DevOps Issue (Requires Approval)

```
TIME: 10:00:00
┌─ GitHub Actions: Kubernetes deployment timeout
│
├─ 10:00:05 Monitor detects failure
│  └─ "Kubernetes deployment timeout"
│
├─ 10:00:10 Analyzer sends to GPT-4o
│  └─ Returns: error_type="DEVOPS", risk_score=8 (HIGH RISK)
│
├─ 10:00:15 Agent routes to DevOps handler
│  ├─ Safety gates: ❌ Risk score too high
│  └─ Request approval
│
├─ 10:00:20 Slack approval request sent
│  └─ [✅ Approve]  [❌ Reject]
│
├─ 10:00:30 DevOps engineer clicks Approve
│  ├─ Create PR with fix
│  └─ Send notification with PR link
│
└─ 10:00:35 Developers review and merge PR
```

**Slack Approval Message:**
```
⚠️ APPROVAL REQUIRED

Repository: critical/api
Workflow: Deploy
Risk Score: 8/10

Category: Infrastructure
Confidence: 92%

Proposed Fix:
Update Kubernetes deployment timeout from 5m to 10m in k8s/deployment.yaml

[✅ Approve]  [❌ Reject]
```

---

## Key Features

✅ **Automatic Classification**: GPT-4o determines if issue is DevOps or Developer  
✅ **Developer Notifications**: Slack alerts for code issues  
✅ **Auto-Fix for DevOps**: Creates PR automatically for infrastructure issues  
✅ **Safety Gates**: Validates risk before auto-fixing  
✅ **Approval Workflow**: High-risk issues require human approval  
✅ **Comprehensive Logging**: All actions audited and tracked  
✅ **Metrics Tracking**: Success rates and resolution times  

---

## Running the System

```bash
# 1. Set up environment
export GITHUB_TOKEN="ghp_..."
export OPENAI_API_KEY="sk-..."
export SLACK_BOT_TOKEN="xoxb-..."

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the agent
python main.py

# 4. Agent will:
#    - Poll GitHub Actions every 5 minutes
#    - Detect failures
#    - Classify as DevOps or Developer
#    - Send notifications or create PRs
#    - Log everything to database
```

---

## Summary

Your system now:

1. **Detects** GitHub Actions failures
2. **Analyzes** with GPT-4o to determine error type
3. **Routes** to appropriate handler:
   - **Developer issue** → Send Slack notification
   - **DevOps issue** → Auto-fix + Create PR
4. **Notifies** team via Slack with details
5. **Logs** everything for audit trail
6. **Tracks** metrics for monitoring

All automated, intelligent, and safe! 🚀
