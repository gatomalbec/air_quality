import json
import sqlite3
from typing import Iterator

import pytest

from air_quality_sensor.buffered_publisher import BufferedPublisher, OutboundPort
from air_quality_sensor.sensor_types import Serializable
from air_quality_sensor.sqlite_buffer import SQLLiteBufferWriter


class MockSerializableMessage(Serializable):
    """Mock serializable message for testing."""

    def __init__(self, data: dict):
        self.data = data

    def to_string(self) -> str:
        return json.dumps(self.data)


class MockPusher(OutboundPort):
    """Mock outbound port for testing."""

    def __init__(self, should_succeed: bool = True):
        self.should_succeed = should_succeed
        self.sent_messages: list[str] = []

    def publish(self, msg: str) -> bool:
        self.sent_messages.append(msg)
        return self.should_succeed

    def close(self) -> None:
        pass


@pytest.fixture
def sqlite_conn() -> Iterator[sqlite3.Connection]:
    """Create an in-memory SQLite connection for testing."""
    conn = sqlite3.connect(":memory:")
    yield conn
    conn.close()


@pytest.fixture
def buffer_writer(sqlite_conn: sqlite3.Connection) -> SQLLiteBufferWriter:
    """Create a buffer writer for testing."""
    return SQLLiteBufferWriter(sqlite_conn)


@pytest.fixture
def mock_pusher_success() -> MockPusher:
    """Create a mock pusher that always succeeds."""
    return MockPusher(should_succeed=True)


@pytest.fixture
def mock_pusher_failure() -> MockPusher:
    """Create a mock pusher that always fails."""
    return MockPusher(should_succeed=False)


@pytest.fixture
def buffered_publisher_success(
    buffer_writer: SQLLiteBufferWriter, mock_pusher_success: MockPusher
) -> BufferedPublisher:
    """Create a buffered publisher with successful pusher."""
    return BufferedPublisher(buffer_writer, mock_pusher_success)


@pytest.fixture
def buffered_publisher_failure(
    buffer_writer: SQLLiteBufferWriter, mock_pusher_failure: MockPusher
) -> BufferedPublisher:
    """Create a buffered publisher with failing pusher."""
    return BufferedPublisher(buffer_writer, mock_pusher_failure)


def test_send_success(buffered_publisher_success: BufferedPublisher) -> None:
    """Test successful message sending."""
    # Set up the buffer
    buffered_publisher_success.buffer.conn.executescript(  # type: ignore[attr-defined]
        buffered_publisher_success.buffer.CREATE_SQL  # type: ignore[attr-defined]
    )

    message = MockSerializableMessage({"test": "data", "value": 42})

    # Send the message
    result = buffered_publisher_success.publish(message.to_string())

    # Should succeed
    assert result is True

    # Check that message was sent via pusher
    assert len(buffered_publisher_success.publisher.sent_messages) == 1  # type: ignore[attr-defined]
    assert buffered_publisher_success.publisher.sent_messages[0] == message.to_string()  # type: ignore[attr-defined]

    # Check that message was marked as sent in buffer
    unsent = list(buffered_publisher_success.buffer.unsent())
    assert len(unsent) == 0  # Should be no unsent messages


def test_send_failure(buffered_publisher_failure: BufferedPublisher) -> None:
    """Test message sending when pusher fails."""
    # Set up the buffer
    buffered_publisher_failure.buffer.conn.executescript(  # type: ignore[attr-defined]
        buffered_publisher_failure.buffer.CREATE_SQL  # type: ignore[attr-defined]
    )

    message = MockSerializableMessage({"test": "data", "value": 42})

    # Send the message
    result = buffered_publisher_failure.publish(message.to_string())

    # Should fail
    assert result is False

    # Check that message was attempted via pusher
    assert len(buffered_publisher_failure.publisher.sent_messages) == 1  # type: ignore[attr-defined]
    assert buffered_publisher_failure.publisher.sent_messages[0] == message.to_string()  # type: ignore[attr-defined]

    # Check that message remains unsent in buffer
    unsent = list(buffered_publisher_failure.buffer.unsent())
    assert len(unsent) == 1  # Should have one unsent message


