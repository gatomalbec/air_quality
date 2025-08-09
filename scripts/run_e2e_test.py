"""
Run the complete air quality system for E2E testing.
"""

import argparse
import logging
import os
import signal
import subprocess
import sys
import time
from typing import List, Tuple

import requests

from air_quality_core.config.environments import get_settings


class E2ETestRunner:
    """Runs the complete system for E2E testing."""

    def __init__(self, environment: str = "testing"):
        self.environment = environment
        self.processes: List[Tuple[str, subprocess.Popen]] = []
        self.running = False
        self.log = logging.getLogger(__name__)

    def setup_environment(self):
        """Set up the test environment."""
        self.log.info("Setting up E2E test environment...")

        # Set environment variable
        os.environ["AIR_QUALITY_ENV"] = self.environment

        # Get configuration
        config = get_settings()

        self.log.info(f"Environment: {self.environment}")
        self.log.info(f"Database: {config.DATABASE_URL}")
        self.log.info(f"MQTT: {config.MQTT_BROKER}:{config.MQTT_PORT}")
        self.log.info(f"API: {config.API_HOST}:{config.API_PORT}")

        # Set up database
        self.log.info("Setting up database...")
        subprocess.run(
            [sys.executable, "scripts/setup_database.py", "--environment", self.environment],
            check=True,
        )

    def start_services(self):
        """Start all services."""
        self.log.info("Starting services...")

        # Start API server
        api_process = subprocess.Popen(
            [sys.executable, "scripts/run_api.py", "--environment", self.environment]
        )
        self.processes.append(("API Server", api_process))

        # Wait for API to be ready
        self._wait_for_api_ready()

        # Start MQTT server
        mqtt_process = subprocess.Popen(
            [sys.executable, "scripts/run_server.py", "--environment", self.environment]
        )
        self.processes.append(("MQTT Server", mqtt_process))

        # Wait for MQTT to be ready
        time.sleep(2)

        # Start sensor
        sensor_process = subprocess.Popen(
            [
                sys.executable,
                "scripts/run_sensor.py",
                "--environment",
                self.environment,
                "--test-mode",
                "--test-count",
                "5",
                "--test-interval",
                "2",
            ]
        )
        self.processes.append(("Sensor", sensor_process))

        self.running = True

    def _wait_for_api_ready(self):
        """Wait for API server to be ready."""
        config = get_settings()
        api_url = f"http://{config.API_HOST}:{config.API_PORT}"

        self.log.info("Waiting for API server to be ready...")
        for i in range(30):  # 30 second timeout
            try:
                response = requests.get(f"{api_url}/ping", timeout=1)
                if response.status_code == 200:
                    self.log.info("API server is ready")
                    return
            except Exception:
                pass
            time.sleep(1)

        raise TimeoutError("API server failed to start")

    def stop_services(self):
        """Stop all services."""
        if not self.running:
            return

        self.log.info("Stopping services...")

        for name, process in self.processes:
            self.log.info(f"Stopping {name}...")
            process.terminate()
            process.wait()

        self.running = False

    def run_test(self, duration: int = 30):
        """Run the complete system for a specified duration."""
        try:
            self.setup_environment()
            self.start_services()

            self.log.info(f"Running E2E test for {duration} seconds...")
            time.sleep(duration)

            self.log.info("E2E test completed successfully")

        except KeyboardInterrupt:
            self.log.info("E2E test interrupted by user")
        except Exception as e:
            self.log.error(f"E2E test failed: {e}")
            raise
        finally:
            self.stop_services()


def main():
    parser = argparse.ArgumentParser(description="Run complete air quality system for E2E testing")
    parser.add_argument(
        "--environment",
        choices=["production", "development", "testing"],
        default="testing",
        help="Environment to run in",
    )
    parser.add_argument(
        "--duration", type=int, default=30, help="Duration to run the test (seconds)"
    )

    args = parser.parse_args()

    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    # Set up signal handlers
    def signal_handler(signum, frame):
        logging.getLogger(__name__).info("Received interrupt signal")
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Run the E2E test
    runner = E2ETestRunner(args.environment)
    runner.run_test(args.duration)


if __name__ == "__main__":
    main()
