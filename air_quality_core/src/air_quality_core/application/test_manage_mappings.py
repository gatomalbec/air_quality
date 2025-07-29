from air_quality_core.application.manage_mappings import add_device_room_mapping


class FakeMappingRepo:
    def __init__(self):
        self.calls = []

    def add_mapping(self, *args, **kwargs):
        self.calls.append(args or tuple(kwargs.values()))


class StubUoW:
    def __init__(self):
        self.map_repo = FakeMappingRepo()

    def device_mapping_repo(self):
        return self.map_repo

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        pass


def test_add_device_room_mapping():
    uow = StubUoW()
    add_device_room_mapping("abc", "kitchen", 100.0, 200.0, uow)
    assert ("abc", "kitchen", 100.0, 200.0) in uow.map_repo.calls
