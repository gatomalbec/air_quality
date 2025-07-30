from typing import List, Optional

from air_quality_core.domain.models import Reading
from air_quality_core.domain.ports import ReadingRepository
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from air_quality_server.adapters.db.sqlalchemy_models import (
    DeviceRoomMappingORM,
    ReadingORM,
)


class PostgresReadingRepository(ReadingRepository):
    def __init__(self, session: Session):
        self.session = session

    # READ side
    def get_latest_for_devices(self, device_ids: List[str], limit: int = 100) -> List[Reading]:
        if not device_ids:
            return []
        stmt = (
            select(ReadingORM)
            .where(ReadingORM.device_id.in_(device_ids))
            .order_by(ReadingORM.ts.desc())
            .limit(limit)
        )
        return [self._to_domain(r) for r in self.session.scalars(stmt).all()]

    def get_readings_for_devices_in_range(
        self,
        device_ids: List[str],
        start_ts: Optional[float],
        end_ts: Optional[float],
    ) -> List[Reading]:
        if not device_ids:
            return []
        stmt = select(ReadingORM).where(ReadingORM.device_id.in_(device_ids))
        if start_ts is not None:
            stmt = stmt.where(ReadingORM.ts >= start_ts)
        if end_ts is not None:
            stmt = stmt.where(ReadingORM.ts <= end_ts)
        stmt = stmt.order_by(ReadingORM.ts.asc())
        return [self._to_domain(r) for r in self.session.scalars(stmt).all()]

    def insert(self, reading: Reading) -> None:
        row = ReadingORM()  # no keyword args
        row.ts = reading.ts
        row.device_id = reading.device_id
        row.pm1 = reading.pm1
        row.pm25 = reading.pm25
        row.pm10 = reading.pm10
        self.session.add(row)

    def delete_device_ids_containing(self, substr: str) -> None:
        stmt = delete(ReadingORM).where(ReadingORM.device_id.contains(substr))
        self.session.execute(stmt)

    # helper
    @staticmethod
    def _to_domain(row: ReadingORM) -> Reading:
        return Reading(
            ts=row.ts,
            device_id=row.device_id,
            pm1=row.pm1,
            pm25=row.pm25,
            pm10=row.pm10,
        )


class PostgresDeviceMappingRepository:
    def __init__(self, session: Session):
        self.session = session

    # READ
    def get_device_ids_for_room(
        self, room: str, start_ts: Optional[float], end_ts: Optional[float]
    ) -> List[str]:
        stmt = select(DeviceRoomMappingORM).where(DeviceRoomMappingORM.room == room)
        if start_ts is not None:
            stmt = stmt.where(DeviceRoomMappingORM.start_ts <= (end_ts or float("inf")))
        if end_ts is not None:
            stmt = stmt.where(
                (DeviceRoomMappingORM.end_ts.is_(None))  # current mapping
                | (DeviceRoomMappingORM.end_ts >= start_ts)
            )
        rows = self.session.scalars(stmt).all()
        return [row.device_id for row in rows]

    # WRITE
    def add_mapping(
        self,
        device_id: str,
        room: str,
        start_ts: float,
        end_ts: Optional[float] = None,
    ) -> None:
        mapping = DeviceRoomMappingORM()
        mapping.device_id = device_id
        mapping.room = room
        mapping.start_ts = start_ts
        mapping.end_ts = end_ts
        self.session.add(mapping)

    def delete_device_ids_containing(self, substr: str) -> None:
        stmt = delete(DeviceRoomMappingORM).where(DeviceRoomMappingORM.device_id.contains(substr))
        self.session.execute(stmt)
