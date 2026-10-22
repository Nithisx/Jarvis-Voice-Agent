# Notes & Vocabulary MCP Server

A production-ready Model Context Protocol (MCP) server providing persistent note-taking, vocabulary storage, active recall quizzes, and deterministic spaced-repetition revision backed by PostgreSQL.

---

## 1. Architecture Overview

```
mcpservers/notes/
├── pyproject.toml                         # Project metadata and dependencies
├── README.md                              # Complete operational and integration documentation
├── .gitignore                             # Git exclusion rules
├── migrations/
│   ├── 001_create_notes_schema.sql        # Standalone, idempotent PostgreSQL schema migration
│   └── run_migration.py                   # Secure Python migration runner
├── src/
│   └── notes_server/
│       ├── __init__.py                    # Package initialization
│       ├── server.py                      # MCP Server setup (stdio transport) & lifecycle
│       ├── config.py                      # Root .env discovery, credential masking, pool config
│       ├── database.py                    # AsyncConnectionPool (psycopg v3) management
│       ├── schemas.py                     # Pydantic input models & row serialization
│       ├── exceptions.py                  # Custom domain and database exceptions
│       ├── repositories/
│       │   ├── __init__.py
│       │   ├── notes_repository.py        # Notes CRUD & GIN full-text search
│       │   └── vocabulary_repository.py   # Spaced repetition, active recall & analytics
│       └── tools/
│           ├── __init__.py                # Tool registry
│           ├── create_note.py             # Tool: create_note
│           ├── get_note.py                # Tool: get_note
│           ├── search_notes.py            # Tool: search_notes
│           ├── update_note.py             # Tool: update_note
│           ├── archive_note.py            # Tool: archive_note
│           ├── save_vocabulary.py         # Tool: save_vocabulary
│           ├── search_vocabulary.py       # Tool: search_vocabulary
│           ├── get_due_reviews.py         # Tool: get_due_reviews (active recall prompts)
│           ├── submit_review.py           # Tool: submit_review (atomic spaced repetition)
│           ├── get_daily_summary.py       # Tool: get_daily_summary (timezone-aware)
│           └── get_learning_stats.py      # Tool: get_learning_stats
└── tests/
    ├── conftest.py                        # Isolated test schema fixture & Windows selector loop
    ├── test_notes.py                      # Note CRUD, search, and archival tests
    ├── test_vocabulary.py                 # Vocabulary persistence & duplicate detection
    ├── test_reviews.py                    # Spaced repetition & active recall tests
    └── test_mcp_tools.py                  # MCP protocol tool registration & end-to-end tests
```

### Architectural Principles:
- **Clean Transport Separation**: Runs over `stdio`. All diagnostics and errors are strictly routed to `sys.stderr` to avoid corrupting MCP JSON-RPC protocol frames on `stdout`.
- **Database Engine**: Uses PostgreSQL with native `psycopg` v3 and asynchronous connection pooling via `psycopg_pool.AsyncConnectionPool`.
- **Zero Schema Auto-Creation**: The MCP server never runs migrations on startup. Migrations are executed intentionally and manually.
- **Data Isolation**: Tests execute against dynamically generated test schemas (`test_notes_<uuid>`) and clean up completely without modifying user data.
- **Polymorphic Referencing**: The `review_history` table records revision events for both `vocabulary` and `notes`. Because PostgreSQL foreign keys cannot target two disparate tables from a single column, referential integrity is strictly validated and enforced transactionally by the application layer.

---

## 2. Prerequisites & Environment Configuration

### Prerequisites
- Python 3.11+
- PostgreSQL 13+ (PostgreSQL 18 is verified and supported)

### PostgreSQL Connection Variable
The server automatically detects the existing PostgreSQL connection string configured in the root `.env` file under the key:

```env
DATABASE_URL=postgresql://user:password@localhost:5432/voiceagent
```

