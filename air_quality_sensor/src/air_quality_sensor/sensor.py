import logging
import queue
import signal
import sqlite3
import sys

from air_quality_core.config.environments import get_settings

from .buffered_publisher import BufferedPublisher
from .delivery_loop import DeliveryLoop, ExponentialBackoff
from .mqtt_publisher import MQTTPublisher
from .poller import BaseSensorThread
from .sensing.pms5003 import PMS5003, open_pm_port
from .sqlite_buffer import SQLLiteBufferWriter

# Set up logging
logging.basicConfig(
    level=getattr(logging, get_settings().LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger(__name__)


def drop_oldest(q: "queue.Queue", item) -> None:
    if q.full():
        q.get_nowait()
    q.put_nowait(item)


def make_outbound_port() -> BufferedPublisher:
    """
    Create a buffered publisher that will persist messages to disk and publish them to MQTT.

    The need for a factory here is because we got a little too carried away with keeping it
    async and sqlite3 connections must be used in the same thread they are created
    (in this case, the delivery loop thread).
    """
    settings = get_settings()

    # Handle in-memory database for testing
    if settings.BUFFER_DB == ":memory:":
        conn = sqlite3.connect(":memory:")
    else:
        conn = sqlite3.connect(settings.BUFFER_DB)

    buf = SQLLiteBufferWriter(conn, max_mb=32)
    mqtt_pub = MQTTPublisher(
        host=settings.MQTT_BROKER,
        port=settings.MQTT_PORT,
        topic=settings.MQTT_TOPIC,
        client_id=f"sensor-{settings.ENVIRONMENT.value}",
        username=None,
        password=None,
    )

    return BufferedPublisher(buf, mqtt_pub)


def make_sensor():
    """Create the PM sensor. This can be overridden for testing."""
    return PMS5003(open_pm_port())


def bootstrap(sensor_factory):
    settings = get_settings()

    log.info(f"Starting sensor in {settings.ENVIRONMENT.value} environment")
    log.info(f"Device ID: {settings.DEVICE_ID}")
    log.info(f"MQTT Broker: {settings.MQTT_BROKER}:{settings.MQTT_PORT}")
    log.info(f"MQTT Topic: {settings.MQTT_TOPIC}")
    log.info(f"Read Interval: {settings.READ_INTERVAL_SEC}s")

    backoff = ExponentialBackoff()

    # work queue
    q: queue.Queue[str] = queue.Queue(maxsize=5000)

    # sensor drivers - use provided factory
    pm = sensor_factory()

    threads = [
        BaseSensorThread("pm", settings.READ_INTERVAL_SEC, settings.DEVICE_ID, pm.read, q),
    ]

    for t in threads:
        t.start()

    loop = DeliveryLoop(q, make_outbound_port, backoff)
    loop.start()
    return threads, loop


def main():
    threads, loop = bootstrap(make_sensor)

    def sigterm_handler(signum, frame):
        log.info("Received shutdown signal, stopping sensor...")
        for t in threads:
            t.stop()
            t.join()
        loop.stop()
        loop.join()
        sys.exit(0)

    signal.signal(signal.SIGTERM, sigterm_handler)
    signal.signal(signal.SIGINT, sigterm_handler)
    signal.pause()


if __name__ == "__main__":
    main()
