from air_quality_core.domain.models import Reading
from air_quality_core.domain.ports import UnitOfWork


def ingest_reading(reading: Reading, uow: UnitOfWork) -> None:
    with uow:
        uow.reading_repo().insert(reading)
