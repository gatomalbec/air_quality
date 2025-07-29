from contextlib import AbstractContextManager

from sqlalchemy.orm import Session

from air_quality_server.adapters.db.session import SessionLocal


class SqlAlchemyUoW(AbstractContextManager):
    def __init__(self, session: Session | None = None):
        self._external = session is not None
        self.session: Session = session or SessionLocal()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, *_):
        if self._external:
            return
        if exc_type:
            self.session.rollback()
        else:
            self.session.commit()
        self.session.close()

    def reading_repo(self):
        from air_quality_server.adapters.db.repository import PostgresReadingRepository

        return PostgresReadingRepository(self.session)

    def device_mapping_repo(self):
        from air_quality_server.adapters.db.repository import PostgresDeviceMappingRepository

        return PostgresDeviceMappingRepository(self.session)
