import sqlite3

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

DB_PATH = "sensor_data.db"

app = FastAPI()
app.mount("/static", StaticFiles(directory="static", html=True), name="static")
print("hello motherfuckers")


def row_to_dict(row):
    return {"ts": row[0], "room": row[1], "pm1": row[2], "pm25": row[3], "pm10": row[4]}


@app.get("/latest")
def latest():
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute("SELECT * FROM readings ORDER BY ts DESC LIMIT 1").fetchone()
    return JSONResponse(row_to_dict(row)) if row else JSONResponse({})


@app.get("/room/{room}")
def latest_for_room(room: str):
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT * FROM readings WHERE room = ? ORDER BY ts DESC LIMIT 1", (room,)
        ).fetchone()
    return JSONResponse(row_to_dict(row)) if row else JSONResponse({})


@app.get("/history/{room}")
def history(room: str):
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            "SELECT ts, pm1, pm25, pm10 FROM readings WHERE room = ? ORDER BY ts DESC LIMIT 100",
            (room,),
        ).fetchall()
    return [
        {"ts": ts, "pm1": pm1, "pm25": pm25, "pm10": pm10}
        for ts, pm1, pm25, pm10 in rows[::-1]
    ]
