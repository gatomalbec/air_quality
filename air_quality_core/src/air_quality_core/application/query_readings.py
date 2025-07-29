# air_quality/application/query_readings.py

from typing import List, Optional

from air_quality_core.domain.models import Reading
from air_quality_server.adapters.db.uow import SqlAlchemyUoW


def get_readings_for_room(
    room: str,
    start_ts: Optional[float],
    end_ts: Optional[float],
    uow: SqlAlchemyUoW,
) -> List[Reading]:
    with uow:
        device_ids = uow.device_mapping_repo().get_device_ids_for_room(
            room=room, start_ts=start_ts, end_ts=end_ts
        )
        if not device_ids:
            return []
        return uow.reading_repo().get_readings_for_devices_in_range(
            device_ids=device_ids,
            start_ts=start_ts,
            end_ts=end_ts,
        )
