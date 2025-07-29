from air_quality_core.application.delete_data import delete_readings_matching


class FakeRepo:
    def __init__(self):
        self.calls = []

    def delete_device_ids_containing(self, substr):
        self.calls.append(substr)


class StubUoW:
    def __init__(self):
        self.read_repo = FakeRepo()
        self.map_repo = FakeRepo()

    def reading_repo(self):
        return self.read_repo

    def device_mapping_repo(self):
        return self.map_repo

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        pass


def test_delete_readings_matching_invokes_both_repos():
    uow = StubUoW()
    delete_readings_matching("fake", uow)
    assert uow.read_repo.calls == ["fake"]
    assert uow.map_repo.calls == ["fake"]
