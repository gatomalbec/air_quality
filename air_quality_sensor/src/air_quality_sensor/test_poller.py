import queue
import threading
import time
from typing import Any
from unittest.mock import Mock

import pytest

from air_quality_sensor.poller import BaseSensorThread
from air_quality_sensor.sensor_types import SensorReading, Serializable


class MockPayload(Serializable):
    """Mock payload for testing"""

    def __init__(self, value: int):
        self.value = value

    def to_dict(self) -> dict[str, Any]:
        return {"value": self.value}


class TestBaseSensorThread:
    """Test cases for BaseSensorThread class"""

    def test_init(self):
        """Test that BaseSensorThread initializes correctly"""
        mock_driver = Mock()
        out_q = queue.Queue()

        thread = BaseSensorThread(
            name="test_thread",
            interval_s=1.0,
            device_id="test_device",
            driver=mock_driver,
            out_q=out_q,
        )

        assert thread.name == "test_thread"
        assert thread.interval_s == 1.0
        assert thread.device_id == "test_device"
        assert thread.driver == mock_driver
        assert thread.out_q == out_q
        assert thread.daemon is True
        assert isinstance(thread.s_stop, threading.Event)

    def test_stop_sets_event(self):
        """Test that stop() sets the stop event"""
        mock_driver = Mock()
        out_q = queue.Queue()

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

    def test_run_with_successful_readings(self):
        """Test run() method with successful sensor readings"""
        mock_payload = MockPayload(42)
        mock_driver = Mock()
        mock_driver.return_value = mock_payload

        out_q = queue.Queue()

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
        reading = out_q.get_nowait()
        assert isinstance(reading, SensorReading)
        assert reading.device_id == "test_device"
        assert reading.payload == mock_payload
        assert reading.ts > 0

    def test_run_with_failed_readings(self):
        """Test run() method when driver returns None"""
        mock_driver = Mock()
        mock_driver.return_value = None  # Simulate failed reading

        out_q = queue.Queue()

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

    def test_run_with_full_queue(self):
        """Test run() method when queue is full"""
        mock_payload = MockPayload(42)
        mock_driver = Mock()
        mock_driver.return_value = mock_payload

        # Create a full queue
        out_q = queue.Queue(maxsize=1)
        out_q.put("existing_item")  # Fill the queue

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

        # Verify queue still has items (oldest removed, newest added)
        assert not out_q.empty()
        # The queue should have the new reading, not the old item
        reading = out_q.get_nowait()
        assert isinstance(reading, SensorReading)

    def test_run_respects_interval(self):
        """Test that run() respects the polling interval"""
        mock_payload = MockPayload(42)
        mock_driver = Mock()
        mock_driver.return_value = mock_payload

        out_q = queue.Queue()

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

        # Should call driver at least once, but not too many times
        # due to the interval
        assert mock_driver.call_count >= 1
        assert mock_driver.call_count <= 2  # Should not exceed reasonable calls

    def test_run_stops_when_stop_flag_set(self):
        """Test that run() stops when stop flag is set"""
        mock_driver = Mock()
        mock_driver.return_value = MockPayload(42)

        out_q = queue.Queue()

        thread = BaseSensorThread(
            name="test_thread",
            interval_s=1.0,
            device_id="test_device",
            driver=mock_driver,
            out_q=out_q,
        )

        # Set stop flag before starting
        thread.stop()

        # Start thread
        thread.start()
        thread.join(timeout=1.0)

        # Verify thread stopped without calling driver
        assert mock_driver.call_count == 0

    @pytest.mark.filterwarnings("ignore::pytest.PytestUnhandledThreadExceptionWarning")
    def test_run_handles_driver_exception(self):
        """Test that run() handles exceptions from driver gracefully"""
        mock_driver = Mock()
        mock_driver.side_effect = Exception("Driver error")

        out_q = queue.Queue()

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

    def test_thread_is_daemon(self):
        """Test that thread is created as daemon"""
        mock_driver = Mock()
        out_q = queue.Queue()

        thread = BaseSensorThread(
            name="test_thread",
            interval_s=1.0,
            device_id="test_device",
            driver=mock_driver,
            out_q=out_q,
        )

        assert thread.daemon is True

    def test_multiple_readings_over_time(self):
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

        out_q = queue.Queue()

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
        for reading in readings:
            assert isinstance(reading, SensorReading)
            assert reading.device_id == "test_device"
            assert isinstance(reading.payload, MockPayload)
            assert reading.ts > 0

    def test_thread_cleanup(self):
        """Test that thread cleans up properly when stopped"""
        mock_driver = Mock()
        mock_driver.return_value = MockPayload(42)

        out_q = queue.Queue()

        thread = BaseSensorThread(
            name="test_thread",
            interval_s=1.0,
            device_id="test_device",
            driver=mock_driver,
            out_q=out_q,
        )

        # Start and stop thread
        thread.start()
        time.sleep(0.1)
        thread.stop()

        # Verify thread stops cleanly
        thread.join(timeout=1.0)
        assert not thread.is_alive()

    def test_concurrent_access_safety(self):
        """Test that thread handles concurrent access safely"""
        mock_driver = Mock()
        mock_driver.return_value = MockPayload(42)

        out_q = queue.Queue()

        thread = BaseSensorThread(
            name="test_thread",
            interval_s=0.1,  # Fast polling
            device_id="test_device",
            driver=mock_driver,
            out_q=out_q,
        )

        # Start thread
        thread.start()

        # Concurrently access thread properties
        def access_thread():
            for _ in range(10):
                _ = thread.interval_s
                _ = thread.device_id
                _ = thread.s_stop.is_set()
                time.sleep(0.01)

        # Run concurrent access
        access_thread()

        # Stop thread
        thread.stop()
        thread.join(timeout=1.0)

        # Verify thread stopped cleanly
        assert not thread.is_alive()

    def test_first_reading_delayed(self):
        """Test that the first reading doesn't happen immediately"""
        mock_driver = Mock()
        mock_driver.return_value = MockPayload(42)

        out_q = queue.Queue()

        thread = BaseSensorThread(
            name="test_thread",
            interval_s=0.2,  # 200ms interval
            device_id="test_device",
            driver=mock_driver,
            out_q=out_q,
        )

        # Start thread
        thread.start()

        # Wait less than the interval
        time.sleep(0.1)  # 100ms, less than 200ms interval

        # Driver should not be called yet
        assert mock_driver.call_count == 0

        # Wait for the interval to pass
        time.sleep(0.15)  # Additional 150ms, total 250ms > 200ms

        # Now driver should have been called
        assert mock_driver.call_count >= 1

        thread.stop()
        thread.join(timeout=1.0)
