"""Tests for vocabulary persistence, duplicate detection, and search."""

from __future__ import annotations

import uuid
import pytest
from datetime import datetime, timezone

from notes_server.exceptions import RecordNotFoundError
from notes_server.repositories.vocabulary_repository import VocabularyRepository


@pytest.mark.asyncio
async def test_save_vocabulary_success(test_conn):
    """Verify saving a new vocabulary entry."""
    unique_word = f"Serendipity_{uuid.uuid4().hex[:4]}"
    res = await VocabularyRepository.save_vocabulary(
        conn=test_conn,
        word=unique_word,
        meaning="Finding valuable things not sought for.",
        example_sentence="A fortunate stroke of serendipity brought them together.",
        synonyms=["fluke", "chance", "coincidence"],
        word_type="noun",
        pronunciation="/ˌser.ənˈdɪp.ə.ti/",
        difficulty="advanced",
    )

    assert res["is_duplicate"] is False
    assert res["id"] is not None
    record = res["saved_record"]
    assert record["normalized_word"] == unique_word.lower()
    assert record["word"] == unique_word
    assert record["review_interval_days"] == 1.0
    assert record["next_review_at"] is not None


@pytest.mark.asyncio
async def test_duplicate_vocabulary_detection(test_conn):
    """Verify case-insensitive duplicate detection returns existing ID."""
    word = f"Ephemeral_{uuid.uuid4().hex[:4]}"
    res1 = await VocabularyRepository.save_vocabulary(
        conn=test_conn,
        word=word,
        meaning="Lasting for a very short time.",
        difficulty="intermediate",
    )
    assert res1["is_duplicate"] is False
    initial_id = res1["id"]

    # Attempt to save the same word with different casing and whitespace
    res2 = await VocabularyRepository.save_vocabulary(
        conn=test_conn,
        word=f"  {word.upper()}  ",
        meaning="Another definition attempted.",
    )
    assert res2["is_duplicate"] is True
    assert res2["id"] == initial_id
    assert "already exists" in res2["message"]


@pytest.mark.asyncio
async def test_search_vocabulary(test_conn):
    """Verify searching vocabulary by word, meaning, synonym, and context."""
    kw = f"lucid_{uuid.uuid4().hex[:4]}"
    await VocabularyRepository.save_vocabulary(
        conn=test_conn,
        word=f"{kw}_word",
        meaning="Expressed clearly; easy to understand.",
        example_sentence="She gave a lucid explanation.",
        synonyms=["articulate", "coherent"],
        word_type="adjective",
        difficulty="intermediate",
    )

    # Search by word
    by_word = await VocabularyRepository.search_vocabulary(test_conn, query=kw)
    assert len(by_word) >= 1

    # Search by meaning
    by_meaning = await VocabularyRepository.search_vocabulary(test_conn, query="understand")
    assert any(v["word"] == f"{kw}_word" for v in by_meaning)

    # Search by synonym
    by_syn = await VocabularyRepository.search_vocabulary(test_conn, query="articulate")
    assert any(v["word"] == f"{kw}_word" for v in by_syn)

    # Filter by difficulty
    by_diff = await VocabularyRepository.search_vocabulary(
        test_conn, query=kw, difficulty="intermediate"
    )
    assert len(by_diff) >= 1

    # Filter mismatch
    by_diff_mismatch = await VocabularyRepository.search_vocabulary(
        test_conn, query=kw, difficulty="beginner"
    )
    assert len(by_diff_mismatch) == 0


@pytest.mark.asyncio
async def test_get_vocabulary_by_id(test_conn):
    """Verify retrieval by ID."""
    res = await VocabularyRepository.save_vocabulary(
        conn=test_conn,
        word=f"ineffable_{uuid.uuid4().hex[:4]}",
        meaning="Too great or extreme to be expressed in words.",
    )
    vocab_id = res["id"]

    fetched = await VocabularyRepository.get_vocabulary_by_id(test_conn, vocab_id)
    assert fetched["id"] == vocab_id
    assert "ineffable" in fetched["word"]

