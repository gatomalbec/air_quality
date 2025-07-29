from air_quality_core.domain.models import Reading
from air_quality_server.adapters.db.uow import SqlAlchemyUoW


def ingest_reading(reading: Reading, uow: SqlAlchemyUoW) -> None:
    with uow:
        uow.reading_repo().insert(reading)
