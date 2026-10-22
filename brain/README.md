# JARVIS — Voice-to-Voice Personal AI Assistant

JARVIS is a production-grade, **voice-first** AI assistant running entirely on your local Windows machine (Ryzen CPU, no NVIDIA GPU required). Say something; JARVIS listens, reasons using DeepSeek, optionally calls your Notes or Web Search tools, and speaks back using local Kokoro-82M text-to-speech — all in real time.

---

## Architecture

```
Microphone
    │
    ▼
Moonshine Tiny Streaming (STT)       ← Speach2text.py (SpeechToTextService)
    │  (on-device, no cloud)
    ▼
asyncio Transcript Queue
    │
    ▼
LangGraph StateGraph  ─────────────────────────────────────────────────────┐
    │                                                                       │
    ├── DeepSeek API (deepseek-chat)                                        │
    │      reasoning_node → should_continue? ──► tools_node                │
    │                              ▲                  │                     │
    │                              └──────────────────┘                     │
    │                                (tool loop, max 6 steps)               │
    │                                                                       │
    ├── MCP Client Manager (stdio subprocess)                               │
    │      ├── Notes MCP Server      (mcpservers/notes)                     │
    │      └── Web Search MCP Server (mcpservers/web_search)                │
    │                                                                       │
    └── format_response_node → clean spoken text ◄─────────────────────────┘
              │
              ▼
    Kokoro-82M KPipeline (TTS)       ← local CPU, lang_code="a", voice="af_heart"
              │
              ▼
    sounddevice audio playback
              │
              ▼
    Microphone resumes (half-duplex)
```

Conversation state is persisted in **PostgreSQL** via `AsyncPostgresSaver` (LangGraph checkpoint). Falls back to `MemorySaver` if PostgreSQL is unavailable.

---

## Project Layout

```
brain/
├── pyproject.toml              # Package definition, entry-point: jarvis
├── README.md                   # This file
├── .gitignore
│
├── configs/
│   ├── brain.yaml              # Agent & memory configuration
│   ├── mcp_servers.yaml        # Stdio launch commands for MCP servers
│   └── voice.yaml              # STT / TTS / audio settings
│
├── scripts/
│   ├── setup_models.py         # Pre-warm Kokoro + verify Moonshine
│   ├── preflight.py            # Full environment pre-launch check
│   ├── health_check.py         # Active diagnostic (API + MCP + TTS)
│   └── setup_checkpointer.py   # Create LangGraph checkpoint tables in Postgres
│
├── src/
│   └── jarvis_brain/
│       ├── main.py             # CLI entry-point  (jarvis / python -m jarvis_brain.main)
│       ├── lifecycle.py        # 14-step startup orchestrator
│       ├── config.py           # Root .env discovery, secrets, YAML loading
│       ├── exceptions.py       # Typed exception hierarchy
│       │
│       ├── agent/              # LangGraph brain
│       │   ├── graph.py        # StateGraph compiler + JarvisBrain runner
│       │   ├── nodes.py        # reasoning_node, tools_node, format_response_node
│       │   ├── routing.py      # should_continue() conditional edge
│       │   ├── state.py        # AgentState TypedDict
│       │   ├── deepseek_client.py
│       │   ├── prompts.py      # System persona + startup greeting constant
│       │   └── policies.py     # Security: injection neutralization, arg bounds
│       │
│       ├── mcp/                # MCP stdio client management
│       │   ├── client_manager.py   # AsyncExitStack, connect_all(), get_tools()
│       │   ├── config_loader.py    # YAML → stdio launch parameters
│       │   ├── discovery.py        # MCP tool → LangChain BaseTool adapter
│       │   └── health.py           # MCP health probe
│       │
│       ├── memory/
│       │   ├── checkpointer.py     # AsyncPostgresSaver / MemorySaver
│       │   └── session_manager.py  # Thread ID, history trimming
│       │
│       ├── observability/
│       │   ├── logging.py          # Structured stderr logger + secret redaction
│       │   └── metrics.py          # Per-turn latency tracking
│       │
│       └── voice/
│           ├── speech_input.py     # Moonshine → asyncio.Queue bridge
│           ├── tts_kokoro.py       # KokoroTTSService (CPU, 24kHz)
│           ├── audio_output.py     # Thread-safe sounddevice player
│           ├── voice_loop.py       # Continuous half-duplex turn-taking loop
│           ├── speech_formatter.py # Markdown → clean speech text
│           └── greeting.py         # Mandatory startup greeting
│
└── tests/
    ├── conftest.py
    ├── unit/                   # Fast, fully offline (all external APIs mocked)
    ├── integration/            # Connects to real MCP servers & DeepSeek (skipped by default)
    └── safety/                 # Prompt injection & tool policy guards
```

