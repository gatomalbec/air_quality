"""
Alembic environment for the *air_quality* project.

Key points
──────────
• Adds the project root to `sys.path` so imports work.
• Imports `settings` to obtain the database URL.
• Uses the single declarative `Base.metadata` for autogeneration.
• Works in both online & offline modes.
"""

from __future__ import annotations

import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import create_engine, pool

from alembic import context

# ---------------------------------------------------------------------------
# 1 – make the application importable
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[1]  # project/src
sys.path.append(str(ROOT))

# ---------------------------------------------------------------------------
# 2 – application imports
# ---------------------------------------------------------------------------
from air_quality_core.config.settings import settings  # pylint: disable=wrong-import-position
from air_quality_server.adapters.db.sqlalchemy_models import (
    Base,  # pylint: disable=wrong-import-position
)

# ---------------------------------------------------------------------------
# 3 – Alembic configuration
# ---------------------------------------------------------------------------
config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)  # pulls in logging
target_metadata = Base.metadata  # for ‑‑autogenerate


# ---------------------------------------------------------------------------
# 4 – helpers
# ---------------------------------------------------------------------------
def get_url() -> str:
    """Return the SQLAlchemy‑compatible DB URL from project settings."""
    return settings.DATABASE_URL


# ---------------------------------------------------------------------------
# 5 – offline migrations (generates SQL script)
# ---------------------------------------------------------------------------
def run_migrations_offline() -> None:
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


# ---------------------------------------------------------------------------
# 6 – online migrations (apply directly)
# ---------------------------------------------------------------------------
def run_migrations_online() -> None:
    connectable = create_engine(
        get_url(),
        poolclass=pool.NullPool,
        future=True,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


# ---------------------------------------------------------------------------
# 7 – entrance
# ---------------------------------------------------------------------------
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
