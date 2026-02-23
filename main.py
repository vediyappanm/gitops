"""Main entry point for CI/CD Failure Monitor & Auto-Remediation Agent"""
import logging
import os
import argparse
from dotenv import load_dotenv
from src.logging_config import setup_logging
from src.config_manager import ConfigurationManager
from src.database import Database
from src.agent import CICDFailureMonitorAgent

# Load environment variables from .env file
load_dotenv()

# Setup logging
setup_logging(log_level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)


def main():
    """Main entry point"""
    try:
        # Parse command line arguments
        parser = argparse.ArgumentParser(description='CI/CD Failure Monitor & Auto-Remediation Agent')
        parser.add_argument('--dry-run', action='store_true', 
                          help='Run in dry-run mode (simulate without making changes)')
        args = parser.parse_args()
        
        # Load configuration
        config_file = os.getenv("CONFIG_FILE", "config.json")
        config = ConfigurationManager(config_file=config_file)
        
        # Initialize database
        db_url = os.getenv("DATABASE_URL", "sqlite:///ci_cd_monitor.db")
        db = Database(db_url)
        
        # Create and start agent
        agent = CICDFailureMonitorAgent(config, db, dry_run=args.dry_run)
        
        # Get repositories to monitor
        repositories = os.getenv("REPOSITORIES", "").split(",")
        repositories = [r.strip() for r in repositories if r.strip()]
        
        if not repositories:
            logger.error("No repositories configured. Set REPOSITORIES environment variable.")
            return
        
        logger.info(f"Starting CI/CD Failure Monitor Agent for repositories: {repositories}")
        if args.dry_run:
            logger.info("Running in DRY-RUN mode - no changes will be made")
        
        agent.start(repositories)
    
    except KeyboardInterrupt:
        logger.info("Agent interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    main()
