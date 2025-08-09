"""
Enhanced API run script with environment support.
"""

import argparse
import logging
import os

import uvicorn

from air_quality_core.config.environments import get_settings


def main():
    parser = argparse.ArgumentParser(description="Run the air quality API server")
    parser.add_argument(
        "--environment",
        choices=["production", "development", "testing"],
        default="development",
        help="Environment to run in",
    )
    parser.add_argument("--host", help="Host to bind to (overrides config)")
    parser.add_argument("--port", type=int, help="Port to bind to (overrides config)")
    parser.add_argument(
        "--reload", action="store_true", help="Enable auto-reload (development only)"
    )

    args = parser.parse_args()

    # Set environment variable for config
    os.environ["AIR_QUALITY_ENV"] = args.environment

    # Get configuration
    config = get_settings()

    # Set up logging
    logging.basicConfig(
        level=getattr(logging, config.LOG_LEVEL.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(message)s",
    )
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


if __name__ == "__main__":
    main()