def test_send_multiple_messages(buffered_publisher_success: BufferedPublisher) -> None:
    """Test sending multiple messages."""
    # Set up the buffer
    buffered_publisher_success.buffer.conn.executescript(  # type: ignore[attr-defined]
        buffered_publisher_success.buffer.CREATE_SQL  # type: ignore[attr-defined]
    )

    messages = [
        MockSerializableMessage({"id": 1, "data": "first"}),
        MockSerializableMessage({"id": 2, "data": "second"}),
        MockSerializableMessage({"id": 3, "data": "third"}),
    ]

    # Send all messages
    for message in messages:
        result = buffered_publisher_success.publish(message.to_string())
        assert result is True

    # Check that all messages were sent via pusher
    assert len(buffered_publisher_success.publisher.sent_messages) == 3  # type: ignore[attr-defined]
    for i, message in enumerate(messages):
        assert buffered_publisher_success.publisher.sent_messages[i] == message.to_string()  # type: ignore[attr-defined]

    # Check that all messages were marked as sent in buffer
    unsent = list(buffered_publisher_success.buffer.unsent())
    assert len(unsent) == 0  # Should be no unsent messages


def test_send_with_mixed_success_failure() -> None:
    """Test sending messages with mixed success/failure outcomes."""

    # Create a selective pusher that fails for specific messages
    class SelectivePusher(OutboundPort):
        def __init__(self):
            self.sent_messages: list[str] = []
            self.call_count = 0

        def publish(self, msg: str) -> bool:
            self.sent_messages.append(msg)
            self.call_count += 1
            # Fail every other message
            return self.call_count % 2 == 1

        def close(self) -> None:
            pass

    # Set up the test with in-memory database
    conn = sqlite3.connect(":memory:")
    buffer_writer = SQLLiteBufferWriter(conn)
    selective_pusher = SelectivePusher()
    publisher = BufferedPublisher(buffer_writer, selective_pusher)

    # Set up the buffer
    buffer_writer.conn.executescript(buffer_writer.CREATE_SQL)  # type: ignore[attr-defined]

    messages = [
        MockSerializableMessage({"id": 1}),
        MockSerializableMessage({"id": 2}),
        MockSerializableMessage({"id": 3}),
        MockSerializableMessage({"id": 4}),
    ]

    # Send all messages
    results = []
    for message in messages:
        result = publisher.publish(message.to_string())
        results.append(result)

    # Check results: odd-indexed messages should succeed, even-indexed should fail
    assert results == [True, False, True, False]

    # Check that all messages were attempted via pusher
    assert len(selective_pusher.sent_messages) == 4

    # Check that failed messages remain unsent in buffer
    unsent = list(buffer_writer.unsent())
    assert len(unsent) == 2  # Should have two unsent messages (the failed ones)

    conn.close()


def test_send_with_exception() -> None:
    """Test sending when buffer operations raise exceptions."""

    # Create a failing buffer
    class FailingBuffer:
        def append(self, msg):
            raise Exception("Buffer append failed")

        def mark_sent(self, row_id):
            pass

        def unsent(self):
            return iter([])

        def close(self) -> None:
            pass

    # Create a mock pusher
    mock_pusher = MockPusher(should_succeed=True)

    # Create buffered publisher with failing buffer
    publisher = BufferedPublisher(FailingBuffer(), mock_pusher)

    message = MockSerializableMessage({"test": "data"})

    # Send should fail due to buffer exception
    result = publisher.publish(message.to_string())

    # Should fail
    assert result is False

    # Check that message was not sent via pusher (buffer failed first)
    assert len(mock_pusher.sent_messages) == 0
