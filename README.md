# CI/CD Failure Monitor & Auto-Remediation Agent

An intelligent system that monitors GitHub Actions workflow failures, analyzes them using GPT-4o, and automatically remediates safe failures while escalating high-risk issues for human approval.

## Features

- **Continuous Monitoring**: Polls GitHub Actions every 5 minutes for workflow failures
- **AI-Powered Analysis**: Uses GPT-4o to classify failures and propose fixes
- **Risk Scoring**: Assigns risk scores (0-10) to determine auto-remediation safety
- **Safety Gates**: Multiple validation layers prevent dangerous auto-remediations
- **Approval Workflow**: Slack-based approval system for high-risk remediations
- **Comprehensive Audit Trail**: Complete logging of all decisions and actions
- **Metrics Tracking**: Monitors remediation success rates and resolution times
- **Error Handling**: Robust error handling with automatic recovery

## Architecture

The system consists of the following components:

- **Monitor**: Polls GitHub Actions for workflow failures
- **Analyzer**: Sends failures to GPT-4o for analysis and classification
- **Safety Gate**: Validates remediation safety based on risk score and code type
- **Approval Workflow**: Manages human approval for high-risk remediations
- **Executor**: Executes approved remediations
- **Notifier**: Sends Slack notifications at each stage
- **Audit Logger**: Records all actions and decisions
- **Metrics Tracker**: Collects system metrics and statistics
- **Configuration Manager**: Manages system configuration
- **Database**: Persists failures, audit trails, and metrics

## Installation

1. Clone the repository
2. Create a Python virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Set up environment variables:
   ```bash
   cp .env.example .env
   # Edit .env with your credentials
   ```

5. Create configuration file:
   ```bash
   cp config.example.json config.json
   # Edit config.json as needed
   ```

## Configuration

### Environment Variables

