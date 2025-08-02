import logging
import struct
import time
from dataclasses import dataclass
from typing import Optional, Protocol


class SerialLike(Protocol):
    """Protocol defining the interface for serial communication.

    This protocol defines the minimum interface required for serial
    communication with the PMS5003 sensor. Any object implementing
    these methods can be used as a serial port.

    Attributes:
        read: Method to read bytes from the serial port.
        write: Method to write bytes to the serial port.
    """

    def read(self, n: int) -> bytes:
        """Read n bytes from the serial port.

        Args:
            n: Number of bytes to read.

        Returns:
            The bytes read from the serial port.
        """
        ...

    def write(self, b: bytes) -> int:
        """Write bytes to the serial port.

        Args:
            b: Bytes to write to the serial port.

        Returns:
            Number of bytes written.
        """
        ...


@dataclass
class PMS5003Reading:
    """Data class representing a reading from the PMS5003 air quality sensor.

    This class holds all the particulate matter measurements from a single
    sensor reading, including both CF (calibration factor) and ATM (atmospheric)
    values for different particle sizes.

    Attributes:
        pm1_cf: PM1.0 concentration in μg/m³ (calibration factor).
        pm25_cf: PM2.5 concentration in μg/m³ (calibration factor).
        pm10_cf: PM10 concentration in μg/m³ (calibration factor).
        pm1_atm: PM1.0 concentration in μg/m³ (atmospheric).
        pm25_atm: PM2.5 concentration in μg/m³ (atmospheric).
        pm10_atm: PM10 concentration in μg/m³ (atmospheric).
    """

    pm1_cf: int
    pm25_cf: int
    pm10_cf: int
    pm1_atm: int
    pm25_atm: int
    pm10_atm: int


@dataclass
class PMS5003Protocol:
    """Configuration for PMS5003 sensor protocol constants.

    This class encapsulates all the protocol-specific constants for the PMS5003
    sensor, making the code more maintainable and less fragile to protocol changes.

    Attributes:
        header: The expected header bytes for sensor frames.
        frame_length: The expected length of sensor frames in bytes.
        data_length: The length of the data section in bytes.
        checksum_length: The length of the checksum in bytes.
        data_start_offset: The byte offset where data section starts.
        checksum_start_offset: The byte offset where checksum starts.
        unpack_format: Format string for unpacking the sensor data.
        set_passive_cmd: Command to set the sensor to passive mode.
        req_frame_cmd: Command to request a reading from the sensor.
    """

    header: bytes = b"\x42\x4d"
    frame_length: int = 32
    data_length: int = 26  # 13 words * 2 bytes per word
    checksum_length: int = 2
    data_start_offset: int = 4
    checksum_start_offset: int = 30
    unpack_format: str = ">13H"  # 13 big-endian uint16
    set_passive_cmd: bytes = b"\x42\x4d\xe1\x00\x00\xe1"
    req_frame_cmd: bytes = b"\x42\x4d\xe2\x00\x00\xe2"

    @property
    def data_end_offset(self) -> int:
        """The byte offset where data section ends."""
        return self.data_start_offset + self.data_length

    @property
    def checksum_end_offset(self) -> int:
        """The byte offset where checksum ends."""
        return self.checksum_start_offset + self.checksum_length


@dataclass
class PMS5003Config:
    """Configuration for PMS5003 sensor behavior.

    Attributes:
        max_retries: Maximum number of retry attempts for failed readings.
        timeout_seconds: Timeout in seconds for reading operations.
    """

    max_retries: int = 3
    timeout_seconds: float = 1.0


