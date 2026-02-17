# CI/CD Failure Monitor - Run Commands

## Quick Reference

### Start the Agent
```bash
python main.py
```

### Verify Configuration
```bash
python test_configuration.py
```

### View Logs
```bash
tail -f ci_cd_monitor.log
```

---

## Step-by-Step Commands

### 1. Verify Everything is Working

```bash
python test_configuration.py
```

**Expected output:**
```
✅ PASS: Environment Variables
✅ PASS: GitHub Connection
✅ PASS: OpenRouter Connection
✅ PASS: Slack Connection
✅ PASS: Database
✅ PASS: Configuration

✅ All tests passed! System is ready to run.
```

### 2. Start the Agent

```bash
python main.py
```

**Expected output:**
```
Starting CI/CD Failure Monitor Agent for repositories: ['owner/repo1', 'owner/repo2', 'owner/repo3']
```

### 3. Monitor in Real-Time

In a new terminal:
```bash
tail -f ci_cd_monitor.log
```

### 4. Stop the Agent

Press `Ctrl+C` in the terminal running `python main.py`

---

## Database Commands

### View All Failures

```bash
sqlite3 ci_cd_monitor.db "SELECT * FROM failures;"
```

### View All Analyses

```bash
sqlite3 ci_cd_monitor.db "SELECT * FROM analyses;"
```

### View Audit Logs

```bash
sqlite3 ci_cd_monitor.db "SELECT * FROM audit_logs;"
```

### View Metrics

```bash
sqlite3 ci_cd_monitor.db "SELECT * FROM metrics;"
```

### Count Failures by Type

```bash
sqlite3 ci_cd_monitor.db "SELECT error_type, COUNT(*) FROM analyses GROUP BY error_type;"
```

### Count Failures by Category

```bash
sqlite3 ci_cd_monitor.db "SELECT category, COUNT(*) FROM analyses GROUP BY category;"
```

### View Recent Failures

```bash
sqlite3 ci_cd_monitor.db "SELECT * FROM failures ORDER BY created_at DESC LIMIT 10;"
```

### View Recent Analyses

```bash
sqlite3 ci_cd_monitor.db "SELECT * FROM analyses ORDER BY created_at DESC LIMIT 10;"
```

---

## Log Commands

### View All Logs

```bash
cat ci_cd_monitor.log
```

### View Last 50 Lines

```bash
tail -50 ci_cd_monitor.log
```

### View Real-Time Logs

```bash
tail -f ci_cd_monitor.log
```

### Filter for Errors

```bash
grep ERROR ci_cd_monitor.log
```

### Filter for Specific Repository

```bash
grep "owner/repo1" ci_cd_monitor.log
```

### Filter for DEVOPS Issues

```bash
grep "DEVOPS" ci_cd_monitor.log
```

### Filter for DEVELOPER Issues

```bash
grep "DEVELOPER" ci_cd_monitor.log
```

### Filter for PR Creation

```bash
grep "Creating PR" ci_cd_monitor.log
```

### Filter for Slack Notifications

```bash
grep "Slack notification" ci_cd_monitor.log
```

### Count Log Entries by Level

```bash
grep -c "INFO" ci_cd_monitor.log
grep -c "ERROR" ci_cd_monitor.log
grep -c "WARNING" ci_cd_monitor.log
```

---

## Configuration Commands

### View Current Configuration

```bash
cat config.json
```

### View Environment Variables

```bash
cat .env
```

### Update Repository List

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

---

## Testing Commands

### Run All Tests

```bash
python -m pytest tests/ -v
```

### Run Unit Tests Only

```bash
python -m pytest tests/unit/ -v
```

### Run Property-Based Tests Only

```bash
python -m pytest tests/properties/ -v
```

### Run Specific Test File

```bash
python -m pytest tests/unit/test_config_manager.py -v
```

### Run Specific Test

```bash
python -m pytest tests/unit/test_config_manager.py::test_load_configuration -v
```

### Run Tests with Coverage

```bash
python -m pytest tests/ --cov=src --cov-report=html
```

---

## Development Commands

### Install Dependencies

```bash
pip install -r requirements.txt
```

### Update Dependencies

```bash
pip install -r requirements.txt --upgrade
```

### Check Python Version

```bash
python --version
```

### Check Installed Packages

```bash
pip list
```

---

## Troubleshooting Commands

### Check System Status

```bash
python test_configuration.py
```

### Check GitHub Connection

```bash
python -c "from src.github_client import GitHubClient; import os; client = GitHubClient(os.getenv('GITHUB_TOKEN')); print(client.get_rate_limit_status())"
```

### Check Database Connection

```bash
python -c "from src.database import Database; db = Database('sqlite:///ci_cd_monitor.db'); print('Database OK')"
```

### Check Configuration Loading

```bash
python -c "from src.config_manager import ConfigurationManager; config = ConfigurationManager(); print('Configuration OK')"
```

### View Database Schema