---

## Prerequisites

| Requirement | Version |
|---|---|
| Python | 3.11+ |
| Windows | 10 / 11 (Ryzen CPU; no GPU required) |
| PostgreSQL | 14+ (optional — falls back to in-memory if absent) |
| DeepSeek API key | in root `.env` as `DeepSeek_api` |
| Tavily API key | in root `.env` as `TAVILY_API_KEY` |

---

## Quick Start

### 1 — Install dependencies

```powershell
# From the project root (where .venv lives)
.venv\Scripts\pip install -e brain[dev]
.venv\Scripts\pip install -e mcpservers\notes
.venv\Scripts\pip install -e mcpservers\web_search
```

### 2 — Verify root `.env`

```env
# Required
DeepSeek_api=sk-...
TAVILY_API_KEY=tvly-...

# Required for persistent memory (remove if using in-memory fallback)
DATABASE_URL=postgresql://user:password@localhost:5432/voiceagent

# Optional — defaults shown
model=deepseek-flash
```

### 3 — Run the Notes MCP database migration

```powershell
$env:PGPASSWORD="yourpassword"
psql -U postgres -d voiceagent -f mcpservers\notes\migrations\001_create_notes_schema.sql
```

### 4 — Set up the LangGraph checkpoint tables

```powershell
.venv\Scripts\python brain\scripts\setup_checkpointer.py
```

### 5 — Pre-warm local AI models (first run only)

Downloads Kokoro-82M weights from Hugging Face and verifies Moonshine. Requires internet on first run only.

```powershell
.venv\Scripts\python brain\scripts\setup_models.py
```

### 6 — Run preflight checks

Verifies audio hardware, environment variables, MCP server packages, and local models before launch.

```powershell
.venv\Scripts\python brain\scripts\preflight.py
```

### 7 — Launch JARVIS

```powershell
# Option A: via installed entry-point (note the leading .\)
.\venv\Scripts\jarvis

# Option B: direct module (most reliable)
.\venv\Scripts\python.exe -m jarvis_brain.main

# Option C: with flags
.\venv\Scripts\python.exe -m jarvis_brain.main --debug
.\venv\Scripts\python.exe -m jarvis_brain.main --skip-readiness
```

> **PowerShell note:** Always prefix relative paths with `.\` when running executables.
> `.venv\Scripts\jarvis` will fail — `.\venv\Scripts\jarvis` works.

On successful startup JARVIS will:
1. Load Moonshine STT + Kokoro TTS models into memory.
2. Connect to the Notes and Web Search MCP servers.
3. Compile the LangGraph reasoning engine.
4. **Speak the welcome greeting** before the microphone activates:
   > *"Welcome back, Nithish! It's good to have you here. I'm ready to chat, explore something interesting, and help you practise your communication skills. What's on your mind today?"*
5. Begin listening continuously until you press **Ctrl+C**.

---

## Running the Test Suite

```powershell
# All unit + safety tests (fast, fully offline, ~15s)
.venv\Scripts\python -m pytest brain\tests\unit brain\tests\safety -v

# MCP integration test (connects to live subprocess MCP servers, ~15s)
.venv\Scripts\python -m pytest brain\tests\integration\test_mcp_connections.py -v

# Voice pipeline simulation (loads Kokoro model, ~3–4 min on first run)
.venv\Scripts\python -m pytest brain\tests\integration\test_voice_pipeline.py -v

# Live DeepSeek API call (requires real API key, costs credits)
$env:LIVE_TEST = "1"
.venv\Scripts\python -m pytest brain\tests\integration\test_deepseek.py::test_deepseek_live_call -v

