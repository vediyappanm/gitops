# Configure Your Repositories

Your CI/CD Failure Monitor is running! Now you need to update it to monitor your actual repositories.

## Current Status

The agent is running and polling repositories, but it's currently set to monitor placeholder repositories:
- `owner/repo1`
- `owner/repo2`
- `owner/repo3`

These don't exist, so you're getting 404 errors. Let's fix that!

---

## Step 1: Update .env File

Edit `.env` and replace the placeholder repositories with your actual repositories:

**Before:**
```bash
REPOSITORIES=owner/repo1,owner/repo2,owner/repo3
```

**After:**
```bash
REPOSITORIES=your-org/your-repo1,your-org/your-repo2
```

**Examples:**
```bash
# Single repository
REPOSITORIES=mycompany/backend

# Multiple repositories
REPOSITORIES=mycompany/backend,mycompany/frontend,mycompany/api

# GitHub username
REPOSITORIES=myusername/my-project
```

---

## Step 2: Update config.json File

Edit `config.json` and update the repositories list:

**Before:**
```json
{
  "repositories": [
    {
      "owner": "owner",
      "name": "repo1",
      "branch": "main",
      "enabled": true
    },
    {
      "owner": "owner",
      "name": "repo2",
      "branch": "main",
      "enabled": true
    },
    {
      "owner": "owner",
      "name": "repo3",
      "branch": "main",
      "enabled": true
    }
  ]
}
```

**After:**
```json
{
  "repositories": [
    {
      "owner": "mycompany",
      "name": "backend",
      "branch": "main",
      "enabled": true
    },
    {
      "owner": "mycompany",
      "name": "frontend",
      "branch": "main",
      "enabled": true
    }
  ]
}
```

---

## Step 3: Restart the Agent

1. Stop the current agent: Press `Ctrl+C`
2. Start it again: `python main.py`

The agent will now monitor your actual repositories!

---

## Verify It's Working

### Check the Logs

```bash
tail -f logs/ci_cd_monitor.log
```

You should see:
```
Starting CI/CD Failure Monitor Agent for repositories: ['mycompany/backend', 'mycompany/frontend']
Polling GitHub Actions for failures...
```

### No More 404 Errors

Instead of:
```
404 Client Error: Not Found for url: https://api.github.com/repos/owner/repo1/...
```

You should see:
```
Polling repository mycompany/backend...
No failures found
```

---

## Repository Requirements

For the agent to work, your repositories need:

1. **GitHub Actions workflows** - The agent monitors workflow runs
2. **Workflow failures** - The agent detects when workflows fail
3. **GitHub token with access** - Your token must have access to the repository

### Check Your Token Permissions

Your GitHub token needs these scopes:
- `repo` - Full control of private repositories
- `workflow` - Full control of GitHub Actions workflows

To verify:
1. Go to https://github.com/settings/tokens
2. Find your token
3. Check that it has `repo` and `workflow` scopes

---

## Example Configurations

### Single Repository
```bash
# .env
REPOSITORIES=mycompany/api

# config.json
{
  "repositories": [
    {
      "owner": "mycompany",
      "name": "api",
      "branch": "main",
      "enabled": true
    }
  ]
}
```

### Multiple Repositories
```bash
# .env
REPOSITORIES=mycompany/backend,mycompany/frontend,mycompany/mobile

# config.json
{
  "repositories": [
    {
      "owner": "mycompany",
      "name": "backend",
      "branch": "main",
      "enabled": true
    },
    {
      "owner": "mycompany",
      "name": "frontend",
      "branch": "main",
      "enabled": true
    },
    {
      "owner": "mycompany",
      "name": "mobile",
      "branch": "main",
      "enabled": true
    }
  ]
}
```

### Different Branches
```bash
# .env
REPOSITORIES=mycompany/backend,mycompany/frontend

# config.json
{
  "repositories": [
    {
      "owner": "mycompany",
      "name": "backend",
      "branch": "main",
      "enabled": true
    },
    {
      "owner": "mycompany",
      "name": "frontend",
      "branch": "develop",
      "enabled": true
    }
  ]
}
```

---

## Troubleshooting

### Still Getting 404 Errors

**Check:**
1. Repository name is correct (case-sensitive)
2. Repository is public or your token has access
3. You've restarted the agent after updating `.env`

### Agent Not Detecting Failures

**Check:**
1. Repository has GitHub Actions workflows
2. Workflows have actually failed
3. Agent is running: `tail -f logs/ci_cd_monitor.log`

### Token Access Issues

**Check:**
1. Token is valid: `python test_configuration.py`
2. Token has `repo` and `workflow` scopes
3. Token hasn't expired

---

## Next Steps

1. **Update .env** with your repositories
2. **Update config.json** with your repositories
3. **Restart the agent**: `Ctrl+C` then `python main.py`
4. **Monitor the logs**: `tail -f logs/ci_cd_monitor.log`
5. **Wait for failures** - The agent will detect and handle them automatically

---

## What Happens Next

Once you've configured your repositories:

1. **Agent polls every 5 minutes** for workflow failures
2. **When a failure is detected**, it's analyzed with GPT-4o
3. **Classified as DEVOPS or DEVELOPER** issue
4. **Appropriate action is taken:**
   - Developer issue → Slack notification
   - DevOps issue → PR created with fix
5. **Everything is logged** for compliance

---

## Support

For help:
- Check logs: `tail -f logs/ci_cd_monitor.log`
- Run tests: `python test_configuration.py`
- Read docs: See `START_HERE.md`

---

## Summary

Your agent is running! Just update the repository names and it will start monitoring your actual projects. 🚀

```bash
# Edit .env
REPOSITORIES=your-org/your-repo

# Restart agent
python main.py
```

Done! 🎉
