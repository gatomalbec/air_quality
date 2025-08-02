from air_quality_sensor.sensing.pms5003 import PMS5003
from air_quality_sensor.utils.mocks import BadChecksumFakePMS5003, FakePMS5003, TimeoutFakePMS5003


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
    """Test handling of timeout errors."""
    mock = TimeoutFakePMS5003()
    sensor = PMS5003(mock)

    reading = sensor.read()

    # Should return None on timeout after all retries
    assert reading is None
    assert sensor.timeouts == 3  # 3 retries by default


def test_bad_checksum_error():
    """Test handling of bad checksum errors."""
    mock = BadChecksumFakePMS5003()
    sensor = PMS5003(mock)

    reading = sensor.read()

    # Should return None on bad checksum after all retries
    assert reading is None
    assert sensor.crc_errors == 3  # 3 retries by default


def test_multiple_readings():
    """Test multiple consecutive readings."""
    mock = FakePMS5003(pm1_cf=10, pm2_5_cf=15, pm10_cf=20)
    sensor = PMS5003(mock)

    # Take multiple readings
    reading1 = sensor.read()
    reading2 = sensor.read()
    reading3 = sensor.read()

    # All readings should be successful
    assert reading1 is not None
    assert reading2 is not None
    assert reading3 is not None
    assert reading1.pm1_cf == 10
    assert reading2.pm1_cf == 10
    assert reading3.pm1_cf == 10
