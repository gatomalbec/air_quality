import json
import logging

import paho.mqtt.client as mqtt
from air_quality_core.application import ingest_reading
from air_quality_core.config.environments import get_settings
from air_quality_core.domain.models import Reading

from air_quality_server.adapters.db.uow import SqlAlchemyUoW

log = logging.getLogger(__name__)

# Set up logging based on environment
settings = get_settings()
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(message)s",
)

log.info(f"Starting MQTT server in {settings.ENVIRONMENT.value} environment")


def _on_connect(client, _userdata, _flags, rc):
    settings = get_settings()

    if rc:
        log.error("MQTT connect failed, rc=%s", rc)
        return
    log.info("Connected to broker %s:%s", settings.MQTT_BROKER, settings.MQTT_PORT)
    client.subscribe(settings.MQTT_TOPIC, qos=1)
    log.info("Subscribed to %s", settings.MQTT_TOPIC)


def _on_message(_client, _userdata, msg):
    try:
        payload = json.loads(msg.payload.decode())
        reading = Reading(**payload)
        with SqlAlchemyUoW() as uow:
            ingest_reading(reading, uow)
        log.debug("Ingested reading from %s", reading.device_id)
    except Exception as exc:
        log.exception("Failed to process message on topic %s: %s", msg.topic, exc)


def main() -> None:
    settings = get_settings()

    log.info(f"Connecting to MQTT broker at {settings.MQTT_BROKER}:{settings.MQTT_PORT}")
    log.info(f"Using topic: {settings.MQTT_TOPIC}")
    log.info(f"Client ID: {settings.MQTT_CLIENT_ID}")

    client = mqtt.Client(client_id=settings.MQTT_CLIENT_ID, clean_session=True)  # type: ignore[operator]
    client.on_connect = _on_connect
    client.on_message = _on_message
    client.connect(settings.MQTT_BROKER, settings.MQTT_PORT, keepalive=60)
    client.loop_forever()
