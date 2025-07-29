__all__ = ["ReadingORM", "DeviceRoomMappingORM"]

from sqlalchemy import Column, Float, Integer, String

from air_quality_server.adapters.db.session import Base


class ReadingORM(Base):
    __tablename__ = "readings"

    id = Column(Integer, primary_key=True, index=True)
    ts = Column(Float, index=True)
    device_id = Column(String, index=True)
    pm1 = Column(Integer)
    pm25 = Column(Integer)
    pm10 = Column(Integer)


class DeviceRoomMappingORM(Base):
    __tablename__ = "device_room_mappings"

    id = Column(Integer, primary_key=True)
    device_id = Column(String, index=True)
    room = Column(String, index=True)
    start_ts = Column(Float, index=True)
    end_ts = Column(Float, index=True, nullable=True)