class PMS5003:
    """Driver class for the PMS5003 air quality sensor.

    This class provides an interface to communicate with the PMS5003 particulate
    matter sensor. It handles the sensor protocol, including setting the sensor
    to passive mode, requesting readings, and parsing the response frames.

    The sensor communicates using a configurable frame format with a checksum.
    Readings include particulate matter concentrations for PM1.0, PM2.5, and PM10
    in both CF (calibration factor) and ATM (atmospheric) units.

    Attributes:
        protocol: Protocol configuration containing frame format constants.
        crc_errors: Counter for checksum errors encountered.
        timeouts: Counter for timeout errors encountered.
    """

    def __init__(
        self,
        port: SerialLike,
        config: Optional[PMS5003Config] = None,
        protocol: Optional[PMS5003Protocol] = None,
    ):
        """Initialize the PMS5003 sensor driver.

        Args:
            port: A serial-like object that implements the SerialLike protocol.
            config: Configuration for retry and timeout behavior. If None, uses defaults.
            protocol: Protocol configuration. If None, uses PMS5003 defaults.

        Note:
            During initialization, the sensor is set to passive mode and the
            acknowledgment response is discarded.
        """
        self._s = port
        self.config = config or PMS5003Config()
        self.protocol = protocol or PMS5003Protocol()
        self.crc_errors = 0
        self.timeouts = 0

        # Set up logging
        self.logger = logging.getLogger(f"{__name__}.PMS5003")

        self.logger.info("Initializing PMS5003 sensor")
        self.logger.debug(
            f"Configuration: max_retries={self.config.max_retries}, "
            f"timeout_seconds={self.config.timeout_seconds}"
        )
        self.logger.debug(
            f"Protocol: frame_length={self.protocol.frame_length}, "
            f"data_length={self.protocol.data_length}"
        )

        # Set sensor to passive mode
        self.logger.debug("Setting sensor to passive mode")
        self._s.write(self.protocol.set_passive_cmd)
        ack = self._s.read(8)
        self.logger.debug(f"Received ACK: {ack.hex()}")

        self.logger.info("PMS5003 sensor initialized successfully")

    def _checksum_ok(self, frame: bytes) -> bool:
        """Validate the checksum of a PMS5003 sensor frame.

        The PMS5003 sensor sends data in frames with a checksum at the end.
        This method calculates the expected checksum and compares it with
        the received checksum.

        Args:
            frame: The frame received from the sensor.

        Returns:
            True if the checksum is valid, False otherwise.
        """
        expected_checksum = int.from_bytes(
            frame[self.protocol.checksum_start_offset : self.protocol.checksum_end_offset], "big"
        )
        calculated_checksum = sum(frame[: self.protocol.checksum_start_offset]) & 0xFFFF
        is_valid = expected_checksum == calculated_checksum

        if not is_valid:
            self.logger.warning(
                f"Checksum validation failed: expected={expected_checksum:04x}, "
                f"calculated={calculated_checksum:04x}"
            )

        return is_valid

    def _parse(self, frame: bytes) -> PMS5003Reading:
        """Parse a valid sensor frame into a PMS5003Reading object.

        This method unpacks the binary data from the sensor frame and creates
        a PMS5003Reading object with the particulate matter measurements.

        Args:
            frame: A valid frame from the sensor.

        Returns:
            A PMS5003Reading object containing the parsed sensor measurements.

        Note:
            This method assumes the frame has already been validated for
            length, header, and checksum.
        """
        w = struct.unpack(
            self.protocol.unpack_format,
            frame[self.protocol.data_start_offset : self.protocol.data_end_offset],
        )
        reading = PMS5003Reading(
            pm1_cf=w[0],
            pm25_cf=w[1],
            pm10_cf=w[2],
            pm1_atm=w[3],
            pm25_atm=w[4],
            pm10_atm=w[5],
        )

        self.logger.debug(
            f"Parsed reading: PM1={reading.pm1_cf}, PM2.5={reading.pm25_cf}, "
            f"PM10={reading.pm10_cf} μg/m³"
        )

        return reading

    def _read_single_attempt(self) -> Optional[PMS5003Reading]:
        """Attempt a single reading from the sensor.

        Returns:
            A PMS5003Reading object if successful, None if failed.
        """
        self.logger.debug("Requesting sensor reading")
        self._s.write(self.protocol.req_frame_cmd)

        frame = self._s.read(self.protocol.frame_length)
        self.logger.debug(f"Received frame: {len(frame)} bytes")

        # Check frame length
        if len(frame) != self.protocol.frame_length:
            self.timeouts += 1
            self.logger.warning(
                f"Frame length error: expected {self.protocol.frame_length}, got {len(frame)} bytes"
            )
            return None

        # Check frame header
        if frame[: len(self.protocol.header)] != self.protocol.header:
            self.timeouts += 1
            self.logger.warning(
                f"Frame header error: expected {self.protocol.header.hex()}, "
                f"got {frame[:len(self.protocol.header)].hex()}"
            )
            return None

        # Check checksum
        if not self._checksum_ok(frame):
            self.crc_errors += 1
            return None

        self.logger.debug("Frame validation successful")
        return self._parse(frame)

    def read(self) -> Optional[PMS5003Reading]:
        """Read a measurement from the PMS5003 sensor with retry logic.

        This method requests a reading from the sensor in passive mode,
        validates the response frame, and returns the parsed measurements.
        If the frame is invalid or corrupted, it will retry up to the
        configured maximum number of attempts.

        Returns:
            A PMS5003Reading object containing the sensor measurements if the
            frame is valid, None if all retry attempts failed.

        Note:
            The sensor must be in passive mode for this method to work.
            Timeout errors occur when the frame length or header is incorrect.
            CRC errors occur when the checksum validation fails.
        """
        self.logger.debug(f"Starting sensor read (max_retries={self.config.max_retries})")

        for attempt in range(self.config.max_retries):
            attempt_num = attempt + 1
            self.logger.debug(f"Attempt {attempt_num}/{self.config.max_retries}")

            reading = self._read_single_attempt()
            if reading is not None:
                self.logger.info(f"Successfully read sensor data on attempt {attempt_num}")
                return reading

            # Log the failure
            if attempt < self.config.max_retries - 1:
                self.logger.warning(
                    f"Attempt {attempt_num} failed, retrying in {self.config.timeout_seconds}s "
                    f"(crc_errors={self.crc_errors}, timeouts={self.timeouts})"
                )
                time.sleep(self.config.timeout_seconds)
            else:
                self.logger.error(
                    f"All {self.config.max_retries} attempts failed. "
                    f"Final error counts: crc_errors={self.crc_errors}, timeouts={self.timeouts}"
                )

        return None
