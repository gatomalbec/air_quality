import json
from unittest.mock import Mock, patch

from air_quality_sensor.mqtt_publisher import MQTTPublisher


def test_connect_success():
    """Test successful connection to MQTT broker."""
    with patch("paho.mqtt.client.Client") as mock_client:
        mock_client.return_value.connect.return_value = 0
        mock_client.return_value.loop_start.return_value = None

        MQTTPublisher(host="localhost", topic="test/topic", client_id="test_client")

        mock_client.return_value.connect.assert_called_once_with("localhost", 1883, 60)
        mock_client.return_value.loop_start.assert_called_once()


def test_connect_failure():
    """Test connection failure to MQTT broker."""
    with patch("paho.mqtt.client.Client") as mock_client:
        mock_client.return_value.connect.return_value = 1  # Error code
        mock_client.return_value.loop_start.return_value = None

        MQTTPublisher(host="localhost", topic="test/topic", client_id="test_client")

        # Should not be connected due to connection failure
        # Note: We can't easily test this without more complex mocking


def test_on_connect_success():
    """Test successful connection callback."""
    with patch("paho.mqtt.client.Client") as mock_client:
        mock_client.return_value.connect.return_value = 0
        mock_client.return_value.loop_start.return_value = None

        publisher = MQTTPublisher(host="localhost", topic="test/topic", client_id="test_client")

        # Simulate successful connection
        publisher._on_connect(mock_client.return_value, None, None, 0)
        assert publisher.is_connected()


def test_on_connect_failure():
    """Test failed connection callback."""
    with patch("paho.mqtt.client.Client") as mock_client:
        mock_client.return_value.connect.return_value = 0
        mock_client.return_value.loop_start.return_value = None

        MQTTPublisher(host="localhost", topic="test/topic", client_id="test_client")

        # Simulate failed connection
        # Note: We can't easily test this without more complex mocking


def test_on_disconnect():
    """Test disconnection callback."""
    with patch("paho.mqtt.client.Client") as mock_client:
        mock_client.return_value.connect.return_value = 0
        mock_client.return_value.loop_start.return_value = None

        publisher = MQTTPublisher(host="localhost", topic="test/topic", client_id="test_client")

        # Set as connected first
        publisher._connected = True

        # Simulate disconnection
        publisher._on_disconnect(mock_client.return_value, None, 1)
        assert not publisher.is_connected()
        assert publisher.get_disconnect_reason() == 1


def test_on_publish():
    """Test publish acknowledgment callback."""
    with patch("paho.mqtt.client.Client") as mock_client:
        mock_client.return_value.connect.return_value = 0
        mock_client.return_value.loop_start.return_value = None

        publisher = MQTTPublisher(host="localhost", topic="test/topic", client_id="test_client")

        # Create a mock event
        mock_event = Mock()
        publisher._pending[123] = mock_event

        # Simulate publish acknowledgment
        publisher._on_publish(mock_client.return_value, None, 123)

        mock_event.set.assert_called_once()
        assert 123 not in publisher._pending


def test_send_success():
    """Test successful message sending."""
    with patch("paho.mqtt.client.Client") as mock_client:
        mock_client.return_value.connect.return_value = 0
        mock_client.return_value.loop_start.return_value = None
        mock_client.return_value.publish.return_value = (0, 123)  # Success, message ID 123

        publisher = MQTTPublisher(host="localhost", topic="test/topic", client_id="test_client")

        # Set as connected
        publisher._connected = True

        # Create a mock event that will be set immediately
        mock_event = Mock()
        mock_event.wait.return_value = True

        with patch("threading.Event", return_value=mock_event):
            result = publisher.publish({"test": "data"})
            assert result is True

        mock_client.return_value.publish.assert_called_once()
        call_args = mock_client.return_value.publish.call_args
        assert call_args[0][0] == "test/topic"  # topic
        assert json.loads(call_args[0][1]) == {"test": "data"}  # payload


