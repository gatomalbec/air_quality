import logging

from air_quality_core.config.environments import get_settings
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

log = logging.getLogger(__name__)


def create_session_factory():
    """Create the session factory with current settings."""
    settings = get_settings()

    # Set up logging based on environment
    logging.basicConfig(
        level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(message)s",
    )

    log.info(f"Initializing database connection for {settings.ENVIRONMENT.value} environment")
    log.info(f"Database URL: {settings.DATABASE_URL}")

    engine = create_engine(settings.DATABASE_URL, future=True, echo=False)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


# Create the session factory
SessionLocal = create_session_factory()

Base = declarative_base()
