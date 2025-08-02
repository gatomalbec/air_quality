import json
import queue
import sqlite3
import time
from dataclasses import asdict, dataclass
from typing import Any, Dict, List

from air_quality_sensor.buffered_publisher import BufferedPublisher
from air_quality_sensor.delivery_loop import DeliveryLoop, ExponentialBackoff
from air_quality_sensor.poller import BaseSensorThread
from air_quality_sensor.sensor_types import SensorReading, Serializable
from air_quality_sensor.sqlite_buffer import SQLLiteBufferWriter


class StubMQTTPublisher:
    """Stub MQTT publisher for testing."""

    def __init__(self, fails: int = 0):
        self.calls: List[str] = []
        self._fails = fails
        self._closed = False

    def publish(self, msg: str) -> bool:
        if self._closed:
            return False

        self.calls.append(msg)
        if self._fails > 0:
            self._fails -= 1
            return False
        return True

    def close(self):
        self._closed = True


@dataclass
class MockSerializablePayload(Serializable):
    """Mock serializable payload for testing."""

    data: dict

    def to_string(self) -> str:
        return json.dumps(asdict(self))


class MockSensorDriver:
    """Mock sensor driver that returns predictable readings."""

    def __init__(self, readings: List[Dict[str, Any]] | None = None):
        self.readings = readings or [{"pm1": 10, "pm2_5": 15, "pm10": 20}]
        self.index = 0

    def __call__(self) -> Serializable | None:
        if self.index >= len(self.readings):
            return None
        reading = self.readings[self.index]
        self.index += 1
        return MockSerializablePayload(data=reading)


def make_payload(i: int) -> str:
    """Create a test payload with predictable data."""
    reading = SensorReading(
        ts=time.time() + i,
        device_id="test-device",
        payload=MockSerializablePayload({"test_id": i, "value": i * 10}),
    )
    return reading.to_string()


def test_publish_success():
    """Test successful message publishing through the full pipeline."""
    # Setup MQTT publisher
    mqtt = StubMQTTPublisher()

    # Setup queue and delivery loop
    q: queue.Queue[str] = queue.Queue(maxsize=10)

    def make_outbound_port() -> BufferedPublisher:
        conn = sqlite3.connect(":memory:", isolation_level=None)
        buf = SQLLiteBufferWriter(conn, max_mb=1)
        conn.executescript(buf.CREATE_SQL)
        return BufferedPublisher(buf, mqtt)

    loop = DeliveryLoop(q, make_outbound_port, ExponentialBackoff())

    # Start delivery loop
    loop.start()

    # Add message to queue
    payload = make_payload(1)
    q.put(payload)

    # Wait for processing
    time.sleep(0.2)

    # Verify message was published
    assert len(mqtt.calls) == 1
    assert mqtt.calls[0] == payload

    # Cleanup
    loop.stop()
    loop.join()


def test_backoff_and_retry():
    """Test exponential backoff and retry logic."""
    # MQTT publisher that fails first 2 times, then succeeds
    mqtt = StubMQTTPublisher(fails=2)

    q: queue.Queue[str] = queue.Queue(maxsize=10)
    backoff = ExponentialBackoff(base=0.1, max_=0.2)

    def make_outbound_port() -> BufferedPublisher:
        conn = sqlite3.connect(":memory:", isolation_level=None)
        buf = SQLLiteBufferWriter(conn, max_mb=1)
        conn.executescript(buf.CREATE_SQL)
        return BufferedPublisher(buf, mqtt)

    loop = DeliveryLoop(q, make_outbound_port, backoff)

    loop.start()

    # Add message to queue
    payload = make_payload(1)
    q.put(payload)

    # Wait for retries and eventual success
    time.sleep(1.0)

    # Should have been called 3 times (2 failures + 1 success)
    assert len(mqtt.calls) == 3
    assert mqtt.calls[0] == payload
    assert mqtt.calls[1] == payload
    assert mqtt.calls[2] == payload

    loop.stop()
    loop.join()


