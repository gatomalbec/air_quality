# air_quality/config/settings.py

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # database / api
    DATABASE_URL: str = "postgresql://sensor:secret@localhost:5432/sensordb"
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000

    # mqtt
    MQTT_BROKER: str = "localhost"
    MQTT_PORT: int = 1883
    MQTT_TOPIC: str = "air/+/readings"
    MQTT_CLIENT_ID: str = "air‑quality‑server"

    # sensor / producer
    PMS_PORT: str = "/dev/serial0"
    BUFFER_DB: str = "buffer.db"
    REPO_DIR: str = "/home/pi/sensor"
    READ_INTERVAL_SEC: int = 10
    LOG_LEVEL: str = "INFO"

    class Config:
        env_file = ".env"


settings = Settings()
