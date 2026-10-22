"""Standalone Migration Runner for Notes MCP Server.

Executes `001_create_notes_schema.sql` against the database specified in the root `.env`.
Safe, idempotent, and non-destructive.
"""

import sys
from pathlib import Path
import psycopg

# Add parent notes_server package to sys.path to resolve config
CURRENT_DIR = Path(__file__).resolve().parent
NOTES_ROOT = CURRENT_DIR.parent
SRC_DIR = NOTES_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from notes_server.config import get_database_url, get_masked_db_url  # noqa: E402


def run_migration() -> None:
    migration_file = CURRENT_DIR / "001_create_notes_schema.sql"
    if not migration_file.exists():
        print(f"Error: Migration file not found at {migration_file}", file=sys.stderr)
        sys.exit(1)

    try:
        db_url = get_database_url()
    except Exception as exc:
        print(f"Configuration Error: {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"Connecting to database ({get_masked_db_url()})...")

    try:
        sql_content = migration_file.read_text(encoding="utf-8")
        with psycopg.connect(db_url, autocommit=True) as conn:
            with conn.cursor() as cur:
                print("Executing migration 001_create_notes_schema.sql...")
                cur.execute(sql_content)
                
                # Check created tables
                cur.execute("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                      AND table_name IN ('notes', 'vocabulary', 'review_history')
                    ORDER BY table_name;
                """)
                tables = [row[0] for row in cur.fetchall()]

                # Check created indexes
                cur.execute("""
                    SELECT indexname 
                    FROM pg_indexes 
                    WHERE schemaname = 'public' 
                      AND tablename IN ('notes', 'vocabulary', 'review_history')
                    ORDER BY indexname;
                """)
                indexes = [row[0] for row in cur.fetchall()]

        print("Migration applied successfully!")
        print(f"Verified tables: {', '.join(tables)}")
        print(f"Verified indexes count: {len(indexes)}")

    except psycopg.OperationalError as exc:
        print(f"Database connection error: Could not connect to PostgreSQL. {exc}", file=sys.stderr)
        sys.exit(1)
    except psycopg.Error as exc:
        print(f"Database error during migration: {exc}", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        print(f"Unexpected error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    run_migration()

