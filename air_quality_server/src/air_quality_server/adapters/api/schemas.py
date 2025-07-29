# air_quality/adapters/api/schemas.py

from typing import Optional

from pydantic import BaseModel, Field


class RoomHistoryRequest(BaseModel):
    room: str
    start_ts: Optional[float] = Field(None, description="Start timestamp (inclusive)")
    end_ts: Optional[float] = Field(None, description="End timestamp (inclusive)")


class DeviceRoomMappingIn(BaseModel):
    device_id: str
    room: str
    start_ts: float
    end_ts: Optional[float] = None


class ReadingOut(BaseModel):
    ts: float
    device_id: str
    pm1: int
    pm25: int
    pm10: int

    @classmethod
    def from_domain(cls, reading) -> "ReadingOut":
        return cls(
            ts=reading.ts,
            device_id=reading.device_id,
            pm1=reading.pm1,
            pm25=reading.pm25,
            pm10=reading.pm10,
        )


class ReadingIn(BaseModel):
    ts: float
    device_id: str
    pm1: int
    pm25: int
    pm10: int


class DeleteRequest(BaseModel):
    device_id_contains: str = Field(..., description="Substring that marks records to delete")
