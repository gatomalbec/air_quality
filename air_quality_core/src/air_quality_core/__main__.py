"""
Canonical entry point for air_quality_core package.

This package contains domain models, application services, and configuration.
It does not include testing or orchestration functionality.
"""

import sys

from air_quality_core.config.environments import get_settings


def main() -> None:
    """Main entry point for air_quality_core package."""
    print("air_quality_core - Domain and application layer package")
    print("This package is not intended to be run directly.")
    print("Use the specific service packages (air_quality_server, air_quality_sensor) instead.")

    # Show current configuration
    try:
        config = get_settings()
        print("\nCurrent configuration:")
        print(f"Environment: {config.ENVIRONMENT}")
        print(f"Database: {config.DATABASE_URL}")
        print(f"MQTT: {config.MQTT_BROKER}:{config.MQTT_PORT}")
        print(f"API: {config.API_HOST}:{config.API_PORT}")
    except Exception as e:
        print(f"Could not load configuration: {e}")

    sys.exit(0)


if __name__ == "__main__":
    main()
