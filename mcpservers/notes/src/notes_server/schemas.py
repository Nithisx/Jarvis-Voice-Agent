"""Data schemas and Pydantic validation models for Notes MCP Server."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

NoteCategory = Literal[
    "general",
    "communication",
    "grammar",
    "vocabulary",
    "story",
    "technical",
    "personal_reflection",
]

DifficultyLevel = Literal[
    "beginner",
    "intermediate",
    "advanced",
]


class CreateNoteInput(BaseModel):
    title: str = Field(..., min_length=1, description="Title of the note.")
    content: str = Field(..., min_length=1, description="Markdown or text content of the note.")
    category: NoteCategory = Field(
        default="general",
        description="Category: general, communication, grammar, vocabulary, story, technical, or personal_reflection.",
    )
    tags: list[str] = Field(default_factory=list, description="Optional list of tags for searching.")
    source: Optional[str] = Field(None, description="Source context (e.g. conversation, web, manual, story).")
    example: Optional[str] = Field(None, description="Optional example sentence or snippet.")
    learned_at: Optional[datetime] = Field(None, description="Timestamp when learned, defaults to current UTC.")

    @field_validator("title", "content", mode="before")
    @classmethod
    def strip_text(cls, v: Any) -> Any:
        if isinstance(v, str):
            v = v.strip()
            if not v:
                raise ValueError("Must not be empty or whitespace only.")
        return v

    @field_validator("tags", mode="before")
    @classmethod
    def clean_tags(cls, v: Any) -> list[str]:
        if v is None:
            return []
        if isinstance(v, list):
            return [str(t).strip().lower() for t in v if str(t).strip()]
        return []


class UpdateNoteInput(BaseModel):
    note_id: str = Field(..., description="UUID of the note to update.")
    title: Optional[str] = Field(None, min_length=1, description="Updated title.")
    content: Optional[str] = Field(None, min_length=1, description="Updated content.")
    category: Optional[NoteCategory] = Field(None, description="Updated category.")
    tags: Optional[list[str]] = Field(None, description="Updated tags.")
    source: Optional[str] = Field(None, description="Updated source context.")
    example: Optional[str] = Field(None, description="Updated example.")

    @field_validator("title", "content", mode="before")
    @classmethod
    def strip_text(cls, v: Any) -> Any:
        if isinstance(v, str):
            v = v.strip()
            if not v:
                raise ValueError("Must not be empty string.")
        return v


class SearchNotesInput(BaseModel):
    query: Optional[str] = Field(None, description="Full-text search query across titles and contents.")
    category: Optional[NoteCategory] = Field(None, description="Filter by note category.")
    tags: Optional[list[str]] = Field(None, description="Filter by tags (matches any listed).")
    include_archived: bool = Field(False, description="Whether to include archived notes.")
    limit: int = Field(20, ge=1, le=100, description="Max results to return (1-100).")


class SaveVocabularyInput(BaseModel):
    word: str = Field(..., min_length=1, description="The vocabulary word or phrase.")
    meaning: str = Field(..., min_length=1, description="Clear definition or translation.")
    example_sentence: Optional[str] = Field(None, description="Example sentence demonstrating usage.")
    synonyms: list[str] = Field(default_factory=list, description="Synonyms or related terms.")
    word_type: Optional[str] = Field(None, description="Part of speech (e.g. noun, verb, idiom).")
    pronunciation: Optional[str] = Field(None, description="IPA or phonetic guide.")
    source_context: Optional[str] = Field(None, description="Origin context or story.")
    difficulty: Optional[DifficultyLevel] = Field(None, description="beginner, intermediate, or advanced.")

    @field_validator("word", "meaning", mode="before")
    @classmethod
    def strip_text(cls, v: Any) -> Any:
        if isinstance(v, str):
            v = v.strip()
            if not v:
                raise ValueError("Must not be empty string.")
        return v

    @field_validator("synonyms", mode="before")
    @classmethod
    def clean_synonyms(cls, v: Any) -> list[str]:
        if v is None:
            return []
        if isinstance(v, list):
            return [str(s).strip() for s in v if str(s).strip()]
        return []


class SearchVocabularyInput(BaseModel):
    query: Optional[str] = Field(None, description="Search term for word, meaning, synonyms, or context.")
    difficulty: Optional[DifficultyLevel] = Field(None, description="Filter by difficulty level.")
    word_type: Optional[str] = Field(None, description="Filter by part of speech.")
    include_archived: bool = Field(False, description="Whether to include archived vocabulary.")
    limit: int = Field(20, ge=1, le=100, description="Max results (1-100).")
    offset: int = Field(0, ge=0, description="Offset for pagination.")


class GetDueReviewsInput(BaseModel):
    limit: int = Field(10, ge=1, le=50, description="Maximum number of items to retrieve (1-50).")
    category: Optional[str] = Field(None, description="Optional category filter.")


class SubmitReviewInput(BaseModel):
    item_id: str = Field(..., description="UUID of the vocabulary item or note being reviewed.")
    rating: int = Field(..., ge=0, le=3, description="0 (Forgot), 1 (Hard), 2 (Good), 3 (Easy).")
    response_text: Optional[str] = Field(None, description="User's recalled answer or transcript.")
    feedback_notes: Optional[str] = Field(None, description="Optional notes or observations.")


class GetDailySummaryInput(BaseModel):
    date: Optional[str] = Field(None, description="Target calendar date in YYYY-MM-DD format.")
    timezone: str = Field("Asia/Kolkata", description="IANA timezone name, e.g. 'Asia/Kolkata', 'UTC'.")


def serialize_db_record(record: dict[str, Any] | None) -> dict[str, Any] | None:
    """Normalize and serialize PostgreSQL record values (UUIDs, datetimes, JSON)."""
    if record is None:
        return None
    output: dict[str, Any] = {}
    for key, val in record.items():
        if isinstance(val, UUID):
            output[key] = str(val)
        elif isinstance(val, datetime):
            output[key] = val.isoformat()
        elif isinstance(val, (list, tuple)):
            output[key] = [
                str(x) if isinstance(x, UUID) else (x.isoformat() if isinstance(x, datetime) else x)
                for x in val
            ]
        elif isinstance(val, dict):
            output[key] = val
        else:
            output[key] = val
    return output

