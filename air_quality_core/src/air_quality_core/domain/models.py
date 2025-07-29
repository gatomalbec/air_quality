from dataclasses import dataclass
from typing import Optional


@dataclass
class Reading:
    ts: float
    device_id: str
    pm1: int
    pm25: int
    pm10: int


@dataclass
class RoomReading(Reading):
    room: str


@dataclass
class DeviceRoomMapping:
    device_id: str
    room: str
    start_ts: float
    end_ts: Optional[float] = None  # None means active
