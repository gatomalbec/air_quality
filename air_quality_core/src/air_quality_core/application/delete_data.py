from air_quality_server.adapters.db.uow import SqlAlchemyUoW


def delete_readings_matching(device_id_contains: str, uow: SqlAlchemyUoW) -> None:
    with uow:
        uow.reading_repo().delete_device_ids_containing(device_id_contains)
        uow.device_mapping_repo().delete_device_ids_containing(device_id_contains)
