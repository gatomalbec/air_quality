"""
Database setup script that handles both production and test databases.
"""

import argparse
import logging
import os
import subprocess
import sys

from air_quality_core.config.environments import Environment, get_settings


def setup_database(environment: Environment, force: bool = False):
    """Set up database for the specified environment."""

    config = get_settings()

    # Set up logging
    logging.basicConfig(
        level=getattr(logging, config.LOG_LEVEL.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(message)s",
    )
    log = logging.getLogger(__name__)

    log.info(f"Setting up database for {environment.value} environment...")
    log.info(f"Database URL: {config.DATABASE_URL}")

    # Parse database URL to get database name
    if "postgresql://" in config.DATABASE_URL:
        db_name = config.DATABASE_URL.split("/")[-1].split("?")[0]
        log.info(f"Database name: {db_name}")

        # Check if database exists
        try:
            result = subprocess.run(
                ["psql", "-lqt", "-h", "localhost", "-U", "sensor"], capture_output=True, text=True
            )

            if db_name in result.stdout:
                if force:
                    log.info(f"Dropping existing database: {db_name}")
                    subprocess.run(
                        ["dropdb", "-h", "localhost", "-U", "sensor", db_name], check=True
                    )
                else:
                    log.info(f"Database {db_name} already exists")
                    return

        except subprocess.CalledProcessError:
            log.warning("Could not check existing databases")

        # Create database
        try:
            log.info(f"Creating database: {db_name}")
            subprocess.run(["createdb", "-h", "localhost", "-U", "sensor", db_name], check=True)
            log.info(f"Database {db_name} created successfully")

        except subprocess.CalledProcessError as e:
            log.error(f"Failed to create database: {e}")
            sys.exit(1)

        # Run migrations
        try:
            log.info("Running database migrations...")
            subprocess.run(["alembic", "upgrade", "head"], check=True)
            log.info("Database migrations completed")

        except subprocess.CalledProcessError as e:
            log.error(f"Failed to run migrations: {e}")
            sys.exit(1)

    else:
        log.error("Only PostgreSQL databases are supported")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Set up database for air quality system")
    parser.add_argument(
        "--environment",
        choices=["production", "development", "testing"],
        default="development",
        help="Environment to set up",
    )
    parser.add_argument(
        "--force", action="store_true", help="Force recreation of existing database"
    )

    args = parser.parse_args()

    # Set environment variable for config
    os.environ["AIR_QUALITY_ENV"] = args.environment

    environment = Environment(args.environment)
    setup_database(environment, args.force)


if __name__ == "__main__":
    main()
