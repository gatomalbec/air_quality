# src/scripts/danger_wipe_database.py
"""
**IRREVERSIBLE – drops every table in the configured database.**

Usage
-----
# prompt for explicit confirmation
poetry run python src/scripts/danger_wipe_database.py

# non‑interactive wipe (CI, scripts)
poetry run python src/scripts/danger_wipe_database.py --force
"""

import argparse
import sys

# project settings – adjust import path if yours differs
from air_quality_core.config.settings import settings
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError


def drop_everything(url: str) -> None:
    """Connect to *url* and drop all tables and materialized views."""
    engine = create_engine(url, future=True)

    with engine.connect() as conn:
        conn.execute(text("COMMIT"))  # end implicit txn if any
        conn.execute(
            text(
                """
                DO
                $do$
                DECLARE
                    obj record;
                BEGIN
                    -- drop views first
                    FOR obj IN
                        SELECT schemaname, relname
                        FROM pg_views
                        WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
                    LOOP
                        EXECUTE format('DROP VIEW IF EXISTS %I.%I CASCADE',
                                       obj.schemaname, obj.relname);
                    END LOOP;

                    -- drop tables
                    FOR obj IN
                        SELECT schemaname, tablename
                        FROM pg_tables
                        WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
                    LOOP
                        EXECUTE format('DROP TABLE IF EXISTS %I.%I CASCADE',
                                       obj.schemaname, obj.tablename);
                    END LOOP;
                END
                $do$;
                """
            )
        )
        conn.commit()
    engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="*** DANGER *** Drop ALL tables in the configured database."
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="skip confirmation prompt (use in CI / non‑interactive runs)",
    )
    args = parser.parse_args()

    if not args.force:
        msg = (
            "This will irrevocably DELETE **ALL** data in the database "
            f"pointed to by settings.DATABASE_URL = {settings.DATABASE_URL!r}\n"
            "Type 'wipe' and press <Enter> to continue: "
        )
        if input(msg).strip().lower() != "wipe":
            print("Aborted.")
            sys.exit(1)

    try:
        drop_everything(settings.DATABASE_URL)
        print("All tables dropped. Database is now empty.")
    except SQLAlchemyError as exc:
        print(f"ERROR – wipe failed: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
