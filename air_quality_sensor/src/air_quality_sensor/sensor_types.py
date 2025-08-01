from dataclasses import dataclass
from typing import Any, Generic, Protocol, TypeVar


class Serializable(Protocol):
    def to_dict(self) -> dict[str, Any]: ...


T = TypeVar("T", bound=Serializable)


@dataclass
class SensorReading(Generic[T]):
    ts: float
    device_id: str
    payload: T
