import json
import os
import sqlite3
import tempfile
from typing import Iterator

import pytest

from air_quality_sensor.buffered_publisher import BufferedPublisher, OutboundPort
from air_quality_sensor.sensor_types import Serializable
from air_quality_sensor.sqlite_buffer import SQLLiteBufferWriter


class MockSerializableMessage(Serializable):
    """Test implementation of Serializable for testing."""

    def __init__(self, data: dict):
        self.data = data

    def to_string(self) -> str:
        return json.dumps(self.data)


class MockPusher(OutboundPort):
    """Mock implementation of OutboundPort for testing."""

    def __init__(self, should_succeed: bool = True):
        self.should_succeed = should_succeed
        self.sent_messages: list[Serializable] = []

    def send(self, msg: Serializable) -> bool:
        self.sent_messages.append(msg)
        return self.should_succeed


@pytest.fixture
def temp_db_path() -> Iterator[str]:
    """Create a temporary database file path."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    yield db_path
    # Cleanup
    if os.path.exists(db_path):
        os.unlink(db_path)


@pytest.fixture
def sqlite_conn(temp_db_path: str) -> Iterator[sqlite3.Connection]:
    """Create a SQLite connection to a temporary database."""
    conn = sqlite3.connect(temp_db_path)
    yield conn
    conn.close()


@pytest.fixture
def buffer_writer(sqlite_conn: sqlite3.Connection) -> SQLLiteBufferWriter:
    """Create a buffer writer instance."""
    return SQLLiteBufferWriter(sqlite_conn, max_mb=1, eviction_batch=2)


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


def test_init(buffered_publisher_success: BufferedPublisher) -> None:
    """Test buffered publisher initialization."""
    assert buffered_publisher_success.buffer is not None
    assert buffered_publisher_success.pusher is not None


def test_send_success(buffered_publisher_success: BufferedPublisher) -> None:
    """Test successful message sending."""
    # Set up the buffer
    buffered_publisher_success.buffer.conn.executescript(  # type: ignore[attr-defined]
        buffered_publisher_success.buffer.CREATE_SQL  # type: ignore[attr-defined]
    )

    message = MockSerializableMessage({"test": "data", "value": 42})

    # Send the message
    result = buffered_publisher_success.send(message)

    # Should succeed
    assert result is True

    # Check that message was sent via pusher
    assert len(buffered_publisher_success.pusher.sent_messages) == 1  # type: ignore[attr-defined]
    assert buffered_publisher_success.pusher.sent_messages[0] == message  # type: ignore[attr-defined]

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
    result = buffered_publisher_failure.send(message)

    # Should fail
    assert result is False

    # Check that message was attempted via pusher
    assert len(buffered_publisher_failure.pusher.sent_messages) == 1  # type: ignore[attr-defined]
    assert buffered_publisher_failure.pusher.sent_messages[0] == message  # type: ignore[attr-defined]

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
        result = buffered_publisher_success.send(message)
        assert result is True

    # Check that all messages were sent via pusher
    assert len(buffered_publisher_success.pusher.sent_messages) == 3  # type: ignore[attr-defined]
    assert buffered_publisher_success.pusher.sent_messages == messages  # type: ignore[attr-defined]

    # Check that no messages remain unsent
    unsent = list(buffered_publisher_success.buffer.unsent())
    assert len(unsent) == 0


def test_send_with_mixed_success_failure() -> None:
    """Test sending with a pusher that sometimes fails."""

    # Create a mock pusher that fails on specific messages
    class SelectivePusher(OutboundPort):
        def __init__(self):
            self.sent_messages = []
            self.fail_on = {"fail": True}

        def send(self, msg: Serializable) -> bool:
            self.sent_messages.append(msg)
            return msg.data != self.fail_on  # type: ignore[attr-defined]

    # Set up buffer and publisher
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    try:
        conn = sqlite3.connect(db_path)
        buffer = SQLLiteBufferWriter(conn, max_mb=1, eviction_batch=2)
        pusher = SelectivePusher()
        publisher = BufferedPublisher(buffer, pusher)

        # Set up the buffer
        buffer.conn.executescript(buffer.CREATE_SQL)  # type: ignore[attr-defined]

        # Send messages
        success_msg = MockSerializableMessage({"success": True})
        fail_msg = MockSerializableMessage({"fail": True})

        result1 = publisher.send(success_msg)
        result2 = publisher.send(fail_msg)

        # Check results
        assert result1 is True
        assert result2 is False

        # Check that both were attempted
        assert len(pusher.sent_messages) == 2  # type: ignore[attr-defined]

        # Check buffer state
        unsent = list(buffer.unsent())
        assert len(unsent) == 1  # Only the failed message should remain unsent

    finally:
        conn.close()
        if os.path.exists(db_path):
            os.unlink(db_path)


def test_send_with_exception() -> None:
    """Test sending when buffer operations raise exceptions."""

    # Create a mock buffer that raises exceptions
    class FailingBuffer:
        def append(self, msg):
            raise Exception("Buffer append failed")

        def mark_sent(self, row_id):
            pass

        def unsent(self):
            return []

    mock_pusher = MockPusher(should_succeed=True)
    failing_buffer = FailingBuffer()

    publisher = BufferedPublisher(failing_buffer, mock_pusher)

    message = MockSerializableMessage({"test": "data"})

    # Should handle exception gracefully
    result = publisher.send(message)
    assert result is False

    # Should not have attempted to send via pusher
    assert len(mock_pusher.sent_messages) == 0


def test_protocol_compliance() -> None:
    """Test that BufferedPublisher properly implements OutboundPort protocol."""

    # Create a mock buffer
    class MockBuffer:
        def append(self, msg):
            return 1

        def mark_sent(self, row_id):
            pass

        def unsent(self):
            return []

    mock_pusher = MockPusher()
    mock_buffer = MockBuffer()

    publisher = BufferedPublisher(mock_buffer, mock_pusher)

    # Should be callable with the expected signature
    message = MockSerializableMessage({"test": "data"})
    result = publisher.send(message)
    assert isinstance(result, bool)


def test_message_persistence() -> None:
    """Test that messages are properly persisted in the buffer."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    try:
        conn = sqlite3.connect(db_path)
        buffer = SQLLiteBufferWriter(conn, max_mb=1, eviction_batch=2)
        pusher = MockPusher(should_succeed=False)  # Always fail to test persistence
        publisher = BufferedPublisher(buffer, pusher)

        # Set up the buffer
        buffer.conn.executescript(buffer.CREATE_SQL)  # type: ignore[attr-defined]

        # Send multiple messages
        messages = [
            MockSerializableMessage({"id": 1, "data": "first"}),
            MockSerializableMessage({"id": 2, "data": "second"}),
            MockSerializableMessage({"id": 3, "data": "third"}),
        ]

        for message in messages:
            publisher.send(message)

        # Check that all messages are in buffer as unsent
        unsent = list(buffer.unsent())
        assert len(unsent) == 3

        # Verify the messages are correct
        for i, (row_id, payload) in enumerate(unsent):
            assert payload == messages[i].to_string()

    finally:
        conn.close()
        if os.path.exists(db_path):
            os.unlink(db_path)


def test_mark_sent_functionality() -> None:
    """Test that successful sends properly mark messages as sent."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    try:
        conn = sqlite3.connect(db_path)
        buffer = SQLLiteBufferWriter(conn, max_mb=1, eviction_batch=2)
        pusher = MockPusher(should_succeed=True)  # Always succeed
        publisher = BufferedPublisher(buffer, pusher)

        # Set up the buffer
        buffer.conn.executescript(buffer.CREATE_SQL)  # type: ignore[attr-defined]

        # Send multiple messages
        messages = [
            MockSerializableMessage({"id": 1, "data": "first"}),
            MockSerializableMessage({"id": 2, "data": "second"}),
            MockSerializableMessage({"id": 3, "data": "third"}),
        ]

        for message in messages:
            publisher.send(message)

        # Check that no messages remain unsent
        unsent = list(buffer.unsent())
        assert len(unsent) == 0

    finally:
        conn.close()
        if os.path.exists(db_path):
            os.unlink(db_path)
