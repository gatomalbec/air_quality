from datetime import datetime, timezone

import factory
from air_quality_core.domain.models import Reading


class UTCFloatTimestamp(factory.Factory):
    class Meta:
        model = float

    @classmethod
    def _create(cls, *_, **__):
        return datetime.now(tz=timezone.utc).timestamp()


class ReadingFactory(factory.Factory):
    class Meta:
        model = Reading

    ts = UTCFloatTimestamp()
    device_id = factory.Sequence(lambda n: f"sensor-{n}")
    pm1 = 1
    pm25 = 2
    pm10 = 3
