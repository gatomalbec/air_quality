import json
import sqlite3

import paho.mqtt.client as mqtt

DB_PATH = "sensor_data.db"


# Init SQLite table
def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS readings (
                ts REAL,
                room TEXT,
                pm1 INTEGER,
                pm25 INTEGER,
                pm10 INTEGER
            )
        """)


# Handle incoming messages
def on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload.decode())
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                "INSERT INTO readings (ts, room, pm1, pm25, pm10) VALUES (?, ?, ?, ?, ?)",
                (
                    payload["ts"],
                    payload["room"],
                    payload["pm1"],
                    payload["pm25"],
                    payload["pm10"],
                ),
            )
        print(f"Stored data from {payload['room']} at {payload['ts']}")
    except Exception as e:
        print(f"Error processing message: {e}")


# Setup MQTT client
def run():
    init_db()
    client = mqtt.Client()
    client.on_message = on_message
    client.connect("localhost", 1883)
    client.subscribe("air/#")  # Subscribe to all room topics
    client.loop_forever()


if __name__ == "__main__":
    run()
