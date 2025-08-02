# air_quality/adapters/api/routes.py

from air_quality_core.application.delete_data import delete_readings_matching
from air_quality_core.application.ingest_reading import ingest_reading
from air_quality_core.application.manage_mappings import add_device_room_mapping
from air_quality_core.application.query_readings import get_readings_for_room
from air_quality_core.domain.models import Reading
from fastapi import APIRouter, Depends

from air_quality_server.adapters.api.schemas import (
    DeleteRequest,
    DeviceRoomMappingIn,
    ReadingIn,
    ReadingOut,
    RoomHistoryRequest,
)
from air_quality_server.adapters.db.uow import SqlAlchemyUoW

router = APIRouter()


def get_uow():
    with SqlAlchemyUoW() as uow:
        yield uow


@router.get("/ping")
def ping():
    return {"status": "ok"}


@router.post("/readings", response_model=list[ReadingOut])
def readings(
    req: RoomHistoryRequest,
    uow: SqlAlchemyUoW = Depends(get_uow),
):
    results = get_readings_for_room(
        room=req.room,
        start_ts=req.start_ts,
        end_ts=req.end_ts,
        uow=uow,
    )
    return [ReadingOut.from_domain(r) for r in results]


@router.post("/room-mapping")
def add_mapping(
    mapping: DeviceRoomMappingIn,
    uow: SqlAlchemyUoW = Depends(get_uow),
):
    add_device_room_mapping(
        device_id=mapping.device_id,
        room=mapping.room,
        start_ts=mapping.start_ts,
        end_ts=mapping.end_ts,
        uow=uow,
    )
    return {"status": "ok"}


@router.post("/ingest")
def ingest_reading_endpoint(
    reading_in: ReadingIn,
    uow: SqlAlchemyUoW = Depends(get_uow),
):
    reading = Reading(**reading_in.model_dump())
    with uow:
        ingest_reading(reading, uow)
    return {"status": "ok"}


@router.post("/admin/delete")
def delete_data(req: DeleteRequest, uow: SqlAlchemyUoW = Depends(get_uow)):
    delete_readings_matching(req.device_id_contains, uow)
    return {"status": "ok"}
