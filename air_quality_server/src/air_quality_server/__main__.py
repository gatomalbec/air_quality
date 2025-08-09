"""
Canonical entry point for air_quality_server package.

Usage:
    poetry run air-quality-api --environment development
    poetry run air-quality-server --environment development
    poetry run air-quality-setup-db --environment development
"""

import argparse
import logging
import os
import sys

import uvicorn
from air_quality_core.config.environments import get_settings

from air_quality_server.adapters.mqtt.server import main as mqtt_main


def setup_logging(config) -> None:
    """Set up logging configuration."""
    logging.basicConfig(
        level=getattr(logging, config.LOG_LEVEL.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(message)s",
    )
    return None


def run_api_server(args: argparse.Namespace) -> None:
    """Run the FastAPI server."""
    config = get_settings()
    setup_logging(config)
    log = logging.getLogger(__name__)

    # Override with command line arguments
    host = args.host or config.API_HOST
    port = args.port or config.API_PORT
    reload = args.reload and args.environment != "production"

    log.info("Starting API server...")
    log.info(f"Environment: {args.environment}")
    log.info(f"Host: {host}")
    log.info(f"Port: {port}")
    log.info(f"Reload: {reload}")

    uvicorn.run(
        "air_quality_server.adapters.api.main:app",
        host=host,
        port=port,
        reload=reload,
        log_level=config.LOG_LEVEL.lower(),
    )
    return None


def run_mqtt_server(args: argparse.Namespace) -> None:
    """Run the MQTT server."""
    config = get_settings()
    setup_logging(config)
    log = logging.getLogger(__name__)

    log.info("Starting MQTT server...")
    log.info(f"Environment: {args.environment}")
    log.info(f"MQTT Broker: {config.MQTT_BROKER}:{config.MQTT_PORT}")
    log.info(f"Topic: {config.MQTT_TOPIC}")
    log.info(f"Client ID: {config.MQTT_CLIENT_ID}")

    mqtt_main()
    return None


def setup_database(args: argparse.Namespace) -> None:
    """Set up the database."""
    from sqlalchemy import create_engine

    from air_quality_server.adapters.db.sqlalchemy_models import Base

    config = get_settings()
    setup_logging(config)
    log = logging.getLogger(__name__)

    log.info(f"Setting up database for {args.environment} environment...")
    log.info(f"Database URL: {config.DATABASE_URL}")

    # Create engine and tables
    engine = create_engine(config.DATABASE_URL, future=True, echo=False)
    Base.metadata.create_all(bind=engine)
    log.info("Database setup completed successfully")
    return None


def main() -> None:
    """Main entry point for air_quality_server commands."""
    parser = argparse.ArgumentParser(
        description="Air Quality Server - API, MQTT, and Database Management"
    )
    parser.add_argument(
        "--environment",
        choices=["production", "development", "testing"],
        default="development",
        help="Environment to run in",
    )
    parser.add_argument(
        "command",
        choices=["api", "server", "setup-db"],
        help="Command to run",
    )
    parser.add_argument("--host", help="Host to bind to (overrides config)")
    parser.add_argument("--port", type=int, help="Port to bind to (overrides config)")
    parser.add_argument(
        "--reload", action="store_true", help="Enable auto-reload (development only)"
    )

    args = parser.parse_args()

    # Set environment variable for config
    os.environ["AIR_QUALITY_ENV"] = args.environment

    if args.command == "api":
        run_api_server(args)
    elif args.command == "server":
        run_mqtt_server(args)
    elif args.command == "setup-db":
        setup_database(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
