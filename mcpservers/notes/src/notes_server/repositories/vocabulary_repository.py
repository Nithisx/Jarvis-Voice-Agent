"""Repository for vocabulary and spaced-repetition operations in PostgreSQL."""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional
from uuid import UUID
from zoneinfo import ZoneInfo

import psycopg
from psycopg.types.json import Jsonb

from notes_server.exceptions import RecordNotFoundError, ValidationError
from notes_server.schemas import serialize_db_record


def calculate_next_review(
    current_interval_days: float,
    rating: int,
    now: datetime,
) -> tuple[float, datetime]:
    """Deterministic spaced-repetition algorithm.

    Rating Scale:
    - 0: Forgot completely -> retry after short delay (10 minutes).
    - 1: Remembered with substantial difficulty -> schedule review in 1 day.
    - 2: Remembered with some effort -> moderately increase interval (min 3 days).
    - 3: Remembered easily -> substantially increase interval (min 7 days).
    """
    if rating == 0:
        # 10 minutes delay, interval unchanged for future baseline
        next_review_at = now + timedelta(minutes=10)
        new_interval = max(0.1, current_interval_days)
    elif rating == 1:
        # Reset to 1 day
        new_interval = 1.0
        next_review_at = now + timedelta(days=1)
    elif rating == 2:
        # Moderate increase
        new_interval = max(3.0, round(current_interval_days * 2.0, 1))
        next_review_at = now + timedelta(days=new_interval)
    elif rating == 3:
        # Substantial increase
        new_interval = max(7.0, round(current_interval_days * 2.5, 1))
        next_review_at = now + timedelta(days=new_interval)
    else:
        raise ValidationError(f"Rating must be between 0 and 3, received {rating}.")

    return new_interval, next_review_at


