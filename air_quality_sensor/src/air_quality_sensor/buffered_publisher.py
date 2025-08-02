import logging
from typing import Protocol, runtime_checkable

from air_quality_sensor.sensor_types import Serializable
from air_quality_sensor.sqlite_buffer import BufferWriter

logger = logging.getLogger(__name__)


@runtime_checkable
class OutboundPort(Protocol):
    """Protocol for outbound message publishing."""

    def publish(self, msg: Serializable) -> bool: ...


class BufferedPublisher(OutboundPort):
    """
    Buffered publisher that ensures message durability.

    Flow:
    1. Persist message to buffer → row_id = buffer.append(msg)
    2. Attempt network publish → ok = pusher.publish(msg)
    3. If successful: mark as sent → buffer.mark_sent(row_id)
       If failed: message remains unsent for replay
    """

    def __init__(self, buffer: BufferWriter, pusher: OutboundPort):
        self.buffer = buffer
        self.pusher = pusher

    def publish(self, msg: Serializable) -> bool:
        """
        Publish a message with durability guarantees.

        Args:
            msg: The message to publish

        Returns:
            bool: True if message was successfully published, False otherwise
        """
        try:
            # Step 1: Persist to buffer
            msg_str = msg.to_string()
            row_id = self.buffer.append(msg_str)

            # Step 2: Attempt network publish
            ok = self.pusher.publish(msg)

            # Step 3: Handle result
            if ok:
                self.buffer.mark_sent(row_id)
                logger.info("Message successfully published and marked as durable")
            else:
                logger.warning("Message publish failed, will remain in buffer for replay")

            return ok

        except Exception as e:
            logger.error("Error in buffered publish operation: %s", e)
            return False
