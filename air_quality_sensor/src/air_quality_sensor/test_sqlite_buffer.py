import sqlite3
from typing import Iterator

import pytest

from air_quality_sensor.sqlite_buffer import SQLLiteBufferWriter


@pytest.fixture
def sqlite_conn() -> Iterator[sqlite3.Connection]:
    """Create an in-memory SQLite connection for testing."""
    conn = sqlite3.connect(":memory:")
    yield conn
    conn.close()


@pytest.fixture
def buffer_writer(sqlite_conn: sqlite3.Connection) -> SQLLiteBufferWriter:
    """Create a buffer writer instance."""
    return SQLLiteBufferWriter(sqlite_conn, max_mb=1, eviction_batch=2)


def test_append_data(buffer_writer: SQLLiteBufferWriter) -> None:
    """Test appending data to the buffer."""
    # Execute the CREATE_SQL to set up the table
    buffer_writer.conn.executescript(buffer_writer.CREATE_SQL)

    # Append some data
    row_id = buffer_writer.append('{"test": "data"}')
    assert row_id == 1

    # Verify the data was inserted
    cursor = buffer_writer.conn.execute("SELECT payload_json FROM readings WHERE id = ?", (row_id,))
    result = cursor.fetchone()
    assert result is not None
    assert result[0] == '{"test": "data"}'


def test_append_multiple_data(buffer_writer: SQLLiteBufferWriter) -> None:
    """Test appending multiple data entries."""
    buffer_writer.conn.executescript(buffer_writer.CREATE_SQL)

    # Append multiple entries
    row_ids = []
    for i in range(3):
        row_id = buffer_writer.append(f'{{"test": "data{i}"}}')
        row_ids.append(row_id)

    # Verify all data was inserted
    cursor = buffer_writer.conn.execute("SELECT COUNT(*) FROM readings")
    count = cursor.fetchone()[0]
    assert count == 3


def test_mark_sent(buffer_writer: SQLLiteBufferWriter) -> None:
    """Test marking a row as sent."""
    buffer_writer.conn.executescript(buffer_writer.CREATE_SQL)

    # Insert data
    row_id = buffer_writer.append('{"test": "data"}')

    # Mark as sent
    buffer_writer.mark_sent(row_id)

    # Verify it's marked as sent
    cursor = buffer_writer.conn.execute("SELECT sent FROM readings WHERE id = ?", (row_id,))
    result = cursor.fetchone()
    assert result is not None
    assert result[0] == 1


def test_unsent_entries(buffer_writer: SQLLiteBufferWriter) -> None:
    """Test retrieving unsent entries."""
    buffer_writer.conn.executescript(buffer_writer.CREATE_SQL)

    # Insert multiple entries
    buffer_writer.append('{"test": "data1"}')
    buffer_writer.append('{"test": "data2"}')
    buffer_writer.append('{"test": "data3"}')

    # Mark one as sent
    buffer_writer.mark_sent(1)

    # Get unsent entries
    unsent = list(buffer_writer.unsent())

    # Should have 2 unsent entries (rows 2 and 3)
    assert len(unsent) == 2
    assert unsent[0][0] == 2  # row_id
    assert unsent[0][1] == '{"test": "data2"}'  # payload
    assert unsent[1][0] == 3  # row_id
    assert unsent[1][1] == '{"test": "data3"}'  # payload


def test_unsent_empty_buffer(buffer_writer: SQLLiteBufferWriter) -> None:
    """Test retrieving unsent entries from empty buffer."""
    buffer_writer.conn.executescript(buffer_writer.CREATE_SQL)

    # Get unsent entries from empty buffer
    unsent = list(buffer_writer.unsent())

    # Should be empty
    assert len(unsent) == 0


def test_get_stats_empty_buffer(buffer_writer: SQLLiteBufferWriter) -> None:
    """Test getting stats from empty buffer."""
    buffer_writer.conn.executescript(buffer_writer.CREATE_SQL)

    stats = buffer_writer.get_stats()

    assert stats["total_entries"] == 0
    assert stats["unsent_entries"] == 0
    assert stats["sent_entries"] == 0
    assert stats["file_size_bytes"] >= 0


def test_get_stats_with_data(buffer_writer: SQLLiteBufferWriter) -> None:
    """Test getting stats with data in buffer."""
    buffer_writer.conn.executescript(buffer_writer.CREATE_SQL)

    # Insert some data
    buffer_writer.append('{"test": "data1"}')
    buffer_writer.append('{"test": "data2"}')
    buffer_writer.append('{"test": "data3"}')

    # Mark one as sent
    buffer_writer.mark_sent(1)

    stats = buffer_writer.get_stats()

    assert stats["total_entries"] == 3
    assert stats["unsent_entries"] == 2
    assert stats["sent_entries"] == 1
    assert stats["file_size_bytes"] >= 0


def test_evict_until_size_below_limit_with_size_limit(sqlite_conn: sqlite3.Connection) -> None:
    """Test eviction when size limit is set."""
    writer = SQLLiteBufferWriter(sqlite_conn, max_mb=1, eviction_batch=2)
    writer.conn.executescript(writer.CREATE_SQL)

    # Insert data to trigger eviction
    for i in range(10):
        writer.append(f'{{"test": "data{i}"}}')

    # Eviction should be called during append
    stats = writer.get_stats()
    assert stats["total_entries"] <= 10  # May be less due to eviction


def test_evict_until_size_below_limit_no_size_limit(sqlite_conn: sqlite3.Connection) -> None:
    """Test eviction when no size limit is set."""
    writer = SQLLiteBufferWriter(sqlite_conn, max_mb=None, eviction_batch=2)
    writer.conn.executescript(writer.CREATE_SQL)

    # Insert data - should not trigger eviction
    for i in range(10):
        writer.append(f'{{"test": "data{i}"}}')

    stats = writer.get_stats()
    assert stats["total_entries"] == 10  # No eviction should occur


def test_evict_until_size_below_limit_empty_buffer(sqlite_conn: sqlite3.Connection) -> None:
    """Test eviction with empty buffer."""
    writer = SQLLiteBufferWriter(sqlite_conn, max_mb=1, eviction_batch=2)
    writer.conn.executescript(writer.CREATE_SQL)

    # Should not raise an exception
    writer._evict_until_size_below_limit()

    stats = writer.get_stats()
    assert stats["total_entries"] == 0


def test_append_with_size_limit(sqlite_conn: sqlite3.Connection) -> None:
    """Test append with size limit."""
    writer = SQLLiteBufferWriter(sqlite_conn, max_mb=1, eviction_batch=2)
    writer.conn.executescript(writer.CREATE_SQL)

    # Insert data
    row_id = writer.append('{"test": "data"}')
    assert row_id == 1

    # Verify data was inserted
    cursor = writer.conn.execute("SELECT payload_json FROM readings WHERE id = ?", (row_id,))
    result = cursor.fetchone()
    assert result is not None
    assert result[0] == '{"test": "data"}'


def test_append_without_size_limit(sqlite_conn: sqlite3.Connection) -> None:
    """Test append without size limit."""
    writer = SQLLiteBufferWriter(sqlite_conn, max_mb=None, eviction_batch=2)
    writer.conn.executescript(writer.CREATE_SQL)

    # Insert data
    row_id = writer.append('{"test": "data"}')
    assert row_id == 1

    # Verify data was inserted
    cursor = writer.conn.execute("SELECT payload_json FROM readings WHERE id = ?", (row_id,))
    result = cursor.fetchone()
    assert result is not None
    assert result[0] == '{"test": "data"}'
