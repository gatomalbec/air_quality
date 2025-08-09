"""
Test utilities for sensor mocking and test data generation.
"""

import struct
from typing import List

from air_quality_sensor.sensing.pms5003 import PMS5003Reading, SerialLike


def create_test_readings(count: int) -> List[PMS5003Reading]:
    """Create a list of test sensor readings."""
    readings = []

    for i in range(count):
        reading = PMS5003Reading(
            pm1_cf=10 + i,
            pm25_cf=15 + i,
            pm10_cf=20 + i,
            pm1_atm=12 + i,
            pm25_atm=17 + i,
            pm10_atm=22 + i,
        )
        readings.append(reading)

    return readings


class MockSerialPort(SerialLike):
    """Mock serial port that simulates PMS5003 sensor responses."""

    def __init__(self, readings: List[PMS5003Reading]):
        self.readings = readings
        self.current_index = 0
        self._response_buffer = b""

    def read(self, n: int) -> bytes:
        """Simulate reading sensor data frames."""
        # If we don't have a response ready, create one
        if not self._response_buffer:
            if self.current_index >= len(self.readings):
                # If we've used all readings, cycle back to the last one
                self.current_index = len(self.readings) - 1

            # Create a mock sensor frame
            reading = self.readings[self.current_index]
            self.current_index += 1

            # Build frame: header + frame_length + data + checksum
            header = b"\x42\x4d"  # PMS5003 header
            frame_length = struct.pack(">H", 26)  # Data section length (26 bytes)
            data = struct.pack(
                ">13H",
                reading.pm1_cf,
                reading.pm25_cf,
                reading.pm10_cf,
                reading.pm1_atm,
                reading.pm25_atm,
                reading.pm10_atm,
                0,
                0,
                0,
                0,
                0,
                0,
                0,  # Additional fields set to 0
            )

            # Calculate checksum
            frame_without_checksum = header + frame_length + data
            checksum = sum(frame_without_checksum) & 0xFFFF
            checksum_bytes = struct.pack(">H", checksum)

            self._response_buffer = frame_without_checksum + checksum_bytes

        # Return exactly what was requested, or the remaining buffer
        if n >= len(self._response_buffer):
            result = self._response_buffer
            self._response_buffer = b""
        else:
            result = self._response_buffer[:n]
            self._response_buffer = self._response_buffer[n:]

        return result

    def write(self, data: bytes) -> int:
        """Simulate writing commands to sensor."""
        # Clear any previous response when a new command is written
        self._response_buffer = b""
        return len(data)
