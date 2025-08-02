import json
from dataclasses import asdict, dataclass
from typing import Generic, Protocol, TypeVar


class Serializable(Protocol):
    def to_string(self) -> str: ...


T = TypeVar("T", bound=Serializable)


@dataclass
class SensorReading(Serializable, Generic[T]):
    ts: float
    device_id: str
    payload: T

    def to_string(self) -> str:
        d = asdict(self)
        d["payload"] = self.payload.to_string()
        return json.dumps(d)