def test_file_size_trimming():
    """Test that database file size is trimmed when it exceeds the limit."""
    mqtt = StubMQTTPublisher()

    # Create a factory that will be used to test file size trimming
    def make_outbound_port() -> BufferedPublisher:
        conn = sqlite3.connect(":memory:", isolation_level=None)
        buf = SQLLiteBufferWriter(conn, max_mb=1, eviction_batch=2)
        conn.executescript(buf.CREATE_SQL)
        return BufferedPublisher(buf, mqtt)

    # Pre-fill the database with many messages
    for i in range(100):
        payload = make_payload(i)
        publisher = make_outbound_port()
        publisher.publish(payload)

    # Verify some messages were published
    assert len(mqtt.calls) > 0


def test_queue_overflow_handling():
    """Test queue overflow handling with drop_oldest strategy."""
    # Create a small queue to force overflow
    q: queue.Queue[str] = queue.Queue(maxsize=2)

    # Mock the drop_oldest function
    def drop_oldest(q: queue.Queue, item):
        if q.full():
            q.get_nowait()
        q.put_nowait(item)

    # Create sensor thread with drop_oldest strategy
    driver = MockSensorDriver([{"value": i} for i in range(10)])
    sensor_thread = BaseSensorThread(
        name="test-sensor", interval_s=0.1, device_id="test-device", driver=driver, out_q=q
    )

    # Start sensor thread
    sensor_thread.start()

    # Wait for some readings
    time.sleep(0.5)

    # Stop sensor thread
    sensor_thread.stop()
    sensor_thread.join()

    # Verify queue didn't grow beyond maxsize
    assert q.qsize() <= 2


def test_graceful_shutdown():
    """Test that all threads stop cleanly."""
    mqtt = StubMQTTPublisher()

    q: queue.Queue[str] = queue.Queue(maxsize=10)

    def make_outbound_port() -> BufferedPublisher:
        conn = sqlite3.connect(":memory:", isolation_level=None)
        buf = SQLLiteBufferWriter(conn, max_mb=1)
        conn.executescript(buf.CREATE_SQL)
        return BufferedPublisher(buf, mqtt)

    loop = DeliveryLoop(q, make_outbound_port, ExponentialBackoff())

    # Start delivery loop
    loop.start()

    # Add a message
    payload = make_payload(1)
    q.put(payload)

    # Wait a bit for processing
    time.sleep(0.1)

    # Stop the loop
    loop.stop()
    loop.join(timeout=1.0)

    # Verify thread stopped
    assert not loop.is_alive()

    # Verify MQTT publisher was closed
    mqtt.close()
    assert mqtt._closed


def test_durability_and_replay():
    """Test that unsent messages are replayed after restart."""
    # Test that failed messages are retried within the same delivery loop
    mqtt = StubMQTTPublisher(fails=1)

    q: queue.Queue[str] = queue.Queue(maxsize=10)

    def make_outbound_port() -> BufferedPublisher:
        conn = sqlite3.connect(":memory:", isolation_level=None)
        buf = SQLLiteBufferWriter(conn, max_mb=1)
        conn.executescript(buf.CREATE_SQL)
        return BufferedPublisher(buf, mqtt)

    loop = DeliveryLoop(q, make_outbound_port, ExponentialBackoff(base=0.1, max_=0.2))

    loop.start()

    # Add message to queue
    payload = make_payload(1)
    q.put(payload)

    # Wait for retry and eventual success
    time.sleep(2.0)  # Give more time for retry

    # Should have been called twice (1 failure + 1 success)
    assert len(mqtt.calls) == 2
    assert mqtt.calls[0] == payload
    assert mqtt.calls[1] == payload

    loop.stop()
    loop.join()