- **Discovery Mechanism**: The configuration module (`notes_server.config`) starts from the working directory and walks up the filesystem tree until it locates `.env`.
- **Secret Protection**: Credentials and passwords are masked (`postgresql://user:*****@host:port/db`) in all logs and error messages.
- **Optional Settings**:
  - `NOTES_DB_POOL_MIN_SIZE`: Minimum connection pool size (Default: `1`).
  - `NOTES_DB_POOL_MAX_SIZE`: Maximum connection pool size (Default: `10`).
  - `NOTES_DB_TIMEOUT_SECONDS`: Connection acquisition timeout in seconds (Default: `10.0`).
  - `NOTES_LOG_LEVEL`: Log level (`DEBUG`, `INFO`, `WARNING`, `ERROR`; Default: `INFO`).

---

## 3. Installation

From the project root:

```powershell
# 1. Activate your virtual environment (if not already activated)
.\.venv\Scripts\Activate.ps1

# 2. Install dependencies
pip install -e mcpservers/notes
```

Or install the required packages directly into your environment:
```powershell
pip install "mcp>=1.0.0" "psycopg[binary]>=3.1.0" "psycopg-pool>=3.1.0" "pydantic>=2.0.0" "python-dotenv>=1.0.0"
```

---

## 4. Manual Database Migration

The schema migration is located at:
`mcpservers/notes/migrations/001_create_notes_schema.sql`

The MCP server **never runs migrations automatically on startup**. You must run the migration once before starting the server.

### Option A: Using the Python Migration Runner (Recommended)
This runner safely reads `DATABASE_URL` from the root `.env` without printing secrets, runs the migration in a single transaction, and verifies the created tables and indexes:

```powershell
python mcpservers/notes/migrations/run_migration.py
```

### Option B: Using `psql` via PowerShell
Verify that `psql` is available:
```powershell
psql --version
```

Execute the migration by passing the connection string securely through an environment variable:
```powershell
$env:PGDATABASE_URL = (Get-Content .env | Where-Object { $_ -match '^\s*DATABASE_URL\s*=' } | ForEach-Object { $_.Split('=', 2)[1].Trim().Trim('"'') })
psql $env:PGDATABASE_URL -f "mcpservers/notes/migrations/001_create_notes_schema.sql"
Remove-Item Env:\PGDATABASE_URL
```

---

## 5. Starting the Server

### Standalone stdio Execution
To launch the MCP server in standard input/output mode:

```powershell
python -m notes_server.server
```

Or if installed via `pip install -e`:
```powershell
notes-mcp-server
```

---

## 6. MCP Client Configuration

### Registering with Claude Desktop / Cline / MCP Hosts