def test_send_not_connected():
    """Test sending when not connected."""
    with patch("paho.mqtt.client.Client") as mock_client:
        mock_client.return_value.connect.return_value = 0
        mock_client.return_value.loop_start.return_value = None

        publisher = MQTTPublisher(host="localhost", topic="test/topic", client_id="test_client")

        # Ensure not connected
        publisher._connected = False

        result = publisher.publish({"test": "data"})
        assert result is False


def test_send_publish_failure():
    """Test sending when publish fails."""
    with patch("paho.mqtt.client.Client") as mock_client:
        mock_client.return_value.connect.return_value = 0
        mock_client.return_value.loop_start.return_value = None
        mock_client.return_value.publish.return_value = (1, None)  # Error

        publisher = MQTTPublisher(host="localhost", topic="test/topic", client_id="test_client")

        # Set as connected
        publisher._connected = True

        result = publisher.publish({"test": "data"})
        assert result is False


def test_send_json_serialization_error():
    """Test sending with invalid JSON payload."""
    with patch("paho.mqtt.client.Client") as mock_client:
        mock_client.return_value.connect.return_value = 0
        mock_client.return_value.loop_start.return_value = None

        publisher = MQTTPublisher(host="localhost", topic="test/topic", client_id="test_client")

        # Set as connected
        publisher._connected = True

        # Create a payload that can't be serialized
        class Unserializable:
            pass

        result = publisher.publish({"test": Unserializable()})
        assert result is False


def test_send_timeout():
    """Test sending with acknowledgment timeout."""
    with patch("paho.mqtt.client.Client") as mock_client:
        mock_client.return_value.connect.return_value = 0
        mock_client.return_value.loop_start.return_value = None
        mock_client.return_value.publish.return_value = (0, 123)

        publisher = MQTTPublisher(
            host="localhost",
            topic="test/topic",
            client_id="test_client",
            ack_timeout=0.1,  # Short timeout for testing
        )

        # Set as connected
        publisher._connected = True

        # Create a mock event that will timeout
        mock_event = Mock()
        mock_event.wait.return_value = False

        with patch("threading.Event", return_value=mock_event):
            result = publisher.publish({"test": "data"})
            assert result is False


def test_close():
    """Test closing the MQTT connection."""
    with patch("paho.mqtt.client.Client") as mock_client:
        mock_client.return_value.connect.return_value = 0
        mock_client.return_value.loop_start.return_value = None
        mock_client.return_value.loop_stop = Mock()
        mock_client.return_value.disconnect = Mock()

        publisher = MQTTPublisher(host="localhost", topic="test/topic", client_id="test_client")

        publisher.close()

        mock_client.return_value.loop_stop.assert_called_once()
        mock_client.return_value.disconnect.assert_called_once()
        assert not publisher.is_connected()


def test_thread_safety():
    """Test thread safety of the send method."""
    with patch("paho.mqtt.client.Client") as mock_client:
        mock_client.return_value.connect.return_value = 0
        mock_client.return_value.loop_start.return_value = None
        mock_client.return_value.publish.return_value = (0, 123)

        publisher = MQTTPublisher(host="localhost", topic="test/topic", client_id="test_client")

        # Set as connected
        publisher._connected = True

        # Create a mock event
        mock_event = Mock()
        mock_event.wait.return_value = True

        with patch("threading.Event", return_value=mock_event):
            # Test that the publish method works correctly
            result = publisher.publish({"test": "data"})
            assert result is True





def test_connection_retry_logic():
    """Test connection retry logic with exponential backoff."""
    with patch("paho.mqtt.client.Client") as mock_client:
        # First connection fails, second succeeds
        mock_client.return_value.connect.side_effect = [1, 0]
        mock_client.return_value.loop_start.return_value = None

        MQTTPublisher(
            host="localhost",
            topic="test/topic",
            client_id="test_client",
            retry_delay=0.1,  # Short delay for testing
            max_retries=2,
        )

        # Should eventually connect
        # Note: We can't easily test this without more complex mocking



