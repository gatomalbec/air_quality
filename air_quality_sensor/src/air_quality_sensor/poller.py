import queue
import threading
import time
from typing import Callable

from air_quality_sensor.sensor_types import SensorReading, Serializable


class BaseSensorThread(threading.Thread):
    daemon = True

    def __init__(
        self,
        name: str,
        interval_s: float,
        device_id: str,
        driver: Callable[[], Serializable | None],
        out_q: queue.Queue[SensorReading],
    ):
        super().__init__(name=name)
        self.interval_s = interval_s
        self.device_id = device_id
        self.driver = driver
        self.out_q = out_q
        self.s_stop = threading.Event()

    def stop(self):
        self.s_stop.set()

    def run(self):
        next_tick = time.time() + self.interval_s
        while not self.s_stop.is_set():
            now = time.time()
            if now >= next_tick:
                try:
                    payload = self.driver()
                    if payload is not None:
                        reading = SensorReading(
                            ts=now,
                            device_id=self.device_id,
                            payload=payload,
                        )
                        try:
                            self.out_q.put_nowait(reading)
                        except queue.Full:
                            self.out_q.get_nowait()
                            self.out_q.put_nowait(reading)
                except Exception:
                    pass
                next_tick += self.interval_s
            else:
                self.s_stop.wait(next_tick - now)
