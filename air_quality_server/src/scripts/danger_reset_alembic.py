# dangerous!
from air_quality_core.config.settings import settings
from sqlalchemy import create_engine, text

engine = create_engine(settings.DATABASE_URL)

with engine.connect() as conn:
    conn.execute(text("DELETE FROM alembic_version WHERE version_num = '54390cfee87e'"))
    conn.commit()
    print("Removed bad Alembic version from DB.")
