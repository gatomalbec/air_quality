import queue
import time
from unittest.mock import Mock

from air_quality_sensor.poller import BaseSensorThread
from air_quality_sensor.sensor_types import Serializable


class MockPayload(Serializable):
    """Mock payload for testing"""

    def __init__(self, value: int):
        self.value = value

    def to_string(self) -> str:
        return str(self.value)


def test_stop_sets_event():
    """Test that stop() sets the stop event"""
    mock_driver = Mock()
    out_q: queue.Queue = queue.Queue()

    thread = BaseSensorThread(
        name="test_thread",
        interval_s=1.0,
        device_id="test_device",
        driver=mock_driver,
        out_q=out_q,
    )

    assert not thread.s_stop.is_set()
    thread.stop()
    assert thread.s_stop.is_set()


def test_run_with_successful_readings():
    """Test run() method with successful sensor readings"""
    mock_payload = MockPayload(42)
    mock_driver = Mock()
    mock_driver.return_value = mock_payload

    out_q: queue.Queue = queue.Queue()

    thread = BaseSensorThread(
        name="test_thread",
        interval_s=0.1,  # Fast polling for test
        device_id="test_device",
        driver=mock_driver,
        out_q=out_q,
    )

    # Start thread and let it run briefly
    thread.start()
    time.sleep(0.2)  # Let it run for a short time
    thread.stop()
    thread.join(timeout=1.0)

    # Verify driver was called
    assert mock_driver.call_count >= 1

    # Verify reading was put in queue
    assert not out_q.empty()
    reading_str = out_q.get_nowait()
    assert isinstance(reading_str, str)
    # Parse the JSON to verify structure
    import json

    reading_data = json.loads(reading_str)
    assert reading_data["device_id"] == "test_device"
    assert reading_data["payload"] == "42"  # MockPayload.to_string() returns str(value)
    assert reading_data["ts"] > 0


def test_run_with_failed_readings():
    """Test run() method when driver returns None"""
    mock_driver = Mock()
    mock_driver.return_value = None  # Simulate failed reading

    out_q: queue.Queue = queue.Queue()

    thread = BaseSensorThread(
        name="test_thread",
        interval_s=0.1,  # Fast polling for test
        device_id="test_device",
        driver=mock_driver,
        out_q=out_q,
    )

    # Start thread and let it run briefly
    thread.start()
    time.sleep(0.2)  # Let it run for a short time
    thread.stop()
    thread.join(timeout=1.0)

    # Verify driver was called
    assert mock_driver.call_count >= 1

    # Verify no reading was put in queue
    assert out_q.empty()


def test_run_with_full_queue():
    """Test run() method when queue is full"""
    mock_payload = MockPayload(42)
    mock_driver = Mock()
    mock_driver.return_value = mock_payload

    # Create a queue with maxsize=1 and put one item in it
    out_q: queue.Queue = queue.Queue(maxsize=1)
    out_q.put(MockPayload(999))  # Fill the queue

    thread = BaseSensorThread(
        name="test_thread",
        interval_s=0.1,  # Fast polling for test
        device_id="test_device",
        driver=mock_driver,
        out_q=out_q,
    )

    # Start thread and let it run briefly
    thread.start()
    time.sleep(0.2)  # Let it run for a short time
    thread.stop()
    thread.join(timeout=1.0)

    # Verify driver was called
    assert mock_driver.call_count >= 1

    # Verify queue is still full (no new items added)
    assert out_q.qsize() == 1


def test_run_stops_when_stop_flag_set():
    """Test that run() stops when stop flag is set"""
    mock_driver = Mock()
    mock_driver.return_value = MockPayload(42)

    out_q: queue.Queue = queue.Queue()

    thread = BaseSensorThread(
        name="test_thread",
        interval_s=1.0,  # Long interval
        device_id="test_device",
        driver=mock_driver,
        out_q=out_q,
    )

    # Set stop flag before starting
    thread.s_stop.set()

    # Start thread
    thread.start()
    thread.join(timeout=1.0)

    # Verify thread stopped without calling driver
    assert mock_driver.call_count == 0


def test_run_handles_driver_exception():
    """Test that run() handles exceptions from driver gracefully"""
    mock_driver = Mock()
    mock_driver.side_effect = Exception("Driver error")

    out_q: queue.Queue = queue.Queue()

    thread = BaseSensorThread(
        name="test_thread",
        interval_s=0.1,  # Fast polling for test
        device_id="test_device",
        driver=mock_driver,
        out_q=out_q,
    )

    # Start thread and let it run briefly
    thread.start()
    time.sleep(0.15)  # Wait longer than the interval to ensure first call
    thread.stop()
    thread.join(timeout=1.0)

    # Verify driver was called (even though it raised an exception)
    assert mock_driver.call_count >= 1

    # Verify no reading was put in queue due to exception
    assert out_q.empty()


def test_multiple_readings_over_time():
    """Test multiple readings over time with different payloads"""
    mock_driver = Mock()
    # Provide enough values to avoid StopIteration
    mock_driver.side_effect = [
        MockPayload(1),
        MockPayload(2),
        MockPayload(3),
        None,  # Failed reading
        MockPayload(4),
        MockPayload(5),
        MockPayload(6),
        MockPayload(7),
        MockPayload(8),
        MockPayload(9),
        MockPayload(10),
    ]

    out_q: queue.Queue = queue.Queue()

    thread = BaseSensorThread(
        name="test_thread",
        interval_s=0.05,  # Very fast polling for test
        device_id="test_device",
        driver=mock_driver,
        out_q=out_q,
    )

    # Start thread and let it run briefly
    thread.start()
    time.sleep(0.2)  # Shorter time to avoid running out of mock values
    thread.stop()
    thread.join(timeout=1.0)

    # Verify multiple readings were collected
    readings = []
    while not out_q.empty():
        readings.append(out_q.get_nowait())

    # Should have at least 2 successful readings (excluding the None)
    assert len(readings) >= 2

    # Verify all readings have correct structure
    for reading_str in readings:
        assert isinstance(reading_str, str)
        # Parse the JSON to verify structure
        import json

        reading_data = json.loads(reading_str)
        assert "device_id" in reading_data
        assert "payload" in reading_data
        assert "ts" in reading_data
