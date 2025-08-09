"""
Run the MQTT server with environment support.
"""

import argparse
import logging
import os

from air_quality_core.config.environments import get_settings
from air_quality_server.adapters.mqtt.server import main as mqtt_main


def main():
    parser = argparse.ArgumentParser(description="Run the air quality MQTT server")
    parser.add_argument(
        "--environment",
        choices=["production", "development", "testing"],
        default="development",
        help="Environment to run in",
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

    log.info("Starting MQTT server...")
    log.info(f"Environment: {args.environment}")
    log.info(f"MQTT Broker: {config.MQTT_BROKER}:{config.MQTT_PORT}")
    log.info(f"Topic: {config.MQTT_TOPIC}")
    log.info(f"Client ID: {config.MQTT_CLIENT_ID}")

    # Run the MQTT server
    mqtt_main()


if __name__ == "__main__":
    main()
