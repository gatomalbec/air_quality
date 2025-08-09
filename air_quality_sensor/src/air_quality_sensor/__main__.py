"""
Canonical entry point for air_quality_sensor package.

Usage:
    poetry run air-quality-sensor --environment development
    poetry run air-quality-sensor --environment testing --test-mode
"""

import argparse
import logging
import os

from air_quality_core.config.environments import get_settings
from air_quality_sensor.sensing.pms5003 import PMS5003
from air_quality_sensor.sensor import bootstrap
from air_quality_sensor.sensor import main as sensor_main
from air_quality_sensor.test_utils import MockSerialPort, create_test_readings


def setup_logging(config) -> None:
    """Set up logging configuration."""
    logging.basicConfig(
        level=getattr(logging, config.LOG_LEVEL.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(message)s",
    )
    return None


def run_test_sensor(config, device_id: str, interval: int, count: int) -> None:
    """Run sensor in test mode with mocked hardware."""
    log = logging.getLogger(__name__)

    log.info("Running sensor in TEST mode...")
    log.info(f"Device ID: {device_id}")
    log.info(f"Interval: {interval}s")
    log.info(f"Readings: {count}")

    # Create mock sensor
    readings = create_test_readings(count)
    mock_port = MockSerialPort(readings)

    def mock_sensor_factory() -> PMS5003:
        """Factory function that creates a mock sensor for testing."""
        return PMS5003(mock_port)

    try:
        # Run sensor with mock factory
        threads, loop = bootstrap(sensor_factory=mock_sensor_factory)

        # Wait for readings to complete
        import time

        time.sleep(count * interval + 2)

        # Stop sensor
        for thread in threads:
            thread.stop()
            thread.join()
        loop.stop()
        loop.join()

        log.info("Test sensor completed")

    except Exception as e:
        log.error(f"Test sensor failed: {e}")
        raise
    return None


def run_production_sensor(config, device_id: str) -> None:
    """Run sensor in production mode with real hardware."""
    log = logging.getLogger(__name__)

    log.info("Running sensor in PRODUCTION mode...")
    log.info(f"Device ID: {device_id}")
    log.info(f"Interval: {config.READ_INTERVAL_SEC}s")

    # Run the normal sensor main
    sensor_main()
    return None


def main() -> None:
    """Main entry point for air_quality_sensor."""
    parser = argparse.ArgumentParser(description="Air Quality Sensor")
    parser.add_argument(
        "--environment",
        choices=["production", "development", "testing"],
        default="development",
        help="Environment to run in",
    )
    parser.add_argument("--device-id", help="Device ID (overrides config)")
    parser.add_argument(
        "--test-mode", action="store_true", help="Run in test mode with mocked hardware"
    )
    parser.add_argument(
        "--test-count", type=int, default=10, help="Number of test readings to generate"
    )
    parser.add_argument(
        "--test-interval", type=int, default=1, help="Interval between test readings (seconds)"
    )

    args = parser.parse_args()

    # Set environment variable for config
    os.environ["AIR_QUALITY_ENV"] = args.environment

    # Get configuration
    config = get_settings()

    # Set up logging
    setup_logging(config)
    log = logging.getLogger(__name__)

    # Determine device ID
    device_id = args.device_id or config.DEVICE_ID

    log.info("Starting air quality sensor...")
    log.info(f"Environment: {args.environment}")
    log.info(f"Device ID: {device_id}")
    log.info(f"MQTT Broker: {config.MQTT_BROKER}:{config.MQTT_PORT}")
    log.info(f"Topic: {config.MQTT_TOPIC}")

    if args.test_mode:
        run_test_sensor(config, device_id, args.test_interval, args.test_count)
    else:
        run_production_sensor(config, device_id)


if __name__ == "__main__":
    main()
