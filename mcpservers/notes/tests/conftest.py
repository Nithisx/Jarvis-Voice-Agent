"""Pytest configuration and isolated database fixtures for Notes MCP Server tests."""

from __future__ import annotations

import asyncio
import os
import sys
import uuid
from pathlib import Path
from typing import AsyncGenerator, Generator

# On Windows, psycopg async requires WindowsSelectorEventLoopPolicy
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import psycopg
import pytest
import pytest_asyncio
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

# Ensure src is on Python search path
TESTS_DIR = Path(__file__).resolve().parent
NOTES_DIR = TESTS_DIR.parent
SRC_DIR = NOTES_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from notes_server.config import get_database_url
from notes_server.database import db_manager

MIGRATION_PATH = NOTES_DIR / "migrations" / "001_create_notes_schema.sql"


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create a session-wide event loop for async fixtures using selector loop on Windows."""
    if sys.platform == "win32":
        policy = asyncio.WindowsSelectorEventLoopPolicy()
        asyncio.set_event_loop_policy(policy)
        loop = policy.new_event_loop()
    else:
        loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def db_available() -> bool:
    """Check if PostgreSQL database is available."""
    try:
        url = get_database_url()
        with psycopg.connect(url, connect_timeout=3) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1;")
                return True
    except Exception:
        return False


@pytest_asyncio.fixture(scope="session")
async def isolated_schema(db_available: bool) -> AsyncGenerator[str, None]:
    """Create an isolated PostgreSQL schema for the entire test session."""
    if not db_available:
        pytest.skip("PostgreSQL is unavailable in the environment.")

    url = get_database_url()
    schema_name = f"test_notes_{uuid.uuid4().hex[:8]}"

    # Synchronously setup isolated test schema and run migration
    with psycopg.connect(url, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(f"CREATE SCHEMA {schema_name};")
            cur.execute(f"SET search_path TO {schema_name};")
            migration_sql = MIGRATION_PATH.read_text(encoding="utf-8")
            cur.execute(migration_sql)

    # Initialize async connection pool targeting the isolated schema
    test_pool = AsyncConnectionPool(
        conninfo=url,
        min_size=1,
        max_size=5,
        timeout=10.0,
        open=False,
        kwargs={
            "row_factory": dict_row,
            "options": f"-c search_path={schema_name}",
        },
    )
    await test_pool.open(wait=True)
    db_manager._pool = test_pool

    yield schema_name

    # Teardown: close pool and drop schema
    await test_pool.close()
    db_manager._pool = None

    with psycopg.connect(url, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(f"DROP SCHEMA IF EXISTS {schema_name} CASCADE;")


@pytest_asyncio.fixture
async def test_conn(isolated_schema: str) -> AsyncGenerator[psycopg.AsyncConnection, None]:
    """Yield an async connection from the isolated test pool."""
    async with db_manager.connection() as conn:
        yield conn

