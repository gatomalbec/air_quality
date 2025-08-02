import pytest

from air_quality_sensor.utils.mocks import FakePMS5003


@pytest.fixture()
def fake_pms5003():
    fake = FakePMS5003()
    yield fake
    fake.reset_input_buffer()
