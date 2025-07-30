"""
Generate or wipe test data via the running FastAPI service.

Usage examples
──────────────
# wipe previous fake data, then insert new readings & mappings
poetry run python src/scripts/generate_fake_data.py \
    --device-id sensor-fake-001 --wipe
"""

import argparse
import random
from datetime import datetime, timedelta, timezone

import requests

BASE_URL = "http://localhost:8000"
MAGIC_IDENTIFIER = "fake"


# ─────────────────────────── HTTP helper ────────────────────────────
def post(endpoint: str, payload: dict) -> None:
    r = requests.post(f"{BASE_URL}{endpoint}", json=payload, timeout=5)
    r.raise_for_status()


# ─────────────────────────── API helpers ────────────────────────────
def insert_room_mapping(device_id: str, room: str, start_ts: float, end_ts: float | None):
    post(
        "/room-mapping",
        {
            "device_id": device_id,
            "room": room,
            "start_ts": start_ts,
            "end_ts": end_ts,
        },
    )


def insert_reading(device_id: str, ts: float):
    post(
        "/ingest",
        {
            "ts": ts,
            "device_id": device_id,
            "pm1": random.randint(1, 10),
            "pm25": random.randint(5, 30),
            "pm10": random.randint(10, 50),
        },
    )


def generate_data(
    device_id: str,
    room_sequence: list[str],
    start_time: datetime,
    readings_per_room: int,
    interval_seconds: int,
) -> None:
    current_ts = start_time.timestamp()
    for room in room_sequence:
        end_ts = current_ts + readings_per_room * interval_seconds
        insert_room_mapping(device_id, room, current_ts, end_ts)
        for _ in range(readings_per_room):
            insert_reading(device_id, current_ts)
            current_ts += interval_seconds


def wipe_data(device_id: str) -> None:
    if MAGIC_IDENTIFIER not in device_id:
        raise ValueError(
            f"Refusing to wipe device_id={device_id!r} "
            f"(missing magic identifier '{MAGIC_IDENTIFIER}')"
        )
    post("/admin/delete", {"device_id_contains": device_id})


# ───────────────────────────── CLI ─────────────────────────────
def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--device-id", default="fake")
    parser.add_argument("--wipe", action="store_true")
    parser.add_argument(
        "--start-now",
        action="store_true",
        help="start at current UTC time instead of now‑2h",
    )
    args = parser.parse_args()

    if args.wipe:
        wipe_data(args.device_id)

    # pick start time
    if args.start_now:
        start = datetime.now(tz=timezone.utc)
    else:
        start = datetime.now(tz=timezone.utc) - timedelta(hours=2)

    generate_data(
        device_id=args.device_id,
        room_sequence=["kitchen", "living_room", "bedroom"],
        start_time=start,
        readings_per_room=20,
        interval_seconds=60,
    )
    print("Done.")


if __name__ == "__main__":
    main()
