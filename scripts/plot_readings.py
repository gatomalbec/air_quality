#!/usr/bin/env python
"""
ASCII plot of PM metrics for one or more rooms.

Example
-------
poetry run plot-readings --rooms kitchen living_room --hours 1.5 --metric pm10
"""

import argparse
import datetime as dt
import sys
from typing import Dict, List, Tuple, TypedDict

import plotext as plt  # type: ignore  # third‑party library without stubs
import requests

BASE_URL = "http://localhost:8000"


# ────────────────────────── models ──────────────────────────
class Reading(TypedDict):
    ts: float
    pm1: int
    pm25: int
    pm10: int


# ─────────────────────────── API ────────────────────────────
def fetch(room: str, start_ts: float, end_ts: float) -> List[Reading]:
    resp = requests.post(
        f"{BASE_URL}/readings",
        json={"room": room, "start_ts": start_ts, "end_ts": end_ts},
        timeout=5,
    )
    resp.raise_for_status()
    return resp.json()  # type: ignore[return-value]  # runtime JSON → Reading list


# ─────────────────────────── CLI ────────────────────────────
def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--rooms", nargs="+", required=True)
    p.add_argument("--hours", type=float, default=2.0)
    p.add_argument("--metric", choices=["pm1", "pm25", "pm10"], default="pm25")
    return p.parse_args()


# ───────────────────────── helpers ──────────────────────────
def xticks(start: dt.datetime, span_min: float, n: int = 5) -> Tuple[List[float], List[str]]:
    step = span_min / (n - 1) if n > 1 else span_min
    pos = [round(i * step, 2) for i in range(n)]
    labels = [(start + dt.timedelta(minutes=m)).strftime("%H:%M") for m in pos]
    return pos, labels


# ────────────────────────── main ────────────────────────────
def main() -> None:
    args = parse_args()

    end = dt.datetime.now()
    start = end - dt.timedelta(hours=args.hours)
    start_ts, end_ts = start.timestamp(), end.timestamp()
    span_min = (end_ts - start_ts) / 60

    data: Dict[str, List[Reading]] = {room: fetch(room, start_ts, end_ts) for room in args.rooms}

    if all(not lst for lst in data.values()):
        print("No data returned.")
        sys.exit(0)

    plt.clear_figure()
    plt.title(f"{args.metric} – last {args.hours:g} h")
    plt.xlabel("local time")
    plt.ylabel(args.metric)

    for room, readings in data.items():
        if not readings:
            continue
        xs = [(r["ts"] - start_ts) / 60 for r in readings]  # minutes
        ys = [r[args.metric] for r in readings]  # type: ignore[index,literal-required]
        plt.plot(xs, ys, label=room)

    pos, labels = xticks(start, span_min)
    plt.xticks(pos, labels)

    plt.show()


if __name__ == "__main__":
    main()
