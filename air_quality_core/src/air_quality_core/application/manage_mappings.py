# air_quality/application/manage_mappings.py

from typing import Optional

from air_quality_core.domain.ports import UnitOfWork


def add_device_room_mapping(
    device_id: str,
    room: str,
    start_ts: float,
    end_ts: Optional[float],
    uow: UnitOfWork,
) -> None:
    with uow:
        uow.device_mapping_repo().add_mapping(
            device_id=device_id,
            room=room,
            start_ts=start_ts,
            end_ts=end_ts,
        )
