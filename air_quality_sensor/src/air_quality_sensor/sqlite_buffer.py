import logging
import os
from typing import Iterable, Protocol, Tuple

logger = logging.getLogger(__name__)


class BufferWriter(Protocol):
    """Protocol for buffer writers."""

    def append(self, data: str) -> int: ...
    def mark_sent(self, row_id: int) -> None: ...
    def unsent(self) -> Iterable[Tuple[int, str]]: ...


class SQLLiteBufferWriter(BufferWriter):
    CREATE_SQL = """
    CREATE TABLE IF NOT EXISTS readings (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        payload_json  TEXT    NOT NULL,
        sent          INTEGER NOT NULL DEFAULT 0
    );
    CREATE INDEX IF NOT EXISTS idx_sent ON readings(sent);
    """

    INSERT_SQL = """
    INSERT INTO readings (payload_json) VALUES (?);
    """

    UNSENT_SQL = """
    SELECT id, payload_json FROM readings WHERE sent = 0;
    """

    MARK_SENT_SQL = """
    UPDATE readings SET sent = 1 WHERE id = ?;
    """

    EVICT_SQL = """
    DELETE FROM readings WHERE id IN (SELECT id FROM readings ORDER BY id LIMIT ?);
    """

    def __init__(
        self,
        conn,
        *,
        max_mb: int | None = None,
        eviction_batch: int = 500,
    ):
        self.conn = conn
        self.max_mb = max_mb
        self.eviction_batch = eviction_batch
        # usable_MB = 32  - (WAL + schema ≈ 0.5 MB) ≈ 31.5 MB
        # hours backup     = usable_MB / 0.06 MB·h⁻¹

        logger.info(
            "Initialized SQLLiteBufferWriter with max_mb=%s, eviction_batch=%s",
            max_mb,
            eviction_batch,
        )

    def db_file_size(self) -> int:
        # Get the database file path from the connection
        db_info = self.conn.execute("PRAGMA database_list").fetchone()
        if not db_info:
            logger.debug("No database info found, returning 0 for file size")
            return 0

        # The second column is the file path, but for in-memory databases it's empty
        path = db_info[2]  # Use index 2 for the file path
        if not path or path == ":memory:":
            logger.debug("In-memory database or no path, returning 0 for file size")
            return 0

        try:
            size = os.path.getsize(path)
            logger.debug("Database file size: %s bytes", size)
            return size
        except (OSError, FileNotFoundError) as e:
            logger.warning("Could not get file size for %s: %s", path, e)
            return 0

    def _evict_until_size_below_limit(self) -> None:
        """Evict old entries in batches until database size is below the limit."""
        if self.max_mb is None:
            logger.debug("No size limit set, skipping eviction")
            return

        max_bytes = self.max_mb * 1024 * 1024
        logger.info("Starting eviction process, target size: %s bytes", max_bytes)

        eviction_rounds = 0
        while self.db_file_size() > max_bytes:
            # Get current count to see if there are any rows to evict
            cursor = self.conn.execute("SELECT COUNT(*) FROM readings")
            current_count = cursor.fetchone()[0]

            if current_count == 0:
                logger.debug("No more data to evict, stopping")
                break  # No more data to evict

            # Evict a batch of old entries
            self.conn.execute(self.EVICT_SQL, (self.eviction_batch,))
            eviction_rounds += 1

            logger.info(
                "Eviction round %s: removed %s entries, remaining: %s",
                eviction_rounds,
                self.eviction_batch,
                current_count - self.eviction_batch,
            )

        if eviction_rounds > 0:
            final_size = self.db_file_size()
            logger.info(
                "Eviction complete: %s rounds, final size: %s bytes",
                eviction_rounds,
                final_size,
            )
        else:
            logger.debug("No eviction needed")

    def append(self, data: str) -> int:
        logger.debug("Appending data: %s", data[:100] + "..." if len(data) > 100 else data)

        # Check if we need to evict old entries due to size limit
        if self.max_mb is not None:
            current_size = self.db_file_size()
            max_bytes = self.max_mb * 1024 * 1024
            if current_size > max_bytes:
                logger.info(
                    "Database size %s bytes exceeds limit %s bytes, triggering eviction",
                    current_size,
                    max_bytes,
                )
                self._evict_until_size_below_limit()

        curr = self.conn.execute(self.INSERT_SQL, (data,))
        row_id = curr.lastrowid
        logger.debug("Inserted data with row_id: %s", row_id)
        return row_id

    def mark_sent(self, row_id: int) -> None:
        logger.debug("Marking row %s as sent", row_id)
        result = self.conn.execute(self.MARK_SENT_SQL, (row_id,))
        rows_affected = result.rowcount
        if rows_affected == 0:
            logger.warning("No rows were marked as sent for row_id: %s", row_id)
        else:
            logger.debug("Successfully marked row %s as sent", row_id)

    def unsent(self) -> Iterable[Tuple[int, str]]:
        logger.debug("Retrieving unsent entries")
        cursor = self.conn.execute(self.UNSENT_SQL)
        rows = list(cursor)
        logger.debug("Found %s unsent entries", len(rows))
        return rows

    def get_stats(self) -> dict:
        """Get statistics about the buffer."""
        cursor = self.conn.execute("SELECT COUNT(*) FROM readings")
        total_count = cursor.fetchone()[0]

        cursor = self.conn.execute("SELECT COUNT(*) FROM readings WHERE sent = 1")
        sent_count = cursor.fetchone()[0]

        unsent_count = total_count - sent_count
        file_size = self.db_file_size()

        stats = {
            "total_entries": total_count,
            "sent_entries": sent_count,
            "unsent_entries": unsent_count,
            "file_size_bytes": file_size,
            "max_mb": self.max_mb,
            "eviction_batch": self.eviction_batch,
        }

        logger.info("Buffer stats: %s", stats)
        return stats
