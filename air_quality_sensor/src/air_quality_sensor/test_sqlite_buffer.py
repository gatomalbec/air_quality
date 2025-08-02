import os
import sqlite3
import tempfile
from typing import Iterator
from unittest.mock import patch

import pytest

from air_quality_sensor.sqlite_buffer import SQLLiteBufferWriter


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


def test_db_file_size_with_file(buffer_writer: SQLLiteBufferWriter) -> None:
    """Test getting database file size when file exists."""
    # Create a small file to test size calculation
    size = buffer_writer.db_file_size()
    assert size >= 0


def test_db_file_size_memory_db() -> None:
    """Test getting database file size for in-memory database."""
    conn = sqlite3.connect(":memory:")
    writer = SQLLiteBufferWriter(conn)
    size = writer.db_file_size()
    assert size == 0
    conn.close()


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


def test_mark_sent_nonexistent_id(buffer_writer: SQLLiteBufferWriter) -> None:
    """Test marking a non-existent row as sent."""
    buffer_writer.conn.executescript(buffer_writer.CREATE_SQL)

    # Mark non-existent ID as sent (should not raise error)
    buffer_writer.mark_sent(999)

    # Verify no rows were affected
    cursor = buffer_writer.conn.execute("SELECT COUNT(*) FROM readings WHERE sent = 1")
    count = cursor.fetchone()[0]
    assert count == 0


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

    # Should have 2 unsent entries (ids 2 and 3)
    assert len(unsent) == 2
    assert unsent[0][0] == 2  # id
    assert unsent[1][0] == 3  # id


def test_unsent_empty_buffer(buffer_writer: SQLLiteBufferWriter) -> None:
    """Test retrieving unsent entries from empty buffer."""
    buffer_writer.conn.executescript(buffer_writer.CREATE_SQL)

    unsent = list(buffer_writer.unsent())
    assert len(unsent) == 0


def test_get_stats_empty_buffer(buffer_writer: SQLLiteBufferWriter) -> None:
    """Test getting stats from empty buffer."""
    buffer_writer.conn.executescript(buffer_writer.CREATE_SQL)

    stats = buffer_writer.get_stats()
    assert stats["total_entries"] == 0
    assert stats["sent_entries"] == 0
    assert stats["unsent_entries"] == 0
    assert stats["max_mb"] == 1
    assert stats["eviction_batch"] == 2
    assert "file_size_bytes" in stats


def test_get_stats_with_data(buffer_writer: SQLLiteBufferWriter) -> None:
    """Test getting stats with data in buffer."""
    buffer_writer.conn.executescript(buffer_writer.CREATE_SQL)

    # Add some data
    buffer_writer.append('{"test": "data1"}')
    buffer_writer.append('{"test": "data2"}')
    buffer_writer.append('{"test": "data3"}')

    # Mark one as sent
    buffer_writer.mark_sent(1)

    stats = buffer_writer.get_stats()
    assert stats["total_entries"] == 3
    assert stats["sent_entries"] == 1
    assert stats["unsent_entries"] == 2


def test_evict_until_size_below_limit_with_size_limit(sqlite_conn: sqlite3.Connection) -> None:
    """Test the _evict_until_size_below_limit method with size limit."""
    writer = SQLLiteBufferWriter(sqlite_conn, max_mb=1, eviction_batch=2)
    writer.conn.executescript(writer.CREATE_SQL)

    # Mock db_file_size to simulate large file
    with patch.object(writer, "db_file_size", return_value=2 * 1024 * 1024):  # 2MB
        # Add some data first
        for i in range(5):
            writer.append(f'{{"test": "data{i}"}}')

        # Call the method directly
        writer._evict_until_size_below_limit()

        # Should have evicted some entries
        cursor = writer.conn.execute("SELECT COUNT(*) FROM readings")
        count = cursor.fetchone()[0]
        assert count < 5  # Some entries should have been evicted


def test_evict_until_size_below_limit_no_size_limit(sqlite_conn: sqlite3.Connection) -> None:
    """Test the _evict_until_size_below_limit method with no size limit."""
    writer = SQLLiteBufferWriter(sqlite_conn, max_mb=None, eviction_batch=2)
    writer.conn.executescript(writer.CREATE_SQL)

    # Add some data
    for i in range(3):
        writer.append(f'{{"test": "data{i}"}}')

    # Call the method - should do nothing since max_mb is None
    writer._evict_until_size_below_limit()

    # Should still have all entries
    cursor = writer.conn.execute("SELECT COUNT(*) FROM readings")
    count = cursor.fetchone()[0]
    assert count == 3


