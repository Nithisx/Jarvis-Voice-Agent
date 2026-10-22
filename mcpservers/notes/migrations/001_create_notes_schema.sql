-- =====================================================================
-- Migration 001: Notes, Vocabulary, and Spaced-Repetition Review Schema
-- Target: PostgreSQL 13+ (Uses built-in gen_random_uuid())
--
-- Safety Guarantees:
-- 1. Executed inside a single atomic transaction (BEGIN ... COMMIT).
-- 2. Strictly non-destructive: uses IF NOT EXISTS and does not drop tables.
-- 3. Idempotent: safe to re-run without errors or data loss.
--
-- Polymorphic Referential Integrity Architecture:
-- The `review_history` table stores spaced-repetition logs for both
-- `vocabulary` items and `notes`. PostgreSQL standard foreign keys cannot
-- reference multiple target tables from a single column (`item_id`).
-- Therefore:
-- - `item_type` is constrained to ('vocabulary', 'note').
-- - Referential integrity and transactional consistency are maintained and
--   strictly validated by the Notes MCP Server repository layer within
--   atomic database transactions.
-- =====================================================================

BEGIN;

-- ---------------------------------------------------------------------
-- 1. Notes Table
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS notes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    category TEXT NOT NULL CHECK (
        category IN ('general', 'communication', 'grammar', 'vocabulary', 'story', 'technical', 'personal_reflection')
    ),
    tags TEXT[] NOT NULL DEFAULT '{}',
    source TEXT,
    example TEXT,
    learned_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    review_interval_days NUMERIC NOT NULL DEFAULT 1.0,
    next_review_at TIMESTAMPTZ,
    last_reviewed_at TIMESTAMPTZ,
    review_count INTEGER NOT NULL DEFAULT 0,
    self_assessed_mastery NUMERIC,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    archived_at TIMESTAMPTZ
);

COMMENT ON TABLE notes IS 'Persistent knowledge notes with categorization, tags, and revision capabilities.';
COMMENT ON COLUMN notes.category IS 'Restricted category taxonomy for note classification.';
COMMENT ON COLUMN notes.tags IS 'Array of string tags for multifaceted search.';
COMMENT ON COLUMN notes.archived_at IS 'Timestamp when soft-archived. Null indicates an active note.';

-- ---------------------------------------------------------------------
-- 2. Vocabulary Table
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS vocabulary (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    word TEXT NOT NULL,
    normalized_word TEXT NOT NULL,
    meaning TEXT NOT NULL,
    example_sentence TEXT,
    synonyms JSONB NOT NULL DEFAULT '[]'::jsonb,
    word_type TEXT,
    pronunciation TEXT,
    source_context TEXT,
    difficulty TEXT CHECK (
        difficulty IS NULL OR difficulty IN ('beginner', 'intermediate', 'advanced')
    ),
    learned_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    review_interval_days NUMERIC NOT NULL DEFAULT 1.0,
    next_review_at TIMESTAMPTZ NOT NULL DEFAULT (CURRENT_TIMESTAMP + INTERVAL '1 day'),
    last_reviewed_at TIMESTAMPTZ,
    review_count INTEGER NOT NULL DEFAULT 0,
    self_assessed_mastery NUMERIC,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    archived_at TIMESTAMPTZ
);

COMMENT ON TABLE vocabulary IS 'Vocabulary entries with spaced repetition schedules and active recall metadata.';
COMMENT ON COLUMN vocabulary.normalized_word IS 'Lowercased, trimmed word representation used for duplicate detection.';
COMMENT ON COLUMN vocabulary.review_interval_days IS 'Current spacing interval in days calculated by the review scheduler.';
COMMENT ON COLUMN vocabulary.self_assessed_mastery IS 'Self-reported mastery score percentage (0-100%).';

-- ---------------------------------------------------------------------
-- 3. Review History Table (Spaced Repetition Logs)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS review_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    item_type TEXT NOT NULL CHECK (item_type IN ('vocabulary', 'note')),
    item_id UUID NOT NULL,
    rating INTEGER NOT NULL CHECK (rating >= 0 AND rating <= 3),
    response_text TEXT,
    feedback_notes TEXT,
    reviewed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    next_review_at TIMESTAMPTZ
);

COMMENT ON TABLE review_history IS 'Spaced-repetition revision log for vocabulary and notes.';
COMMENT ON COLUMN review_history.rating IS 'Self-assessed recall rating: 0 (Forgot), 1 (Hard), 2 (Good), 3 (Easy).';
COMMENT ON COLUMN review_history.item_id IS 'Polymorphic reference to vocabulary.id or notes.id, validated at application layer.';

-- ---------------------------------------------------------------------
-- 4. Indexes for Performance and Queries
-- ---------------------------------------------------------------------

-- Vocabulary Uniqueness: Case-insensitive unique constraint for active entries
CREATE UNIQUE INDEX IF NOT EXISTS idx_vocabulary_active_normalized_word 
    ON vocabulary (normalized_word) 
    WHERE archived_at IS NULL;

-- Notes Full-Text Search (GIN)
CREATE INDEX IF NOT EXISTS idx_notes_fts 
    ON notes 
    USING GIN (to_tsvector('english', coalesce(title, '') || ' ' || coalesce(content, '')));

-- Notes Category & Tags
CREATE INDEX IF NOT EXISTS idx_notes_category 
    ON notes (category) 
    WHERE archived_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_notes_tags 
    ON notes 
    USING GIN (tags) 
    WHERE archived_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_notes_learned_at 
    ON notes (learned_at);

CREATE INDEX IF NOT EXISTS idx_notes_next_review 
    ON notes (next_review_at) 
    WHERE archived_at IS NULL;

-- Vocabulary Full-Text Search (GIN)
CREATE INDEX IF NOT EXISTS idx_vocabulary_fts 
    ON vocabulary 
    USING GIN (to_tsvector('english', coalesce(word, '') || ' ' || coalesce(meaning, '')));

CREATE INDEX IF NOT EXISTS idx_vocabulary_normalized_word 
    ON vocabulary (normalized_word);

CREATE INDEX IF NOT EXISTS idx_vocabulary_learned_at 
    ON vocabulary (learned_at);

CREATE INDEX IF NOT EXISTS idx_vocabulary_next_review 
    ON vocabulary (next_review_at) 
    WHERE archived_at IS NULL;

-- Review History Indexes
CREATE INDEX IF NOT EXISTS idx_review_history_item 
    ON review_history (item_id, reviewed_at DESC);

CREATE INDEX IF NOT EXISTS idx_review_history_reviewed_at 
    ON review_history (reviewed_at DESC);

COMMIT;

