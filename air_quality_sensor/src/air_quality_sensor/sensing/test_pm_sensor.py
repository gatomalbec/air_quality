import time

from factory import Factory, Faker

from air_quality_sensor.sensing.pms5003 import (
    PMS5003,
    PMS5003Config,
    PMS5003Protocol,
    PMS5003Reading,
)
from air_quality_sensor.utils.mocks import BadChecksumFakePMS5003, FakePMS5003, TimeoutFakePMS5003


class PMS5003ReadingFactory(Factory):
    """Factory for creating PMS5003Reading instances with realistic test data."""

    class Meta:
        model = PMS5003Reading

    ts = Faker("unix_time")
    pm1_cf = Faker("random_int", min=0, max=100)
    pm25_cf = Faker("random_int", min=0, max=100)
    pm10_cf = Faker("random_int", min=0, max=100)
    pm1_atm = Faker("random_int", min=0, max=100)
    pm25_atm = Faker("random_int", min=0, max=100)
    pm10_atm = Faker("random_int", min=0, max=100)


def test_pms5003_reading_creation():
    """Test that PMS5003Reading can be created with valid data."""
    reading = PMS5003Reading(
        ts=1234567890.0,
        pm1_cf=10,
        pm25_cf=15,
        pm10_cf=20,
        pm1_atm=12,
        pm25_atm=18,
        pm10_atm=25,
    )

    assert reading.ts == 1234567890.0
    assert reading.pm1_cf == 10
    assert reading.pm25_cf == 15
    assert reading.pm10_cf == 20
    assert reading.pm1_atm == 12
    assert reading.pm25_atm == 18
    assert reading.pm10_atm == 25


def test_pms5003_config_defaults():
    """Test that PMS5003Config has correct default values."""
    config = PMS5003Config()

    assert config.max_retries == 3
    assert config.timeout_seconds == 1.0


def test_pms5003_config_custom_values():
    """Test that PMS5003Config can be created with custom values."""
    config = PMS5003Config(max_retries=5, timeout_seconds=2.5)

    assert config.max_retries == 5
    assert config.timeout_seconds == 2.5


def test_pms5003_protocol_defaults():
    """Test that PMS5003Protocol has correct default values."""
    protocol = PMS5003Protocol()

    assert protocol.header == b"\x42\x4d"
    assert protocol.frame_length == 32
    assert protocol.data_length == 26
    assert protocol.checksum_length == 2
    assert protocol.data_start_offset == 4
    assert protocol.checksum_start_offset == 30
    assert protocol.unpack_format == ">13H"
    assert protocol.data_end_offset == 30
    assert protocol.checksum_end_offset == 32


def test_pms5003_initialization():
    """Test basic PMS5003 initialization."""
    mock = FakePMS5003()
    sensor = PMS5003(mock)

    assert sensor.config.max_retries == 3
    assert sensor.config.timeout_seconds == 1.0
    assert sensor.protocol.frame_length == 32
    assert sensor.crc_errors == 0
    assert sensor.timeouts == 0


def test_pms5003_initialization_with_custom_config():
    """Test PMS5003 initialization with custom configuration."""
    mock = FakePMS5003()
    config = PMS5003Config(max_retries=5, timeout_seconds=2.0)
    sensor = PMS5003(mock, config)

    assert sensor.config.max_retries == 5
    assert sensor.config.timeout_seconds == 2.0


def test_pms5003_initialization_with_custom_protocol():
    """Test PMS5003 initialization with custom protocol configuration."""
    mock = FakePMS5003()
    protocol = PMS5003Protocol(frame_length=64, data_length=58)
    sensor = PMS5003(mock, protocol=protocol)

    assert sensor.protocol.frame_length == 64
    assert sensor.protocol.data_length == 58


def test_successful_reading():
    """Test successful reading from sensor with valid frame."""
    mock = FakePMS5003(
        pm1_cf=10,
        pm2_5_cf=15,
        pm10_cf=20,
        pm1_atm=12,
        pm2_5_atm=18,
        pm10_atm=25,
    )

    sensor = PMS5003(mock)
    reading = sensor.read()

    # Verify reading was successful
    assert reading is not None
    assert reading.pm1_cf == 10
    assert reading.pm25_cf == 15
    assert reading.pm10_cf == 20
    assert reading.pm1_atm == 12
    assert reading.pm25_atm == 18
    assert reading.pm10_atm == 25


