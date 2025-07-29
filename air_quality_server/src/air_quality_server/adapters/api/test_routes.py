from air_quality_core.domain.models import Reading
from fastapi import FastAPI
from fastapi.testclient import TestClient

from air_quality_server.adapters.api.routes import get_uow, router
from air_quality_server.adapters.db.uow import SqlAlchemyUoW
from air_quality_server.utils.factories import ReadingFactory


# ───────────── fakes ─────────────
class FakeReadingRepo:
    def __init__(self):
        self.insert_calls: list[Reading] = []
        self.delete_calls: list[str] = []

    def get_readings_for_devices_in_range(self, *, device_ids, start_ts, end_ts):
        return [ReadingFactory(device_id="abc")]

    def insert(self, reading):
        self.insert_calls.append(reading)

    def delete_device_ids_containing(self, s):
        self.delete_calls.append(s)


class FakeMappingRepo:
    def __init__(self):
        self.add_calls = []
        self.delete_calls = []

    def get_device_ids_for_room(self, *, room, start_ts=None, end_ts=None):
        return ["abc"]

    def add_mapping(self, *args, **kwargs):
        # supports positional or keyword
        self.add_calls.append(args or tuple(kwargs.values()))

    def delete_device_ids_containing(self, s):
        self.delete_calls.append(s)


class StubUoW(SqlAlchemyUoW):
    def __init__(self):
        super().__init__(session=None)
        self.read_repo = FakeReadingRepo()
        self.map_repo = FakeMappingRepo()

    def reading_repo(self):
        return self.read_repo

    def device_mapping_repo(self):
        return self.map_repo

    def __exit__(self, *exc):
        pass


_SHARED = StubUoW()


def override_uow():
    yield _SHARED


# ───────── FastAPI client ─────────
app = FastAPI()
app.include_router(router)
app.dependency_overrides[get_uow] = override_uow
client = TestClient(app)


# ───────────── tests ─────────────
def test_readings_endpoint_returns_expected_payload():
    res = client.post("/readings", json={"room": "kitchen"})
    assert res.json()[0]["device_id"] == "abc"


def test_room_mapping_endpoint_calls_add_mapping():
    client.post(
        "/room-mapping",
        json={
            "device_id": "abc",
            "room": "kitchen",
            "start_ts": 100.0,
            "end_ts": 200.0,
        },
    )
    assert ("abc", "kitchen", 100.0, 200.0) in _SHARED.map_repo.add_calls


def test_ingest_endpoint_inserts_reading():
    payload = ReadingFactory(device_id="fake").__dict__
    client.post("/ingest", json=payload)
    assert any(r.device_id == "fake" for r in _SHARED.read_repo.insert_calls)


def test_admin_delete_endpoint_invokes_delete_on_both_repos():
    client.post("/admin/delete", json={"device_id_contains": "fake"})
    assert "fake" in _SHARED.read_repo.delete_calls
    assert "fake" in _SHARED.map_repo.delete_calls