```bash
sqlite3 ci_cd_monitor.db ".schema"
```

### Backup Database

```bash
cp ci_cd_monitor.db ci_cd_monitor.db.backup
```

### Reset Database

```bash
rm ci_cd_monitor.db
python main.py  # Will recreate database
```

---

## Monitoring Commands

### Monitor CPU Usage

```bash
# On Linux/Mac
top -p $(pgrep -f "python main.py")

# On Windows
tasklist | findstr python
```

### Monitor Memory Usage

```bash
# On Linux/Mac
ps aux | grep "python main.py"

# On Windows
tasklist /v | findstr python
```

### Monitor Network Connections

```bash
# On Linux/Mac
lsof -i -P -n | grep python

# On Windows
netstat -ano | findstr python
```

---

## Deployment Commands

### Run in Background (Linux/Mac)

```bash
nohup python main.py > ci_cd_monitor.log 2>&1 &
```

### Run in Background with Screen (Linux/Mac)

```bash
screen -S ci-monitor -d -m python main.py
```

### Attach to Screen Session

```bash
screen -r ci-monitor
```

### Run as Service (Linux)

Create `/etc/systemd/system/ci-monitor.service`:
```ini
[Unit]
Description=CI/CD Failure Monitor
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/path/to/project
ExecStart=/usr/bin/python3 main.py
Restart=always

[Install]
WantedBy=multi-user.target
```

Then:
```bash
sudo systemctl start ci-monitor
sudo systemctl enable ci-monitor
sudo systemctl status ci-monitor
```

---

## Quick Workflows

### Complete Setup Workflow

```bash
# 1. Verify configuration
python test_configuration.py

# 2. Update repositories in .env
# Edit .env and set REPOSITORIES

# 3. Update config.json
# Edit config.json with your settings

# 4. Start the agent
python main.py

# 5. Monitor in another terminal
tail -f ci_cd_monitor.log
```

### Troubleshooting Workflow

```bash
# 1. Check system status
python test_configuration.py

# 2. View recent logs
tail -50 ci_cd_monitor.log

# 3. Check for errors
grep ERROR ci_cd_monitor.log

# 4. View database
sqlite3 ci_cd_monitor.db "SELECT * FROM failures ORDER BY created_at DESC LIMIT 5;"

# 5. Restart agent
# Press Ctrl+C to stop
python main.py
```

### Monitoring Workflow

```bash
# Terminal 1: Run agent
python main.py

# Terminal 2: Monitor logs
tail -f ci_cd_monitor.log

# Terminal 3: Monitor database
watch -n 5 'sqlite3 ci_cd_monitor.db "SELECT COUNT(*) FROM failures;"'

# Terminal 4: Monitor Slack (manual)
# Check Slack workspace for notifications
```

---

## Common Issues & Commands

### Issue: Agent won't start

```bash
# Check configuration
python test_configuration.py

# Check logs
tail -50 ci_cd_monitor.log

# Check database
sqlite3 ci_cd_monitor.db ".tables"
```

### Issue: No failures detected

```bash
# Check repositories
grep REPOSITORIES .env

# Check logs for polling
grep "Polling" ci_cd_monitor.log

# Check GitHub connection
python test_configuration.py
```

### Issue: Slack notifications not working

```bash
# Check Slack token
grep SLACK_BOT_TOKEN .env

# Check logs for Slack errors
grep -i slack ci_cd_monitor.log

# Check Slack channels
grep slack_channels config.json
```

### Issue: PRs not being created

```bash
# Check GitHub token
grep GITHUB_TOKEN .env

# Check logs for PR creation
grep "Creating PR" ci_cd_monitor.log

# Check risk scores
sqlite3 ci_cd_monitor.db "SELECT risk_score FROM analyses ORDER BY created_at DESC LIMIT 5;"
```

---

## Summary

### Essential Commands

| Command | Purpose |
|---------|---------|
| `python main.py` | Start the agent |
| `python test_configuration.py` | Verify configuration |
| `tail -f ci_cd_monitor.log` | Monitor logs |
| `sqlite3 ci_cd_monitor.db "SELECT * FROM failures;"` | View failures |

### Monitoring Commands

| Command | Purpose |
|---------|---------|
| `tail -f ci_cd_monitor.log` | Real-time logs |
| `grep ERROR ci_cd_monitor.log` | View errors |
| `sqlite3 ci_cd_monitor.db "SELECT * FROM analyses;"` | View analyses |

### Configuration Commands

| Command | Purpose |
|---------|---------|
| `cat .env` | View credentials |
| `cat config.json` | View configuration |
| `python test_configuration.py` | Verify all connections |

---

## Next Steps

1. **Start the agent:**
   ```bash
   python main.py
   ```

2. **Monitor in another terminal:**
   ```bash
   tail -f ci_cd_monitor.log
   ```

3. **Check Slack** for notifications

4. **Review PRs** on GitHub

That's it! The system is running. 🚀
