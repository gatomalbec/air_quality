import json
import os
import socket
import sqlite3
import struct
import subprocess
import sys
import time

import paho.mqtt.client as mqtt
import serial

# Configuration
DEVICE_ID = socket.gethostname()
BROKER_HOST = "192.168.2.254"  # IP of your MQTT broker
BROKER_PORT = 1883
TOPIC = f"air/{DEVICE_ID}"
COMMAND_TOPIC = f"commands/{DEVICE_ID}"
BUFFER_DB = "buffer.db"
REPO_DIR = "/home/pi/sensor"  # path to git repo

# Sensor setup
ser = serial.Serial("/dev/serial0", baudrate=9600, timeout=1)


# SQLite buffer table
def init_db():
    with sqlite3.connect(BUFFER_DB) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS pending (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts REAL,
                device_id TEXT,
                pm1 INTEGER,
                pm25 INTEGER,
                pm10 INTEGER
            )
        """)


# Read from PMS5003
def read_sensor():
    frame = ser.read(32)
    if len(frame) != 32 or frame[0:2] != b"\x42\x4d":
        return None
    data = struct.unpack(">HHHHHHHHHHHHHH", frame[4:32])
    return {
        "ts": time.time(),
        "device_id": DEVICE_ID,
        "pm1": data[3],
        "pm25": data[4],
        "pm10": data[5],
    }


# Buffer to disk
def buffer_reading(r):
    with sqlite3.connect(BUFFER_DB) as conn:
        conn.execute(
            "INSERT INTO pending (ts, device_id, pm1, pm25, pm10) VALUES (?, ?, ?, ?, ?)",
            (r["ts"], r["device_id"], r["pm1"], r["pm25"], r["pm10"]),
        )


# Publish buffered readings
def flush_buffer(client):
    with sqlite3.connect(BUFFER_DB) as conn:
        rows = conn.execute("SELECT * FROM pending ORDER BY id").fetchall()

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
        result = client.publish(TOPIC, payload, qos=1)
        if result.rc == mqtt.MQTT_ERR_SUCCESS:
            with sqlite3.connect(BUFFER_DB) as conn:
                conn.execute("DELETE FROM pending WHERE id = ?", (row[0],))
        else:
            break  # broker unreachable — stop retry loop


# Handle MQTT command messages
def on_command(client, userdata, msg):
    try:
        payload = json.loads(msg.payload.decode())
        if payload.get("action") == "update":
            print("Received update command. Pulling code...")
            subprocess.run(["git", "-C", REPO_DIR, "pull"], check=True)
            print("Restarting process with new code.")
            os.execv(sys.executable, [sys.executable] + sys.argv)
    except Exception as e:
        print(f"Update failed: {e}")


# Setup and main loop
def main():
    init_db()

    client = mqtt.Client()
    client.connect(BROKER_HOST, BROKER_PORT)
    client.loop_start()

    # Subscribe to command topic
    client.subscribe(COMMAND_TOPIC)
    client.message_callback_add(COMMAND_TOPIC, on_command)

    while True:
        reading = read_sensor()
        if reading:
            buffer_reading(reading)
            flush_buffer(client)
            print(f"Reading: {reading}")
        time.sleep(10)


if __name__ == "__main__":
    main()