def test_timeout_error():
    """Test handling of timeout error (incomplete frame)."""
    mock = TimeoutFakePMS5003(
        pm1_cf=10,
        pm2_5_cf=15,
        pm10_cf=20,
    )

    sensor = PMS5003(mock)
    reading = sensor.read()

    # Verify reading failed due to timeout
    assert reading is None
    assert sensor.timeouts == 3  # All 3 attempts failed due to timeout
    assert sensor.crc_errors == 0


def test_bad_checksum_error():
    """Test handling of CRC error (invalid checksum)."""
    mock = BadChecksumFakePMS5003(
        pm1_cf=10,
        pm2_5_cf=15,
        pm10_cf=20,
    )

    sensor = PMS5003(mock)
    reading = sensor.read()

    # Verify reading failed due to bad checksum
    assert reading is None
    assert sensor.crc_errors == 3  # All 3 attempts failed due to bad checksum
    assert sensor.timeouts == 0


def test_retry_logic_success_on_second_attempt():
    """Test that retry logic succeeds on second attempt."""

    class IntermittentFakePMS5003(FakePMS5003):
        """Mock that fails first attempt, succeeds on second."""

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._sensor_read_count = 0

        def write(self, data: bytes) -> int:
            # Count sensor read attempts (REQ_FRAME commands)
            if data == self.protocol.req_frame_cmd:
                self._sensor_read_count += 1
            return super().write(data)

        def read(self, n: int = 1) -> bytes:
            if self._sensor_read_count == 1:
                # First sensor read attempt: return incomplete frame (timeout)
                return b"incomplete"
            else:
                # Subsequent attempts: return valid frame
                return super().read(n)

    mock = IntermittentFakePMS5003(pm1_cf=10, pm2_5_cf=15, pm10_cf=20)
    config = PMS5003Config(max_retries=3, timeout_seconds=0.1)
    sensor = PMS5003(mock, config)

    reading = sensor.read()

    # Should succeed on second attempt
    assert reading is not None
    assert reading.pm1_cf == 10
    assert sensor.timeouts == 1  # First attempt failed
    assert sensor.crc_errors == 0


def test_retry_logic_all_attempts_fail():
    """Test that retry logic gives up after all attempts fail."""
    mock = BadChecksumFakePMS5003(pm1_cf=10, pm2_5_cf=15, pm10_cf=20)
    config = PMS5003Config(max_retries=2, timeout_seconds=0.1)
    sensor = PMS5003(mock, config)

    start_time = time.time()
    reading = sensor.read()
    end_time = time.time()

    # Should fail after all retries
    assert reading is None
    assert sensor.crc_errors == 2  # All 2 attempts failed (max_retries=2 means 2 total attempts)
    assert sensor.timeouts == 0

    # Should have waited between attempts
    elapsed_time = end_time - start_time
    assert elapsed_time >= config.timeout_seconds  # At least one timeout period


def test_retry_logic_no_wait_on_last_attempt():
    """Test that no wait occurs after the last retry attempt."""
    mock = BadChecksumFakePMS5003(pm1_cf=10, pm2_5_cf=15, pm10_cf=20)
    config = PMS5003Config(max_retries=1, timeout_seconds=1.0)  # 1 retry = 2 total attempts
    sensor = PMS5003(mock, config)

    start_time = time.time()
    reading = sensor.read()
    end_time = time.time()

    # Should fail after all retries
    assert reading is None
    assert sensor.crc_errors == 1  # All 1 attempts failed (max_retries=1 means 1 total attempt)

    # Should not wait after last attempt
    elapsed_time = end_time - start_time
    assert elapsed_time < config.timeout_seconds  # No wait after last attempt


def test_multiple_readings():
    """Test multiple consecutive readings."""
    mock = FakePMS5003(
        pm1_cf=10,
        pm2_5_cf=15,
        pm10_cf=20,
    )

    sensor = PMS5003(mock)

    # Take first reading
    reading1 = sensor.read()
    assert reading1 is not None
    assert reading1.pm1_cf == 10

    # Take second reading
    reading2 = sensor.read()
    assert reading2 is not None
    assert reading2.pm1_cf == 10

    # Readings should be different timestamps
    assert reading1.ts != reading2.ts


