from typing import List, Optional, Protocol

from air_quality_core.domain.models import Reading


class ReadingRepository(Protocol):
    def get_latest_for_devices(self, device_ids: List[str], limit: int = 100) -> List[Reading]: ...

    def get_readings_for_devices_in_range(
        self,
        device_ids: List[str],
        start_ts: Optional[float],
        end_ts: Optional[float],
    ) -> List[Reading]: ...

    def insert(self, reading: Reading) -> None: ...

    def delete_device_ids_containing(self, substr: str) -> None: ...


class DeviceMappingRepository(Protocol):
    def get_device_ids_for_room(
        self, room: str, start_ts: Optional[float], end_ts: Optional[float]
    ) -> List[str]: ...

    def add_mapping(
        self, device_id: str, room: str, start_ts: float, end_ts: Optional[float]
    ) -> None: ...

    def delete_device_ids_containing(self, substr: str) -> None: ...


class UnitOfWork(Protocol):
    def reading_repo(self) -> ReadingRepository: ...

    def device_mapping_repo(self) -> DeviceMappingRepository: ...

    def __enter__(self) -> "UnitOfWork": ...

    def __exit__(self, exc_type, exc_val, exc_tb) -> None: ...
