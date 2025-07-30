"""
Air‑quality producer.

• Reads Particulate Matter from a PMS5003 on `settings.PMS_PORT`
• Publishes JSON to   f"{settings.MQTT_TOPIC}/{DEVICE_ID}"
• Buffers to SQLite if the broker is offline
• Listens on `commands/<device_id>` for {"action": "update"} to git‑pull
"""

import json
import logging
import os
import socket
import sqlite3
import struct
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import paho.mqtt.client as mqtt
import serial

from air_quality_core.config.settings import settings

# -------------------------------------------------------------------- #
# configuration
# -------------------------------------------------------------------- #
DEVICE_ID = socket.gethostname()
PUB_TOPIC = f"{settings.MQTT_TOPIC}/{DEVICE_ID}"
CMD_TOPIC = f"commands/{DEVICE_ID}"

BUF_DB = Path(settings.BUFFER_DB)
SER_PORT = settings.PMS_PORT
REPO_DIR = Path(settings.REPO_DIR)
INTERVAL = settings.READ_INTERVAL_SEC

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger("producer")


# -------------------------------------------------------------------- #
# sensor
# -------------------------------------------------------------------- #
_ser = serial.Serial(SER_PORT, baudrate=9600, timeout=1)


def read_sensor() -> dict[str, Any] | None:
    frame = _ser.read(32)
    if len(frame) != 32 or frame[0:2] != b"\x42\x4d":
        return None
    pm = struct.unpack(">HHHHHHHHHHHHHH", frame[4:32])
    return {
        "ts": time.time(),
        "device_id": DEVICE_ID,
        "pm1": pm[3],
        "pm25": pm[4],
        "pm10": pm[5],
    }


# -------------------------------------------------------------------- #
# buffering
# -------------------------------------------------------------------- #
def init_db() -> None:
    BUF_DB.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(BUF_DB) as c:
        c.execute(
            """create table if not exists pending(
                   id integer primary key autoincrement,
                   ts real, device_id text, pm1 integer, pm25 integer, pm10 integer
               )"""
        )


def buffer(r: dict[str, Any]) -> None:
    with sqlite3.connect(BUF_DB) as c:
        c.execute(
            "insert into pending(ts,device_id,pm1,pm25,pm10) values(?,?,?,?,?)",
            (r["ts"], r["device_id"], r["pm1"], r["pm25"], r["pm10"]),
        )


def flush(client: mqtt.Client) -> None:
    with sqlite3.connect(BUF_DB) as c:
        rows = c.execute("select * from pending order by id").fetchall()

    for row in rows:
        payload = json.dumps(
            {
                "ts": row[1],
                "device_id": row[2],
                "pm1": row[3],
                "pm25": row[4],
                "pm10": row[5],
            }
        )
        if client.publish(PUB_TOPIC, payload, qos=1).rc == mqtt.MQTT_ERR_SUCCESS:
            with sqlite3.connect(BUF_DB) as c:
                c.execute("delete from pending where id=?", (row[0],))
        else:
            break  # still offline


# -------------------------------------------------------------------- #
# update command
# -------------------------------------------------------------------- #
def on_command(_client, _userdata, msg: mqtt.MQTTMessage) -> None:
    try:
        if json.loads(msg.payload.decode()).get("action") != "update":
            return
        log.info("update requested")
        subprocess.run(["git", "-C", str(REPO_DIR), "pull"], check=True)
        os.execv(sys.executable, [sys.executable] + sys.argv)
    except Exception as exc:  # keep loop alive
        log.error("update failed: %s", exc)


# -------------------------------------------------------------------- #
# main
# -------------------------------------------------------------------- #
def main() -> None:
    init_db()

    client = mqtt.Client()
    client.connect(settings.MQTT_BROKER, settings.MQTT_PORT)
    client.subscribe(CMD_TOPIC)
    client.message_callback_add(CMD_TOPIC, on_command)
    client.loop_start()

    while True:
        if r := read_sensor():
            buffer(r)
            flush(client)
            log.debug("reading %s", r)
        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