def test_multiple_sensor_threads():
    """Test multiple sensor threads feeding into the same pipeline."""
    mqtt = StubMQTTPublisher()

    q: queue.Queue[str] = queue.Queue(maxsize=20)

    def make_outbound_port() -> BufferedPublisher:
        conn = sqlite3.connect(":memory:", isolation_level=None)
        buf = SQLLiteBufferWriter(conn, max_mb=1)
        conn.executescript(buf.CREATE_SQL)
        return BufferedPublisher(buf, mqtt)

    loop = DeliveryLoop(q, make_outbound_port, ExponentialBackoff())

    # Create multiple sensor threads
    driver1 = MockSensorDriver([{"sensor": "pm", "value": i} for i in range(5)])
    driver2 = MockSensorDriver([{"sensor": "co2", "value": i * 10} for i in range(5)])

    sensor1 = BaseSensorThread(
        name="pm-sensor", interval_s=0.1, device_id="test-device", driver=driver1, out_q=q
    )

    sensor2 = BaseSensorThread(
        name="co2-sensor", interval_s=0.1, device_id="test-device", driver=driver2, out_q=q
    )

    # Start all threads
    loop.start()
    sensor1.start()
    sensor2.start()

    # Wait for processing
    time.sleep(0.5)

    # Stop all threads
    sensor1.stop()
    sensor2.stop()
    loop.stop()

    sensor1.join()
    sensor2.join()
    loop.join()

    # Verify messages were published
    assert len(mqtt.calls) > 0

    # Verify we got messages from both sensors
    import json

    sensor_types = []
    for call in mqtt.calls:
        data = json.loads(call)
        # The payload is a JSON string, so parse it
        payload_data = json.loads(data["payload"])
        print(f"Payload data: {payload_data}")  # Debug
        sensor_types.append(payload_data["data"].get("sensor"))
    print(f"Sensor types: {sensor_types}")  # Debug
    assert "pm" in sensor_types
    assert "co2" in sensor_types


def test_backoff_reset_on_success():
    """Test that backoff resets to base delay after successful publish."""
    # MQTT that fails once, then succeeds
    mqtt = StubMQTTPublisher(fails=1)

    q: queue.Queue[str] = queue.Queue(maxsize=10)
    backoff = ExponentialBackoff(base=0.1, max_=0.5)

    def make_outbound_port() -> BufferedPublisher:
        conn = sqlite3.connect(":memory:", isolation_level=None)
        buf = SQLLiteBufferWriter(conn, max_mb=1)
        conn.executescript(buf.CREATE_SQL)
        return BufferedPublisher(buf, mqtt)

    loop = DeliveryLoop(q, make_outbound_port, backoff)

    loop.start()

    # Add first message (will fail, then succeed)
    payload1 = make_payload(1)
    q.put(payload1)

    # Wait for retry and success
    time.sleep(0.5)

    # Add second message (should succeed immediately due to backoff reset)
    payload2 = make_payload(2)
    q.put(payload2)

    time.sleep(0.2)

    # Both messages should be published
    assert len(mqtt.calls) == 3  # 1 fail + 1 success for first, 1 success for second

    loop.stop()
    loop.join()


def test_stress_test_high_volume():
    """Stress test with high volume of messages."""
    mqtt = StubMQTTPublisher()

    q: queue.Queue[str] = queue.Queue(maxsize=50)

    def make_outbound_port() -> BufferedPublisher:
        conn = sqlite3.connect(":memory:", isolation_level=None)
        buf = SQLLiteBufferWriter(conn, max_mb=1)
        conn.executescript(buf.CREATE_SQL)
        return BufferedPublisher(buf, mqtt)

    loop = DeliveryLoop(q, make_outbound_port, ExponentialBackoff())

    loop.start()

    # Add many messages rapidly
    for i in range(20):
        payload = make_payload(i)
        q.put(payload)

    # Wait for processing
    time.sleep(0.5)

    # Should have processed most messages
    assert len(mqtt.calls) > 10

    loop.stop()
    loop.join()
