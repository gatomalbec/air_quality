from typing import List, Optional, Protocol

from air_quality_core.domain.models import Reading


class ReadingRepository(Protocol):
    def get_latest_for_devices(
        self, device_ids: List[str], limit: int = 100
    ) -> List[Reading]: ...

    def get_readings_for_devices_in_range(
        self,
        device_ids: List[str],
        start_ts: Optional[float],
        end_ts: Optional[float],
    ) -> List[Reading]: ...

    def insert(self, reading: Reading) -> None: ...
