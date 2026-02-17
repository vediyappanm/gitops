# CI/CD Failure Monitor & Auto-Remediation Agent - Setup Guide

## System Overview

Your CI/CD Failure Monitor is a fully automated system that:

1. **Monitors** GitHub Actions workflows for failures
2. **Analyzes** failures using GPT-4o to determine if they're DevOps or Developer issues
3. **Routes** appropriately:
   - **Developer issues** → Sends Slack notification
   - **DevOps issues** → Auto-fixes and creates pull request
4. **Tracks** everything with comprehensive logging and metrics

---

## Prerequisites

- Python 3.8+
- GitHub account with repository access
- OpenRouter API key (for GPT-4o access)
- Slack workspace with bot token
- SQLite (included with Python)

---

## Installation

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Environment Configuration

The `.env` file is already configured with your credentials:

```bash
# GitHub Configuration
GITHUB_TOKEN=your_github_personal_access_token_here

# OpenRouter Configuration
OPENROUTER_API_KEY=your_openrouter_api_key_here

# Slack Configuration
SLACK_BOT_TOKEN=xoxb-your-slack-bot-token-here

# Application Configuration
CONFIG_FILE=config.json
DATABASE_URL=sqlite:///ci_cd_monitor.db
LOG_LEVEL=INFO

# Repositories to monitor (comma-separated)
REPOSITORIES=owner/repo1,owner/repo2,owner/repo3
```

### 3. Update Repository Configuration

Edit `config.json` to specify which repositories to monitor:

```json
{
  "repositories": [
    {
      "owner": "your-org",
      "name": "your-repo",
      "branch": "main",
      "enabled": true
    }
  ]
}
```

---

## Verification

### Run Configuration Tests

Before starting the agent, verify all connections are working:

```bash
python test_configuration.py
```

Expected output:
```
✅ PASS: Environment Variables
✅ PASS: GitHub Connection
✅ PASS: OpenRouter Connection
✅ PASS: Slack Connection
✅ PASS: Database
✅ PASS: Configuration

✅ All tests passed! System is ready to run.
```

---

## Running the Agent

### Start the Monitor

```bash
python main.py
```

The agent will:
1. Load configuration from `config.json`
2. Initialize database
3. Start polling GitHub Actions every 5 minutes
4. Detect failures and analyze them
5. Send notifications or create PRs as needed

### Example Output

```
2026-02-13 07:50:00 - __main__ - INFO - Starting CI/CD Failure Monitor Agent for repositories: ['owner/repo1', 'owner/repo2', 'owner/repo3']
2026-02-13 07:50:05 - src.monitor - INFO - Polling GitHub Actions for failures...
2026-02-13 07:50:10 - src.monitor - INFO - Found 1 failure in owner/repo1
2026-02-13 07:50:15 - src.analyzer - INFO - Analyzing failure: npm install timeout
2026-02-13 07:50:20 - src.analyzer - INFO - Analysis completed: DEVOPS issue (risk_score=3)
2026-02-13 07:50:25 - src.pr_creator - INFO - Creating PR for fix...
2026-02-13 07:50:30 - src.notifier - INFO - Sending Slack notification with PR link
```

---

## How It Works

### Workflow for Developer Issues

```
GitHub Actions Failure (e.g., test failure)
    ↓
Monitor detects failure
    ↓
Analyzer sends to GPT-4o
    ↓
GPT-4o classifies as: DEVELOPER
    ↓
Agent sends Slack notification to developers
    ↓
Developers fix the code and push
```

**Slack Notification:**
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

### Workflow for DevOps Issues

```
GitHub Actions Failure (e.g., npm install timeout)
    ↓
Monitor detects failure
    ↓
Analyzer sends to GPT-4o
    ↓
GPT-4o classifies as: DEVOPS
    ↓
Safety gates validate risk
    ↓
If safe: Create PR with fix
If risky: Request approval
    ↓
PR created on GitHub
    ↓
Developers review and merge
```

**Slack Notification:**
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

---

## System Components

### Core Components

1. **Monitor** (`src/monitor.py`)
   - Polls GitHub Actions for workflow failures
   - Detects new failures every 5 minutes
   - Stores failures in database

2. **Analyzer** (`src/analyzer.py`)
   - Sends failures to GPT-4o for analysis
   - Classifies as DEVOPS or DEVELOPER
   - Extracts proposed fixes and risk scores

