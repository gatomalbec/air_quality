import logging
import queue
import random
import threading
from collections import deque
from typing import Iterable, Protocol, runtime_checkable

from air_quality_sensor.buffered_publisher import BufferedPublisher
from air_quality_sensor.sensor_types import Serializable

logger = logging.getLogger(__name__)

logger = logging.getLogger(__name__)


@runtime_checkable
class BackoffPolicy(Protocol):
    """Protocol for backoff policy implementations."""

    def next_delay(self, *, success: bool) -> float: ...


class ExponentialBackoff(BackoffPolicy):
    """Exponential backoff with jitter for retry logic."""

    def __init__(self, base: float = 1.0, max_: float = 60.0, jitter: float = 0.5):
        self._base = base
        self._max = max_
        self._jitter = jitter
        self._current_delay = base

    def next_delay(self, *, success: bool) -> float:
        """Calculate the next delay based on success/failure."""
        if success:
            self._current_delay = self._base
            return 0.0

        self._current_delay = min(self._current_delay * 2, self._max)
        return self._current_delay * (1 + random.uniform(-self._jitter, self._jitter))


class DeliveryLoop(threading.Thread):
    """Thread that continuously delivers messages from queue and backlog."""

    def __init__(
        self,
        q: queue.Queue[Serializable],
        outbound: BufferedPublisher,
        backlog: Iterable[Serializable],
        backoff: BackoffPolicy,
    ):
        super().__init__(name="delivery-loop")
        self._q = q
        self._out = outbound
        self._backlog = deque(backlog)
        self._backoff = backoff
        self._stop_event = threading.Event()
        logger.info("DeliveryLoop initialized with %d backlog items", len(self._backlog))

    def stop(self) -> None:
        """Signal the delivery loop to stop."""
        logger.info("Stopping delivery loop")
        self._stop_event.set()

    def run(self) -> None:
        """Main delivery loop that processes messages from queue and backlog."""
        logger.info("Starting delivery loop")

        while not self._stop_event.is_set():
            # Get next message from backlog or queue
            if self._backlog:
                msg = self._backlog.popleft()
                logger.debug("Processing message from backlog")
            else:
                try:
                    msg = self._q.get(timeout=1)
                    logger.debug("Processing message from queue")
                except queue.Empty:
                    continue

            # Attempt to publish the message
            logger.debug("Attempting to publish message")
            ok = self._out.publish(msg)

            if not ok:
                logger.warning("Failed to publish message, adding to backlog for retry")
                self._backlog.appendleft(msg)
                delay = self._backoff.next_delay(success=False)
                if delay:
                    logger.debug("Waiting %.2f seconds before retry", delay)
                    self._stop_event.wait(delay)
            else:
                logger.debug("Successfully published message")
                self._backoff.next_delay(success=True)

        logger.info("Delivery loop stopped")
