"""Tests for spaced-repetition reviews, active recall, daily summaries, and stats."""

from __future__ import annotations

import uuid
import pytest
from datetime import datetime, timedelta, timezone

from notes_server.exceptions import ValidationError
from notes_server.repositories.notes_repository import NotesRepository
from notes_server.repositories.vocabulary_repository import (
    VocabularyRepository,
    calculate_next_review,
)


def test_calculate_next_review_algorithm():
    """Verify deterministic spacing intervals for ratings 0 through 3."""
    now = datetime(2026, 10, 21, 12, 0, 0, tzinfo=timezone.utc)

    # Rating 0: Forgot -> 10 minutes delay
    int_0, next_0 = calculate_next_review(current_interval_days=5.0, rating=0, now=now)
    assert int_0 == 5.0
    assert next_0 == now + timedelta(minutes=10)

    # Rating 1: Hard -> 1 day interval
    int_1, next_1 = calculate_next_review(current_interval_days=5.0, rating=1, now=now)
    assert int_1 == 1.0
    assert next_1 == now + timedelta(days=1)

    # Rating 2: Good -> Moderate increase (max 3 days or 2.0x)
    int_2, next_2 = calculate_next_review(current_interval_days=2.0, rating=2, now=now)
    assert int_2 == 4.0
    assert next_2 == now + timedelta(days=4)

    # Rating 3: Easy -> Substantial increase (max 7 days or 2.5x)
    int_3, next_3 = calculate_next_review(current_interval_days=4.0, rating=3, now=now)
    assert int_3 == 10.0
    assert next_3 == now + timedelta(days=10)

    # Invalid rating
    with pytest.raises(ValidationError):
        calculate_next_review(current_interval_days=1.0, rating=4, now=now)


@pytest.mark.asyncio
async def test_get_due_reviews_active_recall(test_conn):
    """Verify due reviews do NOT reveal definitions to ensure active recall."""
    word = f"recondite_{uuid.uuid4().hex[:4]}"
    res = await VocabularyRepository.save_vocabulary(
        conn=test_conn,
        word=word,
        meaning="Little known; abstruse.",
        source_context="Reading philosophy books",
    )
    vocab_id = res["id"]

    # Force item to be overdue
    past_due = datetime.now(timezone.utc) - timedelta(hours=2)
    async with test_conn.cursor() as cur:
        await cur.execute(
            "UPDATE vocabulary SET next_review_at = %s WHERE id = %s;",
            (past_due, uuid.UUID(vocab_id)),
        )
        await test_conn.commit()

    due_reviews = await VocabularyRepository.get_due_reviews(test_conn, limit=10)
    matching = [r for r in due_reviews if r["item_id"] == vocab_id]

    assert len(matching) == 1
    item = matching[0]
    assert item["word"] == word
    assert item["due_status"] == "overdue"
    # Crucial: meaning must NOT be exposed in the active recall prompt
    assert "meaning" not in item
    assert "abstruse" not in str(item.values())


@pytest.mark.asyncio
async def test_submit_review_transaction_and_history(test_conn):
    """Verify submit_review persists review history and updates interval atomically."""
    word = f"ubiquitous_{uuid.uuid4().hex[:4]}"
    res = await VocabularyRepository.save_vocabulary(
        conn=test_conn,
        word=word,
        meaning="Present, appearing, or found everywhere.",
    )
    vocab_id = res["id"]

    # Submit rating 3 (Easy)
    review_res = await VocabularyRepository.submit_review(
        conn=test_conn,
        item_id=vocab_id,
        rating=3,
        response_text="Found everywhere",
        feedback_notes="Remembered immediately.",
    )

    assert review_res["rating"] == 3
    assert review_res["new_interval_days"] >= 7.0
    assert review_res["total_reviews"] == 1
    assert "Subjective self-assessment" in review_res["assessment_nature"]

    # Verify review history was inserted in database
    async with test_conn.cursor() as cur:
        await cur.execute(
            "SELECT * FROM review_history WHERE item_id = %s;",
            (uuid.UUID(vocab_id),),
        )
        history_rows = await cur.fetchall()
        assert len(history_rows) == 1
        assert history_rows[0]["rating"] == 3
        assert history_rows[0]["response_text"] == "Found everywhere"


@pytest.mark.asyncio
async def test_daily_summary_and_timezone(test_conn):
    """Verify get_daily_summary aggregates items in local calendar timezone."""
    now_utc = datetime.now(timezone.utc)
    note = await NotesRepository.create_note(
        conn=test_conn,
        title="Timezone Handling Note",
        content="Testing calendar day partitioning with IANA timezones.",
        category="technical",
        learned_at=now_utc,
    )
    vocab = await VocabularyRepository.save_vocabulary(
        conn=test_conn,
        word=f"chronos_{uuid.uuid4().hex[:4]}",
        meaning="Time in Greek mythology.",
        learned_at=now_utc,
    )

    summary = await VocabularyRepository.get_daily_summary(
        conn=test_conn,
        tz_name="Asia/Kolkata",
    )

    assert summary["timezone"] == "Asia/Kolkata"
    assert summary["total_notes_learned"] >= 1
    assert "technical" in summary["notes_by_category"]
    assert any(n["id"] == note["id"] for n in summary["notes_by_category"]["technical"])
    assert any(v["id"] == vocab["id"] for v in summary["vocabulary"])


@pytest.mark.asyncio
async def test_get_learning_stats(test_conn):
    """Verify learning statistics output structure."""
    stats = await VocabularyRepository.get_learning_stats(test_conn)

    assert "notes" in stats
    assert "vocabulary" in stats
    assert "reviews" in stats
    assert "self_reported_recall_distribution" in stats
    assert "total" in stats["notes"]
    assert "total" in stats["vocabulary"]


@pytest.mark.asyncio
async def test_submit_review_transaction_rollback_on_error(test_conn):
    """Verify transaction rolls back cleanly if an error occurs."""
    word = f"rollback_{uuid.uuid4().hex[:4]}"
    res = await VocabularyRepository.save_vocabulary(
        conn=test_conn,
        word=word,
        meaning="Testing atomic transaction rollback.",
    )
    vocab_id = res["id"]

    # Attempt to submit review with an invalid rating that fails Python or DB constraint
    with pytest.raises(ValidationError):
        await VocabularyRepository.submit_review(
            conn=test_conn,
            item_id=vocab_id,
            rating=99,  # Invalid rating
        )

    # Verify no history record was written
    async with test_conn.cursor() as cur:
        await cur.execute(
            "SELECT COUNT(*) as count FROM review_history WHERE item_id = %s;",
            (uuid.UUID(vocab_id),),
        )
        row = await cur.fetchone()
        assert row["count"] == 0

        # Verify interval was not modified
        await cur.execute(
            "SELECT review_interval_days, review_count FROM vocabulary WHERE id = %s;",
            (uuid.UUID(vocab_id),),
        )
        v = await cur.fetchone()
        assert v["review_interval_days"] == 1.0
        assert v["review_count"] == 0

