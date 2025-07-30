__all__ = ["ReadingORM", "DeviceRoomMappingORM"]

from sqlalchemy import Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from air_quality_server.adapters.db.session import Base


class ReadingORM(Base):
    __tablename__ = "readings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    ts: Mapped[float] = mapped_column(Float, index=True, nullable=False)
    device_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    pm1: Mapped[int] = mapped_column(Integer, nullable=False)
    pm25: Mapped[int] = mapped_column(Integer, nullable=False)
    pm10: Mapped[int] = mapped_column(Integer, nullable=False)


class DeviceRoomMappingORM(Base):
    __tablename__ = "device_room_mappings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    device_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    room: Mapped[str] = mapped_column(String, index=True, nullable=False)
    start_ts: Mapped[float] = mapped_column(Float, index=True, nullable=False)
    end_ts: Mapped[float | None] = mapped_column(Float, index=True, nullable=True)
