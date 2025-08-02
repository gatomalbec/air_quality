from air_quality_core.domain.ports import UnitOfWork


def delete_readings_matching(device_id_contains: str, uow: UnitOfWork) -> None:
    with uow:
        uow.reading_repo().delete_device_ids_containing(device_id_contains)
        uow.device_mapping_repo().delete_device_ids_containing(device_id_contains)