class VocabularyRepository:
    """Handles vocabulary and spaced-repetition reviews."""

    @staticmethod
    async def save_vocabulary(
        conn: psycopg.AsyncConnection,
        word: str,
        meaning: str,
        example_sentence: Optional[str] = None,
        synonyms: Optional[list[str]] = None,
        word_type: Optional[str] = None,
        pronunciation: Optional[str] = None,
        source_context: Optional[str] = None,
        difficulty: Optional[str] = None,
        learned_at: Optional[datetime] = None,
    ) -> dict[str, Any]:
        """Save a vocabulary entry with duplicate detection."""
        if not word or not word.strip():
            raise ValidationError("Vocabulary word must not be empty or whitespace only.")
        if not meaning or not meaning.strip():
            raise ValidationError("Vocabulary meaning must not be empty or whitespace only.")
        if difficulty is not None and difficulty not in ("beginner", "intermediate", "advanced"):
            raise ValidationError(f"Invalid difficulty '{difficulty}'.")

        clean_word = word.strip()
        normalized_word = clean_word.lower()
        clean_synonyms = synonyms or []
        effective_learned_at = learned_at or datetime.now(timezone.utc)

        async with conn.cursor() as cur:
            # Check for existing active vocabulary
            check_sql = """
                SELECT * FROM vocabulary 
                WHERE normalized_word = %s AND archived_at IS NULL;
            """
            await cur.execute(check_sql, (normalized_word,))
            existing = await cur.fetchone()

            if existing:
                return {
                    "is_duplicate": True,
                    "id": str(existing["id"]),
                    "message": f"Vocabulary entry '{clean_word}' already exists with ID {existing['id']}.",
                    "existing_record": serialize_db_record(existing),
                }

            # Insert new record; first review scheduled in 1 day
            insert_sql = """
                INSERT INTO vocabulary (
                    word, normalized_word, meaning, example_sentence, synonyms,
                    word_type, pronunciation, source_context, difficulty, learned_at,
                    review_interval_days, next_review_at, created_at, updated_at
                )
                VALUES (
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s,
                    1.0, CURRENT_TIMESTAMP + INTERVAL '1 day',
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                )
                RETURNING *;
            """
            await cur.execute(
                insert_sql,
                (
                    clean_word,
                    normalized_word,
                    meaning.strip(),
                    example_sentence,
                    Jsonb(clean_synonyms),
                    word_type,
                    pronunciation,
                    source_context,
                    difficulty,
                    effective_learned_at,
                ),
            )
            created = await cur.fetchone()
            await conn.commit()
            return {
                "is_duplicate": False,
                "id": str(created["id"]),
                "saved_record": serialize_db_record(created),
            }

    @staticmethod
    async def get_vocabulary_by_id(
        conn: psycopg.AsyncConnection,
        vocab_id: str | UUID,
    ) -> dict[str, Any]:
        """Retrieve vocabulary by UUID."""
        try:
            uuid_obj = UUID(str(vocab_id))
        except ValueError as exc:
            raise ValidationError(f"Invalid UUID string format: '{vocab_id}'") from exc

        sql = "SELECT * FROM vocabulary WHERE id = %s;"
        async with conn.cursor() as cur:
            await cur.execute(sql, (uuid_obj,))
            row = await cur.fetchone()
            if not row:
                raise RecordNotFoundError(f"Vocabulary entry with ID '{vocab_id}' not found.")
            return serialize_db_record(row)  # type: ignore[return-value]

    @staticmethod
    async def search_vocabulary(
        conn: psycopg.AsyncConnection,
        query: Optional[str] = None,
        difficulty: Optional[str] = None,
        word_type: Optional[str] = None,
        include_archived: bool = False,
        limit: int = 20,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """Search vocabulary entries across words, definitions, synonyms, or context."""
        limit = max(1, min(limit, 100))
        offset = max(0, offset)
        conditions = ["1=1"]
        params: list[Any] = []

        if not include_archived:
            conditions.append("archived_at IS NULL")

        if difficulty:
            conditions.append("difficulty = %s")
            params.append(difficulty)

        if word_type:
            conditions.append("word_type = %s")
            params.append(word_type)

        if query and query.strip():
            clean_q = query.strip()
            like_pattern = f"%{clean_q}%"
            conditions.append(
                "("
                "to_tsvector('english', coalesce(word, '') || ' ' || coalesce(meaning, '')) @@ plainto_tsquery('english', %s) "
                "OR word ILIKE %s "
                "OR meaning ILIKE %s "
                "OR source_context ILIKE %s "
                "OR synonyms::text ILIKE %s"
                ")"
            )
            params.extend([clean_q, like_pattern, like_pattern, like_pattern, like_pattern])

        where_clause = " AND ".join(conditions)
        sql = f"""
            SELECT * FROM vocabulary 
            WHERE {where_clause} 
            ORDER BY created_at DESC 
            LIMIT %s OFFSET %s;
        """
        params.extend([limit, offset])

        async with conn.cursor() as cur:
            await cur.execute(sql, params)
            rows = await cur.fetchall()
            return [serialize_db_record(r) for r in rows if r]  # type: ignore[misc]

    @staticmethod
    async def get_due_reviews(
        conn: psycopg.AsyncConnection,
        limit: int = 10,
        category: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """Retrieve items ready for revision, formatted for active recall.

        Prioritizes overdue items first, then items due soon.
        Does NOT automatically reveal answers/meanings to preserve recall testing.
        """
        limit = max(1, min(limit, 50))
        now = datetime.now(timezone.utc)

        # 1. Fetch vocabulary reviews
        vocab_sql = """
            SELECT id, word, word_type, pronunciation, source_context, difficulty,
                   next_review_at, review_count, last_reviewed_at
            FROM vocabulary
            WHERE archived_at IS NULL 
              AND next_review_at <= (CURRENT_TIMESTAMP + INTERVAL '6 hours')
            ORDER BY next_review_at ASC
            LIMIT %s;
        """
        
        # 2. Fetch notes reviews (if notes have next_review_at set)
        note_cond = "archived_at IS NULL AND next_review_at IS NOT NULL AND next_review_at <= (CURRENT_TIMESTAMP + INTERVAL '6 hours')"
        note_params: list[Any] = []
        if category:
            note_cond += " AND category = %s"
            note_params.append(category)

        note_sql = f"""
            SELECT id, title, category, source, example,
                   next_review_at, review_count, last_reviewed_at
            FROM notes
            WHERE {note_cond}
            ORDER BY next_review_at ASC
            LIMIT %s;
        """
        note_params.append(limit)

        prompts: list[dict[str, Any]] = []

        async with conn.cursor() as cur:
            await cur.execute(vocab_sql, (limit,))
            vocab_rows = await cur.fetchall()

            for r in vocab_rows:
                is_overdue = r["next_review_at"] is not None and r["next_review_at"] <= now
                prompts.append({
                    "item_id": str(r["id"]),
                    "item_type": "vocabulary",
                    "prompt": f"What is the definition and usage of: '{r['word']}'?",
                    "word": r["word"],
                    "word_type": r["word_type"],
                    "pronunciation": r["pronunciation"],
                    "source_context": r["source_context"],
                    "difficulty": r["difficulty"],
                    "review_count": r["review_count"],
                    "due_status": "overdue" if is_overdue else "due_today",
                    "next_review_at": r["next_review_at"].isoformat() if r["next_review_at"] else None,
                })

            await cur.execute(note_sql, note_params)
            note_rows = await cur.fetchall()

            for r in note_rows:
                is_overdue = r["next_review_at"] is not None and r["next_review_at"] <= now
                prompts.append({
                    "item_id": str(r["id"]),
                    "item_type": "note",
                    "prompt": f"Active Recall: Recite or summarize note '{r['title']}'",
                    "title": r["title"],
                    "category": r["category"],
                    "source": r["source"],
                    "example": r["example"],
                    "review_count": r["review_count"],
                    "due_status": "overdue" if is_overdue else "due_today",
                    "next_review_at": r["next_review_at"].isoformat() if r["next_review_at"] else None,
                })

        # Sort combined results: overdue first, then by next_review_at ascending
        prompts.sort(key=lambda x: (x["due_status"] != "overdue", x.get("next_review_at") or ""))
        return prompts[:limit]

    @staticmethod
    async def submit_review(
        conn: psycopg.AsyncConnection,
        item_id: str | UUID,
        rating: int,
        response_text: Optional[str] = None,
        feedback_notes: Optional[str] = None,
    ) -> dict[str, Any]:
        """Record review outcome and update spacing schedule in an atomic transaction."""
        try:
            uuid_obj = UUID(str(item_id))
        except ValueError as exc:
            raise ValidationError(f"Invalid UUID string format: '{item_id}'") from exc

        if rating not in (0, 1, 2, 3):
            raise ValidationError(f"Rating must be 0, 1, 2, or 3. Received {rating}.")

        now = datetime.now(timezone.utc)

        # Atomic transaction
        async with conn.transaction():
            async with conn.cursor() as cur:
                # 1. Determine whether item is vocabulary or note
                await cur.execute(
                    "SELECT id, review_interval_days, review_count, self_assessed_mastery "
                    "FROM vocabulary WHERE id = %s AND archived_at IS NULL FOR UPDATE;",
                    (uuid_obj,),
                )
                vocab_item = await cur.fetchone()

                item_type = "vocabulary"
                target_table = "vocabulary"
                item = vocab_item

                if not item:
                    await cur.execute(
                        "SELECT id, review_interval_days, review_count, self_assessed_mastery "
                        "FROM notes WHERE id = %s AND archived_at IS NULL FOR UPDATE;",
                        (uuid_obj,),
                    )
                    note_item = await cur.fetchone()
                    if note_item:
                        item_type = "note"
                        target_table = "notes"
                        item = note_item
                    else:
                        raise RecordNotFoundError(
                            f"Active vocabulary or note with ID '{item_id}' not found."
                        )

                # 2. Calculate next review interval and mastery
                current_interval = float(item["review_interval_days"] or 1.0)
                new_interval, next_review_at = calculate_next_review(current_interval, rating, now)

                old_count = int(item["review_count"] or 0)
                new_count = old_count + 1

                # Weighted moving average for self-assessed mastery (0 - 100 scale)
                current_score = (rating / 3.0) * 100.0
                old_mastery = float(item["self_assessed_mastery"] or current_score)
                new_mastery = round((old_mastery * old_count + current_score) / new_count, 1)

                # 3. Update the target table
                update_sql = f"""
                    UPDATE {target_table}
                    SET review_interval_days = %s,
                        next_review_at = %s,
                        last_reviewed_at = %s,
                        review_count = %s,
                        self_assessed_mastery = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                    RETURNING *;
                """
                await cur.execute(
                    update_sql,
                    (new_interval, next_review_at, now, new_count, new_mastery, uuid_obj),
                )
                updated_row = await cur.fetchone()

                # 4. Insert into review_history log
                log_sql = """
                    INSERT INTO review_history (
                        item_type, item_id, rating, response_text, feedback_notes,
                        reviewed_at, next_review_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING id;
                """
                await cur.execute(
                    log_sql,
                    (
                        item_type,
                        uuid_obj,
                        rating,
                        response_text,
                        feedback_notes,
                        now,
                        next_review_at,
                    ),
                )
                history_row = await cur.fetchone()

                rating_labels = {
                    0: "Forgot completely (Retry in 10 minutes)",
                    1: "Remembered with substantial difficulty (Review in 1 day)",
                    2: "Remembered with some effort (Interval increased)",
                    3: "Remembered easily (Interval substantially increased)",
                }

                return {
                    "review_id": str(history_row["id"]),
                    "item_id": str(uuid_obj),
                    "item_type": item_type,
                    "rating": rating,
                    "rating_description": rating_labels[rating],
                    "new_interval_days": new_interval,
                    "next_review_at": next_review_at.isoformat(),
                    "total_reviews": new_count,
                    "self_assessed_mastery_percent": new_mastery,
                    "assessment_nature": "Subjective self-assessment (not objectively verified correctness)",
                    "updated_item": serialize_db_record(updated_row),
                }

    @staticmethod
    async def get_daily_summary(
        conn: psycopg.AsyncConnection,
        target_date_str: Optional[str] = None,
        tz_name: str = "Asia/Kolkata",
    ) -> dict[str, Any]:
        """Aggregate notes and vocabulary learned on a given local calendar date."""
        try:
            tz = ZoneInfo(tz_name)
        except Exception:
            tz = ZoneInfo("UTC")

        if target_date_str:
            try:
                target_date = datetime.strptime(target_date_str, "%Y-%m-%d").date()
            except ValueError as exc:
                raise ValidationError(f"Invalid date format '{target_date_str}'. Expected YYYY-MM-DD.") from exc
        else:
            target_date = datetime.now(tz).date()

        # Compute UTC start and end bounds for the local calendar date
        start_local = datetime.combine(target_date, datetime.min.time(), tzinfo=tz)
        end_local = datetime.combine(target_date, datetime.max.time(), tzinfo=tz)
        start_utc = start_local.astimezone(timezone.utc)
        end_utc = end_local.astimezone(timezone.utc)

        async with conn.cursor() as cur:
            # Fetch notes learned on date
            notes_sql = """
                SELECT * FROM notes 
                WHERE learned_at >= %s AND learned_at <= %s AND archived_at IS NULL
                ORDER BY created_at ASC;
            """
            await cur.execute(notes_sql, (start_utc, end_utc))
            notes = [serialize_db_record(r) for r in await cur.fetchall()]

            # Fetch vocabulary learned on date
            vocab_sql = """
                SELECT * FROM vocabulary 
                WHERE learned_at >= %s AND learned_at <= %s AND archived_at IS NULL
                ORDER BY created_at ASC;
            """
            await cur.execute(vocab_sql, (start_utc, end_utc))
            vocab = [serialize_db_record(r) for r in await cur.fetchall()]

            # Fetch reviews conducted on date
            reviews_sql = """
                SELECT COUNT(*) as count, AVG(rating) as avg_rating
                FROM review_history
                WHERE reviewed_at >= %s AND reviewed_at <= %s;
            """
            await cur.execute(reviews_sql, (start_utc, end_utc))
            review_summary = await cur.fetchone()

            # Group notes by category
            notes_by_category: dict[str, list[dict[str, Any]]] = {}
            for note in notes:
                cat = note.get("category", "general")
                notes_by_category.setdefault(cat, []).append(note)

            return {
                "date": target_date.isoformat(),
                "timezone": tz_name,
                "utc_bounds": {
                    "start": start_utc.isoformat(),
                    "end": end_utc.isoformat(),
                },
                "total_notes_learned": len(notes),
                "total_vocabulary_learned": len(vocab),
                "notes_by_category": notes_by_category,
                "vocabulary": vocab,
                "reviews_completed": review_summary["count"] if review_summary else 0,
                "average_recall_score": round(float(review_summary["avg_rating"]), 2) if review_summary and review_summary["avg_rating"] is not None else None,
            }

    @staticmethod
    async def get_learning_stats(
        conn: psycopg.AsyncConnection,
    ) -> dict[str, Any]:
        """Aggregate high-level learning statistics and self-reported recall trends."""
        now = datetime.now(timezone.utc)

        async with conn.cursor() as cur:
            # 1. Total notes
            await cur.execute("""
                SELECT 
                    COUNT(*) as total,
                    COUNT(*) FILTER (WHERE archived_at IS NULL) as active,
                    COUNT(*) FILTER (WHERE archived_at IS NOT NULL) as archived
                FROM notes;
            """)
            notes_counts = await cur.fetchone()

            # 2. Total vocabulary
            await cur.execute("""
                SELECT 
                    COUNT(*) as total,
                    COUNT(*) FILTER (WHERE archived_at IS NULL) as active,
                    COUNT(*) FILTER (WHERE archived_at IS NOT NULL) as archived
                FROM vocabulary;
            """)
            vocab_counts = await cur.fetchone()

            # 3. Total reviews
            await cur.execute("SELECT COUNT(*) as total FROM review_history;")
            review_total = await cur.fetchone()

            # 4. Due reviews today and overdue
            await cur.execute("""
                SELECT 
                    COUNT(*) FILTER (WHERE next_review_at <= CURRENT_TIMESTAMP) as overdue,
                    COUNT(*) FILTER (WHERE next_review_at > CURRENT_TIMESTAMP AND next_review_at <= CURRENT_TIMESTAMP + INTERVAL '1 day') as due_today
                FROM vocabulary
                WHERE archived_at IS NULL;
            """)
            vocab_due = await cur.fetchone()

            # 5. Recall ratings breakdown (self-assessed)
            await cur.execute("""
                SELECT 
                    rating,
                    COUNT(*) as count
                FROM review_history
                GROUP BY rating
                ORDER BY rating ASC;
            """)
            rating_rows = await cur.fetchall()
            rating_counts = {r["rating"]: r["count"] for r in rating_rows}

            # 6. Recent learning activity (last 7 days)
            await cur.execute("""
                SELECT 
                    COUNT(*) as new_notes
                FROM notes 
                WHERE learned_at >= CURRENT_TIMESTAMP - INTERVAL '7 days' AND archived_at IS NULL;
            """)
            recent_notes = await cur.fetchone()

            await cur.execute("""
                SELECT 
                    COUNT(*) as new_vocab
                FROM vocabulary 
                WHERE learned_at >= CURRENT_TIMESTAMP - INTERVAL '7 days' AND archived_at IS NULL;
            """)
            recent_vocab = await cur.fetchone()

            return {
                "notes": {
                    "total": notes_counts["total"] if notes_counts else 0,
                    "active": notes_counts["active"] if notes_counts else 0,
                    "archived": notes_counts["archived"] if notes_counts else 0,
                },
                "vocabulary": {
                    "total": vocab_counts["total"] if vocab_counts else 0,
                    "active": vocab_counts["active"] if vocab_counts else 0,
                    "archived": vocab_counts["archived"] if vocab_counts else 0,
                },
                "reviews": {
                    "total_attempts": review_total["total"] if review_total else 0,
                    "overdue": vocab_due["overdue"] if vocab_due else 0,
                    "due_next_24_hours": vocab_due["due_today"] if vocab_due else 0,
                },
                "past_7_days_activity": {
                    "new_notes": recent_notes["new_notes"] if recent_notes else 0,
                    "new_vocabulary": recent_vocab["new_vocab"] if recent_vocab else 0,
                },
                "self_reported_recall_distribution": {
                    "rating_0_forgot": rating_counts.get(0, 0),
                    "rating_1_hard": rating_counts.get(1, 0),
                    "rating_2_good": rating_counts.get(2, 0),
                    "rating_3_easy": rating_counts.get(3, 0),
                    "note": "Metrics reflect user self-assessment and active recall practice, not objectively verified tests.",
                },
            }
