import json
import queue
import time
from typing import Iterator, Tuple

import pytest

from air_quality_sensor.buffered_publisher import BufferedPublisher
from air_quality_sensor.delivery_loop import BackoffPolicy, DeliveryLoop, ExponentialBackoff
from air_quality_sensor.sensor_types import Serializable


class MockSerializableMessage(Serializable):
    def __init__(self, data: dict):
        self.data = data

    def to_string(self) -> str:
        return json.dumps(self.data)


class MockBufferedPublisher(BufferedPublisher):
    def __init__(self, should_succeed: bool = True):
        self.should_succeed = should_succeed
        self.sent_messages: list[str] = []
        # Create a minimal mock buffer and pusher for the parent class
        from air_quality_sensor.sqlite_buffer import BufferWriter

        class MockBuffer(BufferWriter):
            def append(self, msg: str) -> int:
                return 1

            def mark_sent(self, row_id: int) -> None:
                pass

            def unsent(self) -> Iterator[Tuple[int, str]]:
                return iter([])

            def close(self) -> None:
                pass

        class MockPusher:
            def publish(self, msg: str) -> bool:
                return should_succeed

            def close(self) -> None:
                pass

        super().__init__(MockBuffer(), MockPusher())

    def publish(self, msg: str) -> bool:
        self.sent_messages.append(msg)
        return self.should_succeed


class MockBackoffPolicy(BackoffPolicy):
    def __init__(self, delays: list[float]):
        self.delays = delays
        self.call_count = 0

    def next_delay(self, *, success: bool) -> float:
        if self.call_count < len(self.delays):
            delay = self.delays[self.call_count]
            self.call_count += 1
            return delay
        return 0.0


@pytest.fixture
def mock_message() -> MockSerializableMessage:
    return MockSerializableMessage({"test": "data"})


@pytest.fixture
def mock_publisher_success() -> MockBufferedPublisher:
    return MockBufferedPublisher(should_succeed=True)


@pytest.fixture
def mock_publisher_failure() -> MockBufferedPublisher:
    return MockBufferedPublisher(should_succeed=False)


@pytest.fixture
def mock_backoff() -> MockBackoffPolicy:
    return MockBackoffPolicy([0.1, 0.2, 0.3])


@pytest.fixture
def message_queue() -> queue.Queue[str]:
    return queue.Queue()


# ExponentialBackoff tests


def test_next_delay_success():
    backoff = ExponentialBackoff(base=2.0)
    backoff._current_delay = 8.0
    delay = backoff.next_delay(success=True)
    assert delay == 0.0
    assert backoff._current_delay == 2.0


def test_next_delay_failure():
    backoff = ExponentialBackoff(base=1.0, max_=10.0, jitter=0.0)
    delay1 = backoff.next_delay(success=False)
    assert delay1 == 2.0
    assert backoff._current_delay == 2.0
    delay2 = backoff.next_delay(success=False)
    assert delay2 == 4.0
    assert backoff._current_delay == 4.0
    delay3 = backoff.next_delay(success=False)
    assert delay3 == 8.0
    assert backoff._current_delay == 8.0
    delay4 = backoff.next_delay(success=False)
    assert delay4 == 10.0
    assert backoff._current_delay == 10.0


# DeliveryLoop tests


def test_stop(message_queue, mock_publisher_success, mock_backoff):
    def make_publisher():
        return mock_publisher_success

    loop = DeliveryLoop(message_queue, make_publisher, mock_backoff)
    assert not loop._stop_event.is_set()
    loop.stop()
    assert loop._stop_event.is_set()


def test_run_processes_backlog_first(message_queue, mock_publisher_success, mock_backoff):
    queue_message = MockSerializableMessage({"queue": "item"})
    message_queue.put(queue_message.to_string())

    def make_publisher():
        return mock_publisher_success

    loop = DeliveryLoop(message_queue, make_publisher, mock_backoff)
    loop.start()
    time.sleep(0.1)
    loop.stop()
    loop.join()
    assert len(mock_publisher_success.sent_messages) == 1
    assert mock_publisher_success.sent_messages[0] == queue_message.to_string()


def test_run_handles_queue_empty(message_queue, mock_publisher_success, mock_backoff):
    def make_publisher():
        return mock_publisher_success

    loop = DeliveryLoop(message_queue, make_publisher, mock_backoff)
    loop.start()
    time.sleep(0.1)
    loop.stop()
    loop.join()
    assert len(mock_publisher_success.sent_messages) == 0


def test_run_handles_publish_failure(message_queue, mock_publisher_failure, mock_backoff):
    message = MockSerializableMessage({"test": "data"})
    message_queue.put(message.to_string())

    def make_publisher():
        return mock_publisher_failure

    loop = DeliveryLoop(message_queue, make_publisher, mock_backoff)
    loop.start()
    time.sleep(0.1)
    loop.stop()
    loop.join()
    assert len(mock_publisher_failure.sent_messages) >= 1


def test_run_with_successful_publish(message_queue, mock_publisher_success, mock_backoff):
    message = MockSerializableMessage({"test": "data"})
    message_queue.put(message.to_string())

    def make_publisher():
        return mock_publisher_success

    loop = DeliveryLoop(message_queue, make_publisher, mock_backoff)
    loop.start()
    time.sleep(0.1)
    loop.stop()
    loop.join()
    assert len(mock_publisher_success.sent_messages) == 1
    assert mock_publisher_success.sent_messages[0] == message.to_string()


def test_run_with_backoff_delay(message_queue, mock_publisher_failure):
    backoff = MockBackoffPolicy([0.1])
    message = MockSerializableMessage({"test": "data"})
    message_queue.put(message.to_string())

    def make_publisher():
        return mock_publisher_failure

    loop = DeliveryLoop(message_queue, make_publisher, backoff)
    start_time = time.time()
    loop.start()
    time.sleep(0.2)
    loop.stop()
    loop.join()
    end_time = time.time()
    assert end_time - start_time >= 0.1


def test_run_stops_when_signaled(message_queue, mock_publisher_success, mock_backoff):
    def make_publisher():
        return mock_publisher_success

    loop = DeliveryLoop(message_queue, make_publisher, mock_backoff)
    loop.start()
    time.sleep(0.01)
    loop.stop()
    loop.join(timeout=1.0)
    assert not loop.is_alive()


def test_run_with_multiple_messages(message_queue, mock_publisher_success, mock_backoff):
    messages = [
        MockSerializableMessage({"id": 1}),
        MockSerializableMessage({"id": 2}),
        MockSerializableMessage({"id": 3}),
    ]
    for msg in messages:
        message_queue.put(msg.to_string())

    def make_publisher():
        return mock_publisher_success

    loop = DeliveryLoop(message_queue, make_publisher, mock_backoff)
    loop.start()
    time.sleep(0.2)
    loop.stop()
    loop.join()
    assert len(mock_publisher_success.sent_messages) == 3
    for i, msg in enumerate(messages):
        assert mock_publisher_success.sent_messages[i] == msg.to_string()


def test_run_with_mixed_success_failure(message_queue):
    publisher = MockBufferedPublisher(should_succeed=False)
    no_delay_backoff = MockBackoffPolicy([0.0, 0.0])
    message = MockSerializableMessage({"id": 1})
    message_queue.put(message.to_string())

    def make_publisher():
        return publisher

    loop = DeliveryLoop(message_queue, make_publisher, no_delay_backoff)
    loop.start()
    time.sleep(0.1)
    loop.stop()
    loop.join()
    assert len(publisher.sent_messages) >= 1