3. **Safety Gate** (`src/safety_gate.py`)
   - Validates remediation safety
   - Checks risk scores and protected repositories
   - Prevents dangerous auto-fixes

4. **PR Creator** (`src/pr_creator.py`)
   - Creates new branches for fixes
   - Modifies files with proposed fixes
   - Creates pull requests on GitHub

5. **Notifier** (`src/notifier.py`)
   - Sends Slack notifications
   - Handles developer and DevOps notifications
   - Includes PR links and details

6. **Approval Workflow** (`src/approval_workflow.py`)
   - Handles high-risk issues requiring approval
   - Manages approval requests and responses
   - Executes fixes after approval

7. **Executor** (`src/executor.py`)
   - Executes fix commands
   - Handles command execution and error handling
   - Logs execution results

8. **Audit Logger** (`src/audit_logger.py`)
   - Logs all actions for compliance
   - Tracks who did what and when
   - Maintains audit trail

9. **Metrics Tracker** (`src/metrics_tracker.py`)
   - Tracks success rates
   - Measures resolution times
   - Provides performance insights

10. **Agent** (`src/agent.py`)
    - Main orchestrator
    - Routes issues to appropriate handlers
    - Coordinates all components

---

## Configuration Options

### config.json

```json
{
  "risk_threshold": 5,                    // Max risk score for auto-fix (0-10)
  "protected_repositories": [],           // Repos that require approval
  "slack_channels": {
    "alerts": "#ci-cd-alerts",           // General alerts
    "approvals": "#ci-cd-approvals",     // Approval requests
    "critical": "#critical-alerts"       // Critical issues
  },
  "approval_timeout_hours": 24,          // How long to wait for approval
  "polling_interval_minutes": 5,         // How often to check for failures
  "repositories": [                       // Repositories to monitor
    {
      "owner": "your-org",
      "name": "your-repo",
      "branch": "main",
      "enabled": true
    }
  ]
}
```

---

## Troubleshooting

### Issue: "No repositories configured"

**Solution:** Set the `REPOSITORIES` environment variable:
```bash
export REPOSITORIES=owner/repo1,owner/repo2
```

### Issue: "OpenRouter API error"

**Solution:** Verify your API key:
1. Go to https://openrouter.io/keys
2. Check that your API key is valid and active
3. Ensure you have credits available

### Issue: "GitHub authentication failed"

**Solution:** Verify your GitHub token:
1. Go to https://github.com/settings/tokens
2. Check that your token has `repo` and `workflow` scopes
3. Ensure the token hasn't expired

### Issue: "Slack authentication failed"

**Solution:** Verify your Slack bot token:
1. Go to your Slack workspace settings
2. Check that the bot token is valid
3. Ensure the bot has permission to post messages

---

## Monitoring the Agent

### View Logs

```bash
# Real-time logs
tail -f ci_cd_monitor.log

# Filter for errors
grep ERROR ci_cd_monitor.log

# Filter for specific repository
grep "owner/repo1" ci_cd_monitor.log
```

### Check Database

```bash
# View failures
sqlite3 ci_cd_monitor.db "SELECT * FROM failures;"

# View analyses
sqlite3 ci_cd_monitor.db "SELECT * FROM analyses;"

# View audit logs
sqlite3 ci_cd_monitor.db "SELECT * FROM audit_logs;"
```

---

## Next Steps

1. **Update REPOSITORIES** in `.env` with your actual repositories
2. **Update config.json** with your repository details
3. **Run test_configuration.py** to verify all connections
4. **Start the agent** with `python main.py`
5. **Monitor Slack** for notifications
6. **Review PRs** created by the agent

---

## Support

For issues or questions:
1. Check the logs: `tail -f ci_cd_monitor.log`
2. Run tests: `python test_configuration.py`
3. Review the design: `HOW_IT_WORKS.md`
4. Check implementation details: `YOUR_GOAL_IMPLEMENTATION.md`

---

## Summary

Your CI/CD Failure Monitor is now configured and ready to:
- ✅ Monitor GitHub Actions workflows
- ✅ Analyze failures with AI
- ✅ Classify as DevOps or Developer issues
- ✅ Send notifications for developer issues
- ✅ Auto-fix and create PRs for DevOps issues
- ✅ Track everything with comprehensive logging

Start the agent and let it handle your CI/CD failures automatically!
