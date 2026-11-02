"""Create or upgrade every table the app needs. Safe to run again at any time.

One command sets up a brand-new database (CI, Docker, Azure): the core schema, then the auth columns
and the audit table that used to need their own migrate scripts.

Usage: python -m scripts.init_db
"""
import psycopg

from app.config import DATABASE_URL
from app.services.vector_store import VectorStoreService
from scripts import migrate_audit, migrate_auth


def main() -> None:
    VectorStoreService().init_schema()
    with psycopg.connect(DATABASE_URL) as conn:
        for statement in migrate_auth.STATEMENTS + migrate_audit.STATEMENTS:
            conn.execute(statement)
    print("Database ready: schema (pgvector, HNSW, hybrid search), auth columns and audit table.")


if __name__ == "__main__":
    main()
