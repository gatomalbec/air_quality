import queue
import signal
import sqlite3
import sys
from pathlib import Path
from typing import TypedDict, Union

from .buffered_publisher import BufferedPublisher
from .delivery_loop import DeliveryLoop, ExponentialBackoff
from .mqtt_publisher import MQTTPublisher
from .poller import BaseSensorThread
from .sensing.pms5003 import PMS5003, open_pm_port
from .sqlite_buffer import SQLLiteBufferWriter


class MqttConfig(TypedDict):
    host: str
    port: int
    topic: str
    client_id: str
    user: Union[str, None]
    password: Union[str, None]


class SamplingConfig(TypedDict):
    pm: int
    co2: int
    voc: int


class Config(TypedDict):
    device_id: str
    db_path: Path
    buffer_mb: int
    mqtt: MqttConfig
    sampling: SamplingConfig
    queue_max: int


CONFIG: Config = {
    "device_id": "sensor-pi-01",
    "db_path": Path("/var/lib/sensor_pi/readings.db"),
    "buffer_mb": 32,
    "mqtt": {
        "host": "broker.local",
        "port": 1883,
        "topic": "aq/v1/readings",
        "client_id": "sensor-pi-01",
        "user": None,
        "password": None,
    },
    "sampling": {
        "pm": 30,  # seconds
        "co2": 10,
        "voc": 10,
    },
    "queue_max": 5000,
}


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
    conn = sqlite3.connect(CONFIG["db_path"])
    buf = SQLLiteBufferWriter(conn, max_mb=CONFIG["buffer_mb"])
    mqtt_cfg = CONFIG["mqtt"]
    mqtt_pub = MQTTPublisher(
        host=mqtt_cfg["host"],
        port=mqtt_cfg["port"],
        topic=mqtt_cfg["topic"],
        client_id=mqtt_cfg["client_id"],
        username=mqtt_cfg["user"],
        password=mqtt_cfg["password"],
    )

    return BufferedPublisher(buf, mqtt_pub)


def bootstrap():
    backoff = ExponentialBackoff()

    # work queue
    q: queue.Queue[str] = queue.Queue(maxsize=CONFIG["queue_max"])

    # sensor drivers
    pm = PMS5003(open_pm_port())

    threads = [
        BaseSensorThread("pm", CONFIG["sampling"]["pm"], CONFIG["device_id"], pm.read, q),
    ]

    for t in threads:
        t.start()

    loop = DeliveryLoop(q, make_outbound_port, backoff)
    loop.start()
    return threads, loop


def main():
    threads, loop = bootstrap()

    def sigterm_handler(signum, frame):
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
