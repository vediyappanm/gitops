# Quick Start Guide - CI/CD Failure Monitor

## 30-Second Setup

Your system is already configured. Just run:

```bash
python main.py
```

That's it! The agent will start monitoring your repositories.

---

## What Happens When You Run It

### 1. Agent Starts
```
Starting CI/CD Failure Monitor Agent for repositories: ['owner/repo1', 'owner/repo2', 'owner/repo3']
```

### 2. Polls GitHub Every 5 Minutes
```
Polling GitHub Actions for failures...
Found 1 failure in owner/repo1
```

### 3. Analyzes the Failure
```
Analyzing failure: npm install timeout
Sending to GPT-4o for classification...
```

### 4. Classifies the Issue
```
Classification: DEVOPS issue
Risk Score: 3/10
Confidence: 92%
```

### 5. Takes Action

**If DEVELOPER issue:**
```
Sending Slack notification to developers...
✅ Notification sent
```

**If DEVOPS issue:**
```
Creating PR with fix...
✅ PR created: https://github.com/owner/repo1/pull/123
Sending Slack notification with PR link...
```

---

## Example Scenarios

### Scenario 1: Test Failure (Developer Issue)

**What happens:**
```
GitHub Actions: Jest test failed
    ↓
Monitor detects: "Unit test failed: expected 5 but got 3"
    ↓
Analyzer: "This is a DEVELOPER issue"
    ↓
Slack notification sent to developers
    ↓
Developers fix the code and push
```

**Slack Message:**
```
👨‍💻 Developer Code Issue Detected

Repository: owner/repo1
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

### Scenario 2: Timeout (DevOps Issue)

**What happens:**
```
GitHub Actions: npm install timeout
    ↓
Monitor detects: "npm install timeout after 30 seconds"
    ↓
Analyzer: "This is a DEVOPS issue"
    ↓
Safety gates: ✅ All pass (risk score: 3/10)
    ↓
Create PR with fix
    ↓
Slack notification with PR link
    ↓
Developers review and merge
```

**Slack Message:**
```
✅ DevOps Fix - PR Created

Repository: owner/repo1
Category: timeout
Risk Score: 3/10
Effort: low

Issue:
npm install timeout after 30 seconds

Fix:
Increase npm install timeout from 30s to 60s in .github/workflows/build.yml

View Pull Request: https://github.com/owner/repo1/pull/123
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

### Scenario 3: High-Risk Issue (Requires Approval)

**What happens:**
```
GitHub Actions: Kubernetes deployment timeout
    ↓
Monitor detects: "Kubernetes deployment timeout"
    ↓
Analyzer: "This is a DEVOPS issue"
    ↓
Safety gates: ❌ Risk score too high (8/10)
    ↓
Request approval
    ↓
Slack approval request sent
    ↓
DevOps engineer approves
    ↓
Create PR with fix
    ↓
Slack notification with PR link
```

**Slack Approval Message:**
```
⚠️ APPROVAL REQUIRED

Repository: owner/critical-api
Workflow: Deploy
Risk Score: 8/10

Category: Infrastructure
Confidence: 92%

Proposed Fix:
Update Kubernetes deployment timeout from 5m to 10m in k8s/deployment.yaml

[✅ Approve]  [❌ Reject]
```

---

## Monitoring the Agent

### View Live Logs
```bash
tail -f ci_cd_monitor.log
```

### Check for Errors
```bash
grep ERROR ci_cd_monitor.log
```

### View Specific Repository
```bash
grep "owner/repo1" ci_cd_monitor.log
```

---

## Stopping the Agent

Press `Ctrl+C` to stop:
```bash
^C
Agent interrupted by user
```

---

## Troubleshooting

### Agent won't start

**Check logs:**
```bash
python test_configuration.py
```

**Common issues:**
- Missing `.env` file
- Invalid credentials
- Database locked
- Port already in use

### No failures detected

**Check:**
1. Repositories are configured in `config.json`
2. GitHub token has `repo` and `workflow` scopes
3. Repositories actually have workflow failures
4. Polling interval is set correctly (default: 5 minutes)

### Slack notifications not working

**Check:**
1. Slack bot token is valid
2. Bot has permission to post in channels
3. Channel names in `config.json` are correct
4. Bot is invited to the channels

### PRs not being created

**Check:**
1. GitHub token has `repo` scope
2. Repository is not protected
3. Risk score is below threshold
4. Safety gates are passing

---

## Configuration

### Update Repositories

Edit `.env`:
```bash
REPOSITORIES=your-org/repo1,your-org/repo2,your-org/repo3
```

### Update Slack Channels

Edit `config.json`:
```json
{
  "slack_channels": {
    "alerts": "#your-alerts-channel",
    "approvals": "#your-approvals-channel",
    "critical": "#your-critical-channel"
  }
}
```

### Adjust Risk Threshold

Edit `config.json`:
```json
{
  "risk_threshold": 5  // 0-10, higher = more auto-fixes
}
```

### Change Polling Interval

Edit `config.json`:
```json
{
  "polling_interval_minutes": 5  // Check every 5 minutes
}
```

---

## Key Metrics

The system tracks:
- Total failures detected
- Failures analyzed
- Issues classified as DEVOPS vs DEVELOPER
- PRs created
- Notifications sent
- Average resolution time
- Success rate

View metrics in database:
```bash
sqlite3 ci_cd_monitor.db "SELECT * FROM metrics;"
```

---

## Next Steps

1. **Start the agent:**
   ```bash
   python main.py
   ```

2. **Monitor Slack** for notifications

3. **Review PRs** created by the agent

4. **Check logs** for any issues:
   ```bash
   tail -f ci_cd_monitor.log
   ```

5. **Adjust configuration** as needed

---

## Support

For detailed information:
- **How it works:** See `HOW_IT_WORKS.md`
- **Implementation details:** See `YOUR_GOAL_IMPLEMENTATION.md`
- **Setup guide:** See `SETUP_GUIDE.md`
- **System status:** See `SYSTEM_READY.md`

---

## Summary

Your CI/CD Failure Monitor is ready to:
- ✅ Monitor GitHub Actions workflows
- ✅ Analyze failures with AI
- ✅ Classify as DevOps or Developer issues
- ✅ Send notifications for developer issues
- ✅ Auto-fix and create PRs for DevOps issues
- ✅ Track everything with comprehensive logging

**Start now:**
```bash
python main.py
```

Let the agent handle your CI/CD failures automatically! 🚀
