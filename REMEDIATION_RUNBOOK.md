# CI/CD Failure Monitor - Remediation Runbook

This document outlines the common failure patterns detected by the Auto-Remediation Agent and the standard procedures for handling them.

## 📊 Overview
The agent automatically categorizes failures into **DEVOPS** (Auto-fixed via PR) and **DEVELOPER** (Notification only). 

---

## 🔍 Common Failure Patterns

### 1. Missing Dependencies / Path Mismatches (DEVOPS)
- **Symptom:** `ERROR: Could not open requirements file: [Errno 2] No such file or directory`
- **Root Cause:** Workflow file references a path that doesn't exist or was moved.
- **Auto-Fix:** Agent updates the `.github/workflows/*.yml` to point to the correct path.
- **Action:** Review the PR created by the agent and merge if the path is verified.

### 2. Environment Variable Configuration (DEVOPS)
- **Symptom:** `KeyError: 'GITHUB_TOKEN'` or `Missing optional dependency 'slack-sdk'`
- **Root Cause:** Secrets or environment variables are missing from the CI environment.
- **Auto-Fix:** Agent adds missing `env:` mapping to the workflow step.
- **Action:** Ensure the corresponding Secret is added to GitHub Repository Settings.

### 3. Application Logic Bugs (DEVELOPER)
- **Symptom:** `AssertionError`, `IndexError`, or specific test failures in `src/`.
- **Root Cause:** Recent commit introduced a bug in the application code.
- **Action:** Review the Slack notification details. The agent provides the exact file, line, and log snippet. Fix the code manually.

### 4. Linting & Formatting Violations (DEVELOPER/DEVOPS)
- **Symptom:** `flake8` or `black` exit with non-zero status.
- **Root Cause:** Code does not adhere to style guidelines.
- **Action:** Run `black .` or `flake8` locally, fix the issues, and push again.

### 5. Infrastructure / API Issues (DEVOPS)
- **Symptom:** `403 Forbidden` (GitHub API), `Timeout error` connecting to external services.
- **Root Cause:** Permission issues or temporary network instability.
- **Action:** Check if the `GITHUB_TOKEN` has sufficient scopes (`repo` scope required). Restart the workflow if it appears to be a transient network issue.

---

## 🛠️ Operating the Agent

### Monitoring Performance
- View the **Grafana Dashboard** (Port 3000) for real-time KPIs.
- Key Metrics to watch: **Auto-fix Rate**, **Mean Time to Resolution (MTTR)**.

### Providing Feedback
When you receive a Slack notification, please use the interactive buttons:
- **✅ Yes**: Confirm classification is correct.
- **❌ No - It's DevOps**: Fix misclassification for infra/config issues.
- **❌ No - It's Developer**: Fix misclassification for code-level issues.

*Feedback is stored in the database and used to retrain the underlying prompts.*

---

## 🚨 Troubleshooting the Agent
- **Logs:** Check `logs/ci_cd_monitor.log` for agent errors.
- **Parsing Errors:** If you see "Analysis parsing failed", it usually means the Groq API returned malformed JSON. The latest update includes a multi-strategy parser to mitigate this.
- **Safety Gate Blocking:** If a PR isn't created, check the Audit Logs in the database. The **Safety Gate** will block changes with a Risk Score > 9 or changes to protected repositories.