- `GITHUB_TOKEN`: GitHub personal access token with repo and workflow permissions
- `OPENAI_API_KEY`: OpenAI API key for GPT-4o access
- `SLACK_BOT_TOKEN`: Slack bot token for sending notifications
- `CONFIG_FILE`: Path to configuration file (default: config.json)
- `DATABASE_URL`: Database URL (default: sqlite:///ci_cd_monitor.db)
- `LOG_LEVEL`: Logging level (default: INFO)
- `REPOSITORIES`: Comma-separated list of repositories to monitor

### Configuration File (config.json)

```json
{
  "risk_threshold": 5,
  "protected_repositories": ["critical/repo"],
  "slack_channels": {
    "alerts": "#ci-cd-alerts",
    "approvals": "#ci-cd-approvals",
    "critical": "#critical-alerts"
  },
  "approval_timeout_hours": 24,
  "polling_interval_minutes": 5,
  "repository_configs": {
    "critical/repo": {
      "risk_threshold": 3,
      "protected": true
    }
  }
}
```

## Running the Agent

```bash
python main.py
```

The agent will start monitoring the configured repositories and process failures as they occur.

## Testing

Run unit tests:
```bash
pytest tests/unit/
```

Run property-based tests:
```bash
pytest tests/properties/
```

Run all tests:
```bash
pytest tests/
```

## Correctness Properties

The system validates 66 correctness properties through property-based testing:

- **Monitoring Properties** (5): Polling consistency, failure details retrieval, failure reason extraction, idempotent processing, rate limit handling
- **Analysis Properties** (7): Analysis trigger, category assignment, risk score validity, remediation proposal completeness, effort/confidence validity, component identification, analysis persistence
- **Configuration Properties** (5): Environment variable loading, configuration file loading, configuration reload, per-repository overrides, validation
- **Safety Gate Properties** (5): Risk threshold configuration, safe/high-risk classification, risk score validation, safe remediation execution, failed gate escalation
- **Approval Workflow Properties** (6): Approval request notification, interactive buttons, approval execution, rejection handling, timeout escalation, audit trail
- **Notification Properties** (7): Initial alert, analysis notification, approval request, remediation result, critical alert, timeout escalation, channel configuration
- **Audit & Metrics Properties** (6): Comprehensive action logging, timing metrics, remediation result recording, metrics aggregation, audit log persistence, audit log filtering
- **Error Handling Properties** (5): Error catching and logging, critical error alerting, service recovery, API retry logic, remediation rollback
- **GitHub Integration Properties** (5): Authentication, failed workflow filtering, complete workflow details, rate limit handling, error reporting
- **Data Persistence Properties** (5): Failure record round trip, audit trail round trip, metrics round trip, query filtering/aggregation, data retention policy
- **Remediation Execution Properties** (3): Remediation execution, execution output capture, success verification

## Monitoring and Alerting

The system sends Slack notifications at each stage:

1. **Initial Alert**: When a failure is detected
2. **Analysis Notification**: When AI analysis completes
3. **Approval Request**: When approval is needed (with interactive buttons)
4. **Remediation Result**: When remediation completes
5. **Critical Alerts**: For system errors or failures

## Audit Trail

All actions are logged to the database with:
- Timestamp
- Actor (component or user)
- Action type
- Failure/request ID
- Details and reasoning
- Outcome (success/failure)

Query audit logs:
```python
from src.audit_logger import AuditLogger
from src.database import Database

db = Database()
logger = AuditLogger(db)

# Query all logs
logs = logger.query_logs()

# Query with filters
logs = logger.query_logs({
    "start_date": datetime(2024, 1, 1),
    "end_date": datetime(2024, 1, 31),
    "action_type": ActionType.REMEDIATION
})
```

## Metrics

The system tracks:
- Detection latency (time from failure to detection)
- Analysis latency (time to analyze)
- Remediation latency (time to remediate)
- Remediation success rate
- Risk score distribution
- Failure category distribution

Query metrics:
```python
from src.metrics_tracker import MetricsTracker
from src.database import Database

db = Database()
tracker = MetricsTracker(db)

# Get success rate
success_rate = tracker.get_success_rate()

# Get average resolution time
avg_time = tracker.get_average_resolution_time()

# Get risk score distribution
distribution = tracker.get_risk_score_distribution()
```

## Error Handling

The system implements comprehensive error handling:

- **Transient Errors**: Exponential backoff with retry (max 3 attempts)
- **Authentication Errors**: Log error, send critical alert, stop processing
- **Data Validation Errors**: Log error, send alert, skip processing
- **Critical Errors**: Log error, send critical alert, attempt automatic restart

## Development

### Project Structure

```
.
├── src/
│   ├── __init__.py
│   ├── agent.py              # Main orchestrator
│   ├── analyzer.py           # GPT-4o analysis
│   ├── approval_workflow.py  # Approval management
│   ├── audit_logger.py       # Audit trail logging
│   ├── config_manager.py     # Configuration management
│   ├── database.py           # Database layer
│   ├── error_handler.py      # Error handling
│   ├── executor.py           # Remediation execution
│   ├── github_client.py      # GitHub API client
│   ├── logging_config.py     # Logging setup
│   ├── metrics_tracker.py    # Metrics collection
│   ├── models.py             # Data models
│   ├── monitor.py            # Failure monitoring
│   ├── notifier.py           # Slack notifications
│   └── safety_gate.py        # Safety validation
├── tests/
│   ├── unit/                 # Unit tests
│   ├── properties/           # Property-based tests
│   └── integration/          # Integration tests
├── main.py                   # Entry point
├── config.example.json       # Configuration template
├── .env.example              # Environment template
└── requirements.txt          # Python dependencies
```

### Adding New Features

1. Create new component in `src/`
2. Add unit tests in `tests/unit/`
3. Add property-based tests in `tests/properties/`
4. Update `src/agent.py` to integrate new component
5. Update documentation

## License

MIT License

## Support

For issues or questions, please open an issue on GitHub.
#   g i t o p s  
 