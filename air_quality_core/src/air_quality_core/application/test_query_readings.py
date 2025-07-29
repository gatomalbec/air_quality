from air_quality_core.application.query_readings import get_readings_for_room
from air_quality_core.domain.models import Reading


class FakeReadingRepo:
    def get_readings_for_devices_in_range(self, device_ids, start_ts, end_ts):
        return [Reading(ts=1.0, device_id="abc", pm1=1, pm25=2, pm10=3)]


class FakeMappingRepo:
    def get_device_ids_for_room(self, room, start_ts, end_ts):
        assert room == "kitchen"
        return ["abc"]


class StubUoW:
    def reading_repo(self):
        return FakeReadingRepo()

    def device_mapping_repo(self):
        return FakeMappingRepo()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


def test_get_readings_returns_expected_result():
    uow = StubUoW()
    result = get_readings_for_room(room="kitchen", start_ts=0, end_ts=10, uow=uow)
    assert len(result) == 1
    assert result[0].pm25 == 2
    assert result[0].device_id == "abc"
