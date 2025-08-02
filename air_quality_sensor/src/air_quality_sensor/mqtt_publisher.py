import logging
import threading
from typing import Dict, Optional, Protocol

import paho.mqtt.client as paho

logger = logging.getLogger(__name__)


class OutboundPublisher(Protocol):
    def publish(self, payload: str) -> bool: ...


class MQTTPublisher(OutboundPublisher):
    def __init__(
        self,
        *,
        host: str,
        port: int = 1883,
        topic: str,
        client_id: str,
        username: Optional[str] = None,
        password: Optional[str] = None,
        keepalive: int = 60,
        reconnect_delay: float = 1.0,
        max_retries: int = 5,
        retry_delay: float = 1.0,
        retry_delay_max: float = 30.0,
        retry_delay_backoff: float = 2.0,
        retry_delay_max_backoff: float = 60.0,
        ack_timeout: float = 10.0,
    ):
        self.host = host
        self.port = port
        self.topic = topic
        self.client_id = client_id
        self.username = username
        self.password = password
        self.keepalive = keepalive
        self.reconnect_delay = reconnect_delay
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.retry_delay_max = retry_delay_max
        self.retry_delay_backoff = retry_delay_backoff
        self.retry_delay_max_backoff = retry_delay_max_backoff
        self.ack_timeout = ack_timeout

        self._pending: Dict[int, threading.Event] = {}
        self._lock = threading.Lock()
        self._connected = False
        self._disconnected_rc: Optional[int] = None

        self._client = paho.Client(
            client_id=client_id,
            clean_session=True,
            userdata=self,
            protocol=paho.MQTTv311,
        )
        self._client.on_publish = self._on_publish
        self._client.on_disconnect = self._on_disconnect
        self._client.on_connect = self._on_connect

        if username and password:
            self._client.username_pw_set(username, password)

        logger.info(
            "Initializing MQTT publisher: host=%s, port=%s, topic=%s, client_id=%s",
            host,
            port,
            topic,
            client_id,
        )

        self._connect()

    def _connect(self) -> None:
        """Connect to the MQTT broker."""
        try:
            result = self._client.connect(self.host, self.port, self.keepalive)
            if result != paho.MQTT_ERR_SUCCESS:
                logger.error("Failed to connect to MQTT broker: %s", result)
                return

            self._client.loop_start()
            logger.info("Connected to MQTT broker")
        except Exception as e:
            logger.error("Exception during MQTT connection: %s", e)

    def _on_connect(self, client, userdata, flags, rc) -> None:
        """Handle connection events."""
        if rc == 0:
            self._connected = True
            logger.info("Successfully connected to MQTT broker")
        else:
            self._connected = False
            logger.error("Failed to connect to MQTT broker, return code: %s", rc)

    def _on_publish(self, client, userdata, mid) -> None:
        """Handle publish acknowledgment."""
        logger.debug("Publish acknowledged for message ID: %s", mid)
        if mid in self._pending:
            self._pending[mid].set()
            del self._pending[mid]

    def _on_disconnect(self, client, userdata, rc) -> None:
        """Handle disconnection events."""
        self._connected = False
        self._disconnected_rc = rc
        logger.warning("Disconnected from MQTT broker, return code: %s", rc)

    def publish(self, payload: str) -> bool:
        """Send a payload to the MQTT topic."""
        if not self._connected:
            logger.warning("Not connected to MQTT broker, cannot send payload")
            return False

        with self._lock:
            result, mid = self._client.publish(self.topic, payload, qos=1, retain=False)
            if result != paho.MQTT_ERR_SUCCESS:
                logger.error("Failed to publish message, error code: %s", result)
                return False

            logger.debug("Message published with ID: %s", mid)
            ev = threading.Event()
            self._pending[mid] = ev
            success = ev.wait(timeout=self.ack_timeout)
            self._pending.pop(mid, None)

            if not success:
                logger.warning("Publish acknowledgment timeout for message ID: %s", mid)

            return success and self._connected

    def is_connected(self) -> bool:
        """Check if connected to the MQTT broker."""
        return self._connected

    def get_disconnect_reason(self) -> Optional[int]:
        """Get the disconnect reason code."""
        return self._disconnected_rc

    def close(self) -> None:
        """Close the MQTT connection."""
        logger.info("Closing MQTT connection")
        self._client.loop_stop()
        self._client.disconnect()
        self._connected = False