Add the following entry to your MCP client configuration file (e.g., `claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "notes": {
      "command": "d:\\Voice Agent\\.venv\\Scripts\\python.exe",
      "args": [
        "-m",
        "notes_server.server"
      ],
      "cwd": "d:\\Voice Agent",
      "env": {
        "PYTHONPATH": "d:\\Voice Agent\\mcpservers\\notes\\src"
      }
    }
  }
}
```

---

## 7. MCP Tools Reference

The server exposes 11 tools with validated parameters:

| Tool | Description | Key Arguments |
|------|-------------|---------------|
| `create_note` | Creates a persistent note with category and tags | `title`, `content`, `category`, `tags`, `source`, `example`, `learned_at` |
| `get_note` | Retrieves note by UUID | `note_id` |
| `search_notes` | Full-text and faceted search | `query`, `category`, `tags`, `include_archived`, `limit` |
| `update_note` | Updates supplied fields on active note | `note_id`, `title`, `content`, `category`, `tags`, `source`, `example` |
| `archive_note` | Soft-archives note | `note_id` |
| `save_vocabulary` | Saves word with duplicate detection | `word`, `meaning`, `example_sentence`, `synonyms`, `word_type`, `pronunciation`, `source_context`, `difficulty` |
| `search_vocabulary` | Searches vocabulary with pagination | `query`, `difficulty`, `word_type`, `include_archived`, `limit`, `offset` |
| `get_due_reviews` | Returns active-recall prompts (definitions hidden) | `limit`, `category` |
| `submit_review` | Records recall rating (0-3) and reschedules | `item_id`, `rating`, `response_text`, `feedback_notes` |
| `get_daily_summary` | Daily learning grouped by category | `date`, `timezone` |
| `get_learning_stats` | Global learning and recall trend statistics | *None* |

### Spaced-Repetition Rating Scale:
- **`0`**: *Forgot completely* — Immediate retry after 10 minutes.
- **`1`**: *Remembered with substantial difficulty* — Scheduled for review in 1 day.
- **`2`**: *Remembered with some effort* — Interval moderately increased (`max(3 days, previous * 2.0)`).
- **`3`**: *Remembered easily* — Interval substantially increased (`max(7 days, previous * 2.5)`).

> [!NOTE]
> All recall ratings are treated as subjective self-assessments for revision scheduling, not objectively verified exam scores.

---

## 8. Example Tool Invocations

### Example: `create_note`
```json
{
  "title": "PostgreSQL Full-Text Search",
  "content": "GIN indexes with to_tsvector provide fast lexical lookups.",
  "category": "technical",
  "tags": ["postgres", "indexing", "database"],
  "source": "manual"
}
```

### Example: `save_vocabulary`
```json
{
  "word": "Ubiquitous",
  "meaning": "Present, appearing, or found everywhere.",
  "example_sentence": "Smartphones have become ubiquitous in modern society.",
  "synonyms": ["omnipresent", "pervasive"],
  "word_type": "adjective",
  "difficulty": "intermediate"
}
```

### Example: `get_due_reviews`
Returns quiz prompts without revealing answers:
```json
{
  "success": true,
  "total_due": 1,
  "due_reviews": [
    {
      "item_id": "7fa8e1b3-4f2b-4e09-880c-7b4d1b82142e",
      "item_type": "vocabulary",
      "prompt": "What is the definition and usage of: 'Ubiquitous'?",
      "word": "Ubiquitous",
      "word_type": "adjective",
      "due_status": "due_today"
    }
  ]
}
```

### Example: `submit_review`
```json
{
  "item_id": "7fa8e1b3-4f2b-4e09-880c-7b4d1b82142e",
  "rating": 3,
  "response_text": "Present everywhere",
  "feedback_notes": "Recalled quickly."
}
```

---

## 9. Running Tests

Automated testing is configured using `pytest` and `pytest-asyncio`. Tests run against an isolated PostgreSQL test schema that is created and destroyed automatically:

```powershell
python -m pytest mcpservers/notes/tests -v
```

All 23 tests cover:
- Notes CRUD and soft-archival.
- Full-text search and faceted filtering.
- Vocabulary persistence and case-insensitive duplicate prevention.
- Spaced repetition algorithm and active recall prompt masking.
- Daily summary timezone boundaries.
- Atomic transaction execution and rollback.
- Database connection error handling and credential protection.

---

## 10. Backup, Recovery & Security Considerations

### Backup & Recovery
To back up the notes and vocabulary tables:
```powershell
pg_dump -d voiceagent -t notes -t vocabulary -t review_history -f notes_backup.sql
```
To restore:
```powershell
psql -d voiceagent -f notes_backup.sql
```

### Security Notes
1. **Parameterized Queries**: Every SQL query is parameterized with psycopg `%s` bindings to eliminate SQL injection vulnerabilities.
2. **Credential Sanitization**: The connection string is never printed or surfaced in logs or error responses.
3. **No Automatic Transcript Dumping**: The server never records ambient conversation transcripts. It only writes data when tools are explicitly invoked.
4. **Soft Archival**: Archived records retain their full audit trail and timestamps, preventing accidental permanent data loss.

