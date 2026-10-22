"""PostgreSQL asynchronous connection pool management for Notes MCP Server.

Provides robust connection pooling, connection timeouts, dictionary row mapping,
and graceful resource cleanup.
"""

from __future__ import annotations

import asyncio
import logging
import sys
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool, PoolTimeout

from notes_server.config import get_masked_db_url, get_settings
from notes_server.exceptions import DatabaseConnectionError, DatabaseQueryError

logger = logging.getLogger("notes_server.database")


class DatabaseManager:
    """Manages the lifecycle of the PostgreSQL AsyncConnectionPool."""

    def __init__(self) -> None:
        self._pool: Optional[AsyncConnectionPool] = None
        self._lock = asyncio.Lock()

    async def get_pool(self) -> AsyncConnectionPool:
        """Get or initialize the singleton AsyncConnectionPool."""
        if self._pool is not None and not self._pool.closed:
            return self._pool

        async with self._lock:
            if self._pool is not None and not self._pool.closed:
                return self._pool

            settings = get_settings()
            try:
                logger.info(
                    "Initializing PostgreSQL connection pool (%s, min=%d, max=%d)...",
                    get_masked_db_url(),
                    settings.pool_min_size,
                    settings.pool_max_size,
                )
                self._pool = AsyncConnectionPool(
                    conninfo=settings.database_url,
                    min_size=settings.pool_min_size,
                    max_size=settings.pool_max_size,
                    timeout=settings.timeout_seconds,
                    open=False,
                    kwargs={"row_factory": dict_row},
                )
                await self._pool.open(wait=False)
                await self._pool.wait(timeout=settings.timeout_seconds)
                logger.info("PostgreSQL connection pool opened successfully.")
                return self._pool
            except (psycopg.OperationalError, PoolTimeout) as exc:
                logger.error("Failed to connect to PostgreSQL: %s", exc)
                raise DatabaseConnectionError(
                    f"Could not connect to PostgreSQL database ({get_masked_db_url()}). "
                    "Ensure PostgreSQL is running and credentials in .env are valid."
                ) from exc
            except Exception as exc:
                logger.error("Unexpected error initializing PostgreSQL pool: %s", exc)
                raise DatabaseConnectionError(f"Database pool initialization error: {exc}") from exc

    async def close(self) -> None:
        """Close connection pool cleanly."""
        async with self._lock:
            if self._pool is not None and not self._pool.closed:
                logger.info("Closing PostgreSQL connection pool...")
                await self._pool.close()
                self._pool = None
                logger.info("PostgreSQL connection pool closed.")

    @asynccontextmanager
    async def connection(self) -> AsyncGenerator[psycopg.AsyncConnection, None]:
        """Async context manager for acquiring a connection from the pool."""
        pool = await self.get_pool()
        try:
            async with pool.connection() as conn:
                yield conn
        except PoolTimeout as exc:
            logger.error("Database connection acquisition timed out.")
            raise DatabaseConnectionError(
                "Timed out waiting for an available PostgreSQL connection from the pool."
            ) from exc
        except psycopg.OperationalError as exc:
            logger.error("PostgreSQL operational error: %s", exc)
            raise DatabaseConnectionError("PostgreSQL operational error encountered.") from exc
        except psycopg.Error as exc:
            logger.error("PostgreSQL error: %s", exc)
            raise DatabaseQueryError(f"Database error: {exc.pgcode or 'Unknown code'}") from exc

    async def check_health(self) -> bool:
        """Verify database connectivity with a lightweight ping."""
        try:
            async with self.connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute("SELECT 1;")
                    row = await cur.fetchone()
                    return row is not None
        except Exception as exc:
            logger.warning("Database health check failed: %s", exc)
            return False


# Singleton manager instance
db_manager = DatabaseManager()
