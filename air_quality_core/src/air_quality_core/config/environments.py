from enum import Enum

from pydantic_settings import BaseSettings


class Environment(str, Enum):
    PRODUCTION = "production"
    DEVELOPMENT = "development"
    TESTING = "testing"


class Settings(BaseSettings):
    """Configuration settings for the air quality system."""

    # Environment
    ENVIRONMENT: Environment = Environment.DEVELOPMENT

    # Database (PostgreSQL only)
    DATABASE_URL: str = "postgresql://sensor:secret@localhost:5432/sensordb"

    # API
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000

    # MQTT
    MQTT_BROKER: str = "localhost"
    MQTT_PORT: int = 1883
    MQTT_TOPIC: str = "air/+/readings"
    MQTT_CLIENT_ID: str = "air-quality-server"

    # Sensor
    DEVICE_ID: str = "sensor-pi-01"
    PMS_PORT: str = "/dev/serial0"
    BUFFER_DB: str = "buffer.db"
    REPO_DIR: str = "/home/pi/sensor"
    READ_INTERVAL_SEC: int = 10

    # Logging
    LOG_LEVEL: str = "INFO"

    class Config:
        env_file = ".env"


def get_settings() -> Settings:
    """Get settings based on environment."""
    import os

    # Set environment-specific defaults
    env = os.getenv("AIR_QUALITY_ENV", "development").lower()

    if env == "production":
        return Settings(ENVIRONMENT=Environment.PRODUCTION, LOG_LEVEL="WARNING")
    elif env == "testing":
        return Settings(
            ENVIRONMENT=Environment.TESTING,
            DATABASE_URL="postgresql://sensor:secret@localhost:5432/test_sensordb",
            API_PORT=8001,
            MQTT_TOPIC="test/air/+/readings",
            MQTT_CLIENT_ID="air-quality-server-test",
            DEVICE_ID="test-device",
            READ_INTERVAL_SEC=1,
            BUFFER_DB=":memory:",
            LOG_LEVEL="DEBUG",
        )
    else:
        return Settings(ENVIRONMENT=Environment.DEVELOPMENT, LOG_LEVEL="DEBUG")
