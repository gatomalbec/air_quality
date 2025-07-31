import io
import struct
from typing import Optional

from typing_extensions import Buffer

from air_quality_sensor.sensing.pms5003 import PMS5003Protocol


class FakePMS5003(io.BytesIO):
    """Mock PMS5003 sensor that simulates the actual sensor protocol.

    This mock simulates the PMS5003 sensor's behavior, including:
    - Passive mode setup with ACK responses
    - Frame request handling
    - Proper sensor data frame generation with checksums

    The sensor starts in active mode and switches to passive mode when
    the SET_PASSIVE command is received.
    """

    def __init__(
        self,
        *,
        pm1_cf: int = 10,
        pm2_5_cf: int = 12,
        pm10_cf: int = 15,
        pm1_atm: Optional[int] = None,
        pm2_5_atm: Optional[int] = None,
        pm10_atm: Optional[int] = None,
        protocol: Optional[PMS5003Protocol] = None,
    ):
        # Set default ATM values to CF values if not specified
        pm1_atm = pm1_cf if pm1_atm is None else pm1_atm
        pm2_5_atm = pm2_5_cf if pm2_5_atm is None else pm2_5_atm
        pm10_atm = pm10_cf if pm10_atm is None else pm10_atm

        # Store the sensor values
        self._pm1_cf = pm1_cf
        self._pm2_5_cf = pm2_5_cf
        self._pm10_cf = pm10_cf
        self._pm1_atm = pm1_atm
        self._pm2_5_atm = pm2_5_atm
        self._pm10_atm = pm10_atm

        # Store protocol configuration
        self.protocol = protocol or PMS5003Protocol()

        # Sensor state
        self._passive_mode = False
        self._next_response: Optional[bytes] = None

        # Initialize with empty buffer
        super().__init__(b"")

    def _create_sensor_frame(self) -> bytes:
        """Create a valid PMS5003 sensor data frame.

        Returns:
            A complete sensor frame with header, data, and checksum.
        """
        # Frame structure:
        # Byte 0-1: Header
        # Byte 2-3: Frame length (data section length)
        # Byte 4-29: Data (13 words = 26 bytes)
        # Byte 30-31: Checksum (2 bytes)

        # Header
        frame = self.protocol.header

        # Frame length (data section length)
        frame += struct.pack(">H", self.protocol.data_length)

        # Data section (13 words = 26 bytes)
        # First 6 words are the PM values
        data_words = [
            self._pm1_cf,
            self._pm2_5_cf,
            self._pm10_cf,
            self._pm1_atm,
            self._pm2_5_atm,
            self._pm10_atm,
        ]

        # Add 7 more words (14 bytes) of unused data
        data_words.extend([0] * 7)

        # Pack all 13 words as big-endian uint16
        frame += struct.pack(">13H", *data_words)

        # Calculate checksum (sum of all bytes except checksum)
        checksum = sum(frame) & 0xFFFF
        frame += struct.pack(">H", checksum)

        return frame

    def write(self, data: Buffer) -> int:
        """Handle commands sent to the sensor.

        Args:
            data: Command bytes sent to the sensor.

        Returns:
            Number of bytes written.
        """
        # Convert Buffer to bytes for comparison
        data_bytes = bytes(data)

        if data_bytes == self.protocol.set_passive_cmd:
            # Switch to passive mode and prepare ACK response
            self._passive_mode = True
            self._next_response = self.protocol.set_passive_cmd
            return len(data_bytes)
        elif data_bytes == self.protocol.req_frame_cmd:
            # Request a reading - prepare sensor frame response
            if self._passive_mode:
                self._next_response = self._create_sensor_frame()
            else:
                # If not in passive mode, ignore the request
                self._next_response = b""
            return len(data_bytes)
        else:
            # Unknown command - ignore
            return len(data_bytes)

    def read(self, n: int | None = -1) -> bytes:
        """Read response data from the sensor.

        Args:
            n: Number of bytes to read. -1 or None means all available.
        Returns:
            Response bytes from the sensor.
        """
        if n is None or n == -1:
            if self._next_response:
                response = self._next_response
                self._next_response = None
                return response
            return b""
        if self._next_response:
            response = self._next_response[:n]
            self._next_response = self._next_response[n:]
            if not self._next_response:
                self._next_response = None
            return response
        return b""

    def reset_input_buffer(self) -> None:
        """Reset the input buffer (pyserial compatibility)."""
        self._next_response = None
        self.seek(0)


class BadChecksumFakePMS5003(FakePMS5003):
    """Mock that returns frames with bad checksums for testing error handling."""

    def _create_sensor_frame(self) -> bytes:
        frame = super()._create_sensor_frame()
        # Replace checksum with zeros to make it invalid
        return frame[:-2] + b"\x00\x00"


class TimeoutFakePMS5003(FakePMS5003):
    """Mock that simulates timeouts by returning incomplete frames."""

    def read(self, n: int | None = -1) -> bytes:
        if n is None or n == -1:
            if self._next_response:
                # Simulate timeout by returning only half the data
                response = self._next_response[: len(self._next_response) // 2]
                self._next_response = self._next_response[len(self._next_response) // 2 :]
                if not self._next_response:
                    self._next_response = None
                return response
            return b""
        if self._next_response:
            response = self._next_response[: max(1, n // 2)]
            self._next_response = self._next_response[max(1, n // 2) :]
            if not self._next_response:
                self._next_response = None
            return response
        return b""