def test_error_counters_increment():
    """Test that error counters increment properly on multiple failures."""
    # Test timeout counter
    timeout_mock = TimeoutFakePMS5003()
    timeout_sensor = PMS5003(timeout_mock)

    # Multiple timeout attempts
    for _ in range(3):
        reading = timeout_sensor.read()
        assert reading is None

    assert timeout_sensor.timeouts == 9  # 3 calls * 3 attempts each = 9 timeouts
    assert timeout_sensor.crc_errors == 0

    # Test CRC error counter
    bad_checksum_mock = BadChecksumFakePMS5003()
    bad_checksum_sensor = PMS5003(bad_checksum_mock)

    # Multiple CRC error attempts
    for _ in range(2):
        reading = bad_checksum_sensor.read()
        assert reading is None

    assert bad_checksum_sensor.crc_errors == 6  # 2 calls * 3 attempts each = 6 CRC errors
    assert bad_checksum_sensor.timeouts == 0


def test_checksum_validation():
    """Test the _checksum_ok method."""
    # Create a valid frame using the mock
    mock = FakePMS5003(pm1_cf=10, pm2_5_cf=15, pm10_cf=20)
    valid_frame = mock._create_sensor_frame()

    sensor = PMS5003(mock)
    assert sensor._checksum_ok(valid_frame) is True

    # Test with invalid checksum
    invalid_frame = valid_frame[:-2] + b"\x00\x00"
    assert sensor._checksum_ok(invalid_frame) is False


def test_frame_parsing():
    """Test the _parse method."""
    mock = FakePMS5003(pm1_cf=10, pm2_5_cf=15, pm10_cf=20)
    valid_frame = mock._create_sensor_frame()

    sensor = PMS5003(mock)
    reading = sensor._parse(valid_frame)

    assert reading.pm1_cf == 10
    assert reading.pm25_cf == 15
    assert reading.pm10_cf == 20


def test_pms5003_reading_factory_creates_valid_data():
    """Test that the factory creates valid PMS5003Reading instances."""
    reading = PMS5003ReadingFactory()

    assert isinstance(reading.ts, float)
    assert isinstance(reading.pm1_cf, int)
    assert isinstance(reading.pm25_cf, int)
    assert isinstance(reading.pm10_cf, int)
    assert isinstance(reading.pm1_atm, int)
    assert isinstance(reading.pm25_atm, int)
    assert isinstance(reading.pm10_atm, int)


def test_pms5003_reading_factory_with_custom_values():
    """Test that the factory can create readings with custom values."""
    reading = PMS5003ReadingFactory(
        pm1_cf=42,
        pm25_cf=84,
        pm10_cf=126,
    )

    assert reading.pm1_cf == 42
    assert reading.pm25_cf == 84
    assert reading.pm10_cf == 126


def test_mock_sensor_protocol():
    """Test that the mock properly simulates the sensor protocol."""
    mock = FakePMS5003(pm1_cf=10, pm2_5_cf=15, pm10_cf=20)

    # Test SET_PASSIVE command
    result = mock.write(mock.protocol.set_passive_cmd)
    assert result == 6

    # Test REQ_FRAME command
    result = mock.write(mock.protocol.req_frame_cmd)
    assert result == 6

    # Read the response
    response = mock.read(32)
    assert len(response) == 32


def test_mock_sensor_state():
    """Test that the mock maintains proper sensor state."""
    mock = FakePMS5003(pm1_cf=10, pm2_5_cf=15, pm10_cf=20)

    # Initially not in passive mode
    assert not mock._passive_mode

    # Send SET_PASSIVE command
    mock.write(mock.protocol.set_passive_cmd)
    assert mock._passive_mode

    # Send REQ_FRAME command
    mock.write(mock.protocol.req_frame_cmd)
    assert mock._next_response is not None


def test_read_sensor():
    """Legacy test for the old read_sensor function."""
    sensor = FakePMS5003(
        pm1_cf=10,
        pm10_atm=15,
    )
    # Note: This test would need to be updated if read_sensor function still exists
    # For now, we'll test the new class-based approach
    pms = PMS5003(sensor)
    reading = pms.read()
    assert reading is not None