# Full suite
.venv\Scripts\python -m pytest brain\tests -v
```

### Test coverage summary

| Suite | Count | External calls |
|---|---|---|
| `unit/` | 23 tests | None (all mocked) |
| `safety/` | 6 tests | None |
| `integration/test_mcp_connections.py` | 1 test | Notes + Web Search MCP subprocesses |
| `integration/test_deepseek.py` | 2 tests (+ 1 skipped live) | Mocked; live skipped by default |
| `integration/test_voice_pipeline.py` | 1 test | Loads Kokoro locally, mocks DeepSeek |

---

## Active Diagnostics

```powershell
# Check DeepSeek API, MCP servers, and TTS synthesizer
.venv\Scripts\python brain\scripts\health_check.py
```

---

## Configuration Reference

### `configs/brain.yaml`

```yaml
agent:
  temperature: 0.7         # DeepSeek sampling temperature
  max_tool_steps: 6        # Maximum MCP tool iterations per turn
  timeout_seconds: 30.0    # DeepSeek API request timeout
  readiness_check: true    # Probe DeepSeek at startup

memory:
  thread_id: "jarvis_main_session"
  checkpointer_type: "postgres"   # "postgres" or "memory"
  max_history_messages: 20
```

### `configs/voice.yaml`

```yaml
stt:
  model_arch: 2            # Moonshine Tiny Streaming architecture
  language: "en"

tts:
  voice: "af_heart"        # Kokoro voice ID
  speed: 1.0
  device: "cpu"
  sample_rate: 24000

interaction:
  mode: "half_duplex"      # Mic mutes during TTS playback (prevents feedback)
```

### `configs/mcp_servers.yaml`

Defines how each MCP server is launched as a stdio subprocess. No modification required if you installed the packages with `pip install -e`.

---

## Environment Variables

All resolved from the root `.env` file or the process environment. **Never duplicated** into a secondary `.env`.

| Variable | Required | Description |
|---|---|---|
| `DeepSeek_api` | ✅ | DeepSeek API key (`sk-...`) |
| `TAVILY_API_KEY` | ✅ | Tavily API key (`tvly-...`) |
| `DATABASE_URL` | Optional | PostgreSQL connection string. If absent, uses `MemorySaver` |
| `model` | Optional | DeepSeek model name; `deepseek-flash` → `deepseek-chat` |

Secrets are **never** printed, logged, or passed as environment variables to MCP subprocess children.

---

## Security

- **Secret redaction:** All log output passes through a regex-based redactor that masks `sk-...`, `tvly-...` keys and PostgreSQL password fields.
- **Prompt injection neutralization:** Retrieved web content is sanitized before being included in LLM context. Patterns like *"Ignore all previous instructions"* are replaced with `[Neutralized directive]`.
- **Tool authorization:** Only tools registered at startup can be invoked. Unknown tool names raise `PolicyViolationError`.
- **Argument bounds:** Tool string arguments exceeding 20,000 characters are rejected before execution.
- **Content truncation:** External retrieved content is capped at 12,000 characters to prevent context-stuffing.

---

## Stopping JARVIS

Press **Ctrl+C** at any time. JARVIS will:
1. Stop the microphone capture stream.
2. Close MCP server subprocesses cleanly.
3. Close the PostgreSQL checkpointer connection pool.
4. Exit with code 0.

---

## Troubleshooting

### Kokoro TTS takes a long time on first launch
Kokoro-82M weights are downloaded from Hugging Face Hub on first use. Run `setup_models.py` once to pre-cache them.

### `UndefinedTable: relation "checkpoints" does not exist`
Run `setup_checkpointer.py` to create the LangGraph checkpoint tables:
```powershell
.venv\Scripts\python brain\scripts\setup_checkpointer.py
```

### Microphone not detected
Check that your default Windows audio input device is set correctly in **Settings → System → Sound**. Run `preflight.py` to list detected devices.

### DeepSeek authentication error
Verify `DeepSeek_api` is set correctly in the root `.env`. Run `health_check.py` to probe the API.

### `asyncio.WindowsSelectorEventLoopPolicy` warning
This is set automatically on Windows in `main.py`. No action required.