def test_evict_until_size_below_limit_empty_buffer(sqlite_conn: sqlite3.Connection) -> None:
    """Test the _evict_until_size_below_limit method with empty buffer."""
    writer = SQLLiteBufferWriter(sqlite_conn, max_mb=1, eviction_batch=2)
    writer.conn.executescript(writer.CREATE_SQL)

    # Mock db_file_size to simulate large file
    with patch.object(writer, "db_file_size", return_value=2 * 1024 * 1024):  # 2MB
        # Call the method on empty buffer
        writer._evict_until_size_below_limit()

        # Should not raise any errors
        cursor = writer.conn.execute("SELECT COUNT(*) FROM readings")
        count = cursor.fetchone()[0]
        assert count == 0


def test_append_with_size_limit(sqlite_conn: sqlite3.Connection) -> None:
    """Test appending data when size limit is reached."""
    # Create a buffer with very small size limit
    writer = SQLLiteBufferWriter(sqlite_conn, max_mb=1)  # 1MB limit
    writer.conn.executescript(writer.CREATE_SQL)

    # Mock the db_file_size to simulate a large file
    with patch.object(writer, "db_file_size", return_value=2 * 1024 * 1024):  # 2MB
        with patch.object(writer, "_evict_until_size_below_limit") as mock_evict:
            writer.append('{"test": "data"}')
            mock_evict.assert_called_once()


def test_append_without_size_limit(sqlite_conn: sqlite3.Connection) -> None:
    """Test appending data when no size limit is set."""
    writer = SQLLiteBufferWriter(sqlite_conn, max_mb=None)
    writer.conn.executescript(writer.CREATE_SQL)

    # Should not call _evict_until_size_below_limit when max_mb is None
    with patch.object(writer, "_evict_until_size_below_limit") as mock_evict:
        writer.append('{"test": "data"}')
        mock_evict.assert_not_called()


def test_sql_statements_are_valid(buffer_writer: SQLLiteBufferWriter) -> None:
    """Test that all SQL statements are syntactically valid."""
    # Test CREATE_SQL
    buffer_writer.conn.executescript(buffer_writer.CREATE_SQL)

    # Test INSERT_SQL
    buffer_writer.conn.execute(buffer_writer.INSERT_SQL, ('{"test": "data"}',))

    # Test UNSENT_SQL
    cursor = buffer_writer.conn.execute(buffer_writer.UNSENT_SQL)
    assert cursor is not None

    # Test MARK_SENT_SQL
    buffer_writer.conn.execute(buffer_writer.MARK_SENT_SQL, (1,))

    # Test EVICT_SQL
    buffer_writer.conn.execute(buffer_writer.EVICT_SQL, (1,))


def test_connection_integration(sqlite_conn: sqlite3.Connection) -> None:
    """Test full integration with SQLite connection."""
    writer = SQLLiteBufferWriter(sqlite_conn, max_mb=1, eviction_batch=2)

    # Set up the database
    writer.conn.executescript(writer.CREATE_SQL)

    # Add some data
    row_id1 = writer.append('{"sensor": "pm25", "value": 15.5}')
    row_id2 = writer.append('{"sensor": "pm10", "value": 25.2}')

    # Mark first as sent
    writer.mark_sent(row_id1)

    # Get unsent entries
    unsent = list(writer.unsent())
    assert len(unsent) == 1
    assert unsent[0][0] == row_id2

    # Verify the data integrity
    cursor = writer.conn.execute("SELECT payload_json FROM readings WHERE id = ?", (row_id2,))
    result = cursor.fetchone()
    assert result[0] == '{"sensor": "pm10", "value": 25.2}'


def test_multiple_eviction_rounds(sqlite_conn: sqlite3.Connection) -> None:
    """Test that multiple eviction rounds work correctly."""
    writer = SQLLiteBufferWriter(sqlite_conn, max_mb=1, eviction_batch=2)
    writer.conn.executescript(writer.CREATE_SQL)

    # Add many entries
    for i in range(10):
        writer.append(f'{{"test": "data{i}"}}')

    # Mock db_file_size to simulate large file that requires multiple eviction rounds
    with patch.object(writer, "db_file_size", return_value=2 * 1024 * 1024):  # 2MB
        # Call the eviction method
        writer._evict_until_size_below_limit()

        # Should have evicted some entries
        cursor = writer.conn.execute("SELECT COUNT(*) FROM readings")
        count = cursor.fetchone()[0]
        assert count < 10  # Some entries should have been evicted



