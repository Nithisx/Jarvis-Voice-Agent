"""Repository for persistent note operations in PostgreSQL."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

import psycopg
from psycopg.types.json import Jsonb

from notes_server.exceptions import RecordNotFoundError, ValidationError
from notes_server.schemas import serialize_db_record


class NotesRepository:
    """Handles note CRUD and search operations with parameterized SQL."""

    @staticmethod
    async def create_note(
        conn: psycopg.AsyncConnection,
        title: str,
        content: str,
        category: str,
        tags: list[str] | None = None,
        source: str | None = None,
        example: str | None = None,
        learned_at: datetime | None = None,
    ) -> dict[str, Any]:
        """Insert a new note record."""
        if not title or not title.strip():
            raise ValidationError("Note title must not be empty or whitespace only.")
        if not content or not content.strip():
            raise ValidationError("Note content must not be empty or whitespace only.")
        valid_categories = {
            "general", "communication", "grammar", "vocabulary",
            "story", "technical", "personal_reflection"
        }
        if category not in valid_categories:
            raise ValidationError(f"Invalid category '{category}'.")

        clean_tags = tags or []
        effective_learned_at = learned_at or datetime.now(timezone.utc)

        sql = """
            INSERT INTO notes (
                title, content, category, tags, source, example, learned_at,
                created_at, updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            RETURNING *;
        """
        async with conn.cursor() as cur:
            await cur.execute(
                sql,
                (
                    title,
                    content,
                    category,
                    clean_tags,
                    source,
                    example,
                    effective_learned_at,
                ),
            )
            row = await cur.fetchone()
            await conn.commit()
            return serialize_db_record(row)  # type: ignore[return-value]

    @staticmethod
    async def get_note_by_id(
        conn: psycopg.AsyncConnection,
        note_id: str | UUID,
    ) -> dict[str, Any]:
        """Fetch a single note by UUID."""
        try:
            uuid_obj = UUID(str(note_id))
        except ValueError as exc:
            raise ValidationError(f"Invalid UUID string format: '{note_id}'") from exc

        sql = "SELECT * FROM notes WHERE id = %s;"
        async with conn.cursor() as cur:
            await cur.execute(sql, (uuid_obj,))
            row = await cur.fetchone()
            if not row:
                raise RecordNotFoundError(f"Note with ID '{note_id}' not found.")
            return serialize_db_record(row)  # type: ignore[return-value]

    @staticmethod
    async def search_notes(
        conn: psycopg.AsyncConnection,
        query: Optional[str] = None,
        category: Optional[str] = None,
        tags: Optional[list[str]] = None,
        include_archived: bool = False,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Search notes using full-text search, category, and tag filters."""
        limit = max(1, min(limit, 100))
        conditions = ["1=1"]
        params: list[Any] = []

        if not include_archived:
            conditions.append("archived_at IS NULL")

        if category:
            conditions.append("category = %s")
            params.append(category)

        if tags:
            clean_tags = [t.strip().lower() for t in tags if t.strip()]
            if clean_tags:
                conditions.append("tags && %s::text[]")
                params.append(clean_tags)

        order_by = "created_at DESC"
        if query and query.strip():
            clean_q = query.strip()
            like_pattern = f"%{clean_q}%"
            conditions.append(
                "("
                "to_tsvector('english', coalesce(title, '') || ' ' || coalesce(content, '')) @@ plainto_tsquery('english', %s) "
                "OR title ILIKE %s "
                "OR content ILIKE %s"
                ")"
            )
            params.extend([clean_q, like_pattern, like_pattern])
            order_by = (
                "ts_rank(to_tsvector('english', coalesce(title, '') || ' ' || coalesce(content, '')), "
                "plainto_tsquery('english', %s)) DESC, created_at DESC"
            )

        where_clause = " AND ".join(conditions)
        if query and query.strip():
            # Add plain_q parameter for ts_rank in order_by
            sql = f"SELECT * FROM notes WHERE {where_clause} ORDER BY {order_by} LIMIT %s;"
            query_params = params + [clean_q, limit]
        else:
            sql = f"SELECT * FROM notes WHERE {where_clause} ORDER BY {order_by} LIMIT %s;"
            query_params = params + [limit]

        async with conn.cursor() as cur:
            await cur.execute(sql, query_params)
            rows = await cur.fetchall()
            return [serialize_db_record(r) for r in rows if r]  # type: ignore[misc]

    @staticmethod
    async def update_note(
        conn: psycopg.AsyncConnection,
        note_id: str | UUID,
        title: Optional[str] = None,
        content: Optional[str] = None,
        category: Optional[str] = None,
        tags: Optional[list[str]] = None,
        source: Optional[str] = None,
        example: Optional[str] = None,
    ) -> dict[str, Any]:
        """Update explicitly provided fields on an active note."""
        try:
            uuid_obj = UUID(str(note_id))
        except ValueError as exc:
            raise ValidationError(f"Invalid UUID string format: '{note_id}'") from exc

        set_clauses: list[str] = []
        params: list[Any] = []

        if title is not None:
            set_clauses.append("title = %s")
            params.append(title)
        if content is not None:
            set_clauses.append("content = %s")
            params.append(content)
        if category is not None:
            set_clauses.append("category = %s")
            params.append(category)
        if tags is not None:
            clean_tags = [t.strip().lower() for t in tags if t.strip()]
            set_clauses.append("tags = %s")
            params.append(clean_tags)
        if source is not None:
            set_clauses.append("source = %s")
            params.append(source)
        if example is not None:
            set_clauses.append("example = %s")
            params.append(example)

        if not set_clauses:
            # Nothing to update; retrieve current record
            return await NotesRepository.get_note_by_id(conn, uuid_obj)

        set_clauses.append("updated_at = CURRENT_TIMESTAMP")
        set_sql = ", ".join(set_clauses)
        params.append(uuid_obj)

        sql = f"""
            UPDATE notes
            SET {set_sql}
            WHERE id = %s AND archived_at IS NULL
            RETURNING *;
        """
        async with conn.cursor() as cur:
            await cur.execute(sql, params)
            row = await cur.fetchone()
            if not row:
                # Check whether note exists but is archived, or doesn't exist at all
                await cur.execute("SELECT id, archived_at FROM notes WHERE id = %s;", (uuid_obj,))
                check = await cur.fetchone()
                if not check:
                    raise RecordNotFoundError(f"Note with ID '{note_id}' does not exist.")
                raise ValidationError(f"Cannot update archived note with ID '{note_id}'.")
            await conn.commit()
            return serialize_db_record(row)  # type: ignore[return-value]

    @staticmethod
    async def archive_note(
        conn: psycopg.AsyncConnection,
        note_id: str | UUID,
    ) -> dict[str, Any]:
        """Soft-archive a note by setting its archived_at timestamp."""
        try:
            uuid_obj = UUID(str(note_id))
        except ValueError as exc:
            raise ValidationError(f"Invalid UUID string format: '{note_id}'") from exc

        sql = """
            UPDATE notes
            SET archived_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s AND archived_at IS NULL
            RETURNING *;
        """
        async with conn.cursor() as cur:
            await cur.execute(sql, (uuid_obj,))
            row = await cur.fetchone()
            if not row:
                await cur.execute("SELECT id, archived_at FROM notes WHERE id = %s;", (uuid_obj,))
                check = await cur.fetchone()
                if not check:
                    raise RecordNotFoundError(f"Note with ID '{note_id}' does not exist.")
                # Already archived
                return await NotesRepository.get_note_by_id(conn, uuid_obj)
            await conn.commit()
            return serialize_db_record(row)  # type: ignore[return-value]
