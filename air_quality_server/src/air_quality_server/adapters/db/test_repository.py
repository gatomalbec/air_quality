"""
Repository tests – keep mappings alive between tests.
"""

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, insert
from sqlalchemy.orm import sessionmaker

from air_quality_server.adapters.db.repository import (
    PostgresDeviceMappingRepository,
    PostgresReadingRepository,
)
from air_quality_server.adapters.db.sqlalchemy_models import Base, DeviceRoomMappingORM, ReadingORM
from air_quality_server.utils.factories import ReadingFactory


# ───────── session fixture ─────────
@pytest.fixture()
def session():
    eng = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(eng)
    sess = sessionmaker(bind=eng, expire_on_commit=False)()
    yield sess
    sess.close()  # ← do NOT call clear_mappers()


@pytest.fixture()
def reading_repo(session):
    return PostgresReadingRepository(session)


@pytest.fixture()
def mapping_repo(session):
    return PostgresDeviceMappingRepository(session)


# ───────── helpers ─────────
def seed_reading(sess, reading):
    sess.execute(
        insert(ReadingORM).values(
            ts=reading.ts,
            device_id=reading.device_id,
            pm1=reading.pm1,
            pm25=reading.pm25,
            pm10=reading.pm10,
        )
    )


def seed_mapping(sess, *, device_id, room, start_ts, end_ts=None):
    sess.execute(
        insert(DeviceRoomMappingORM).values(
            device_id=device_id,
            room=room,
            start_ts=start_ts,
            end_ts=end_ts,
        )
    )


# ───────── Reading repo tests ─────────
def test_insert_and_delete(reading_repo, session):
    seed_reading(session, ReadingFactory(device_id="fake"))
    session.commit()

    assert reading_repo.get_latest_for_devices(["fake"])
    reading_repo.delete_device_ids_containing("fake")
    session.commit()
    assert not reading_repo.get_latest_for_devices(["fake"])


def test_get_readings_for_devices_in_range(reading_repo, session):
    now = datetime.now(tz=timezone.utc).timestamp()
    seed_reading(session, ReadingFactory(ts=now - 30, device_id="d1"))
    seed_reading(session, ReadingFactory(ts=now - 15, device_id="d1"))
    seed_reading(session, ReadingFactory(ts=now - 5, device_id="d1"))
    session.commit()

    res = reading_repo.get_readings_for_devices_in_range(
        device_ids=["d1"], start_ts=now - 20, end_ts=now
    )
    assert len(res) == 2


# ───────── Mapping repo tests ─────────
def test_add_get_delete_mapping(mapping_repo, session):
    now = datetime.now(tz=timezone.utc).timestamp()
    seed_mapping(session, device_id="fake", room="lab", start_ts=now - 10)
    session.commit()

    assert mapping_repo.get_device_ids_for_room("lab", 0, now) == ["fake"]

    mapping_repo.delete_device_ids_containing("fake")
    session.commit()
    assert mapping_repo.get_device_ids_for_room("lab", 0, now) == []
