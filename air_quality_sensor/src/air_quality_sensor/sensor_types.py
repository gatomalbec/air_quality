from dataclasses import dataclass
from typing import Generic, Protocol, TypeVar


class Serializable(Protocol):
    def to_string(self) -> str: ...


T = TypeVar("T", bound=Serializable)


@dataclass
class SensorReading(Generic[T]):
    ts: float
    device_id: str
    payload: T
