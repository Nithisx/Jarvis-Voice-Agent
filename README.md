<div align="center">

# 🤖 JARVIS — Voice-to-Voice Personal AI Assistant

**A fully local, production-grade AI assistant that listens, thinks, and talks back.**

Powered by **Moonshine STT** · **DeepSeek** · **Kokoro-82M TTS** · **LangGraph** · **MCP Tools**

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)
![Platform](https://img.shields.io/badge/Platform-Windows-0078D4?logo=windows)
![CPU](https://img.shields.io/badge/Hardware-CPU%20Only-green)
![License](https://img.shields.io/badge/License-MIT-yellow)

</div>

---

## What is JARVIS?

JARVIS is a **voice-first** personal AI assistant that runs entirely on your Windows PC — no GPU, no cloud STT, no cloud TTS required.

You speak → JARVIS listens → reasons using DeepSeek → optionally searches the web or saves notes → **speaks back** using a local Kokoro-82M voice model — all in real time.

### Core capabilities

| Capability | Technology |
|---|---|
| 🎙️ Speech recognition (on-device) | Moonshine Tiny Streaming (CPU) |
| 🛡️ Wake-word gate (on-device) | Local regex gate (`Hey Jarvis`, `Jarvis`) + 3.0s silence endpointing |
| 🧠 Reasoning & tool use | DeepSeek API via LangGraph (streaming disabled) |
| 📋 Command queueing | Bounded FIFO queue (cap 5) with non-blocking concurrent capture |
| 📒 Persistent note-taking | Notes MCP Server + PostgreSQL |
| 🌐 Web search | Tavily Web Search MCP Server |
| 🔊 Text-to-speech (on-device) | Kokoro-82M (CPU, 24 kHz) · gapless full-response continuous synthesis |
| 💾 Conversation memory | LangGraph AsyncPostgresSaver |

---

## System Architecture

```
You speak
    │
    ▼
┌─────────────────────────────────────────────┐
│  Moonshine Tiny Streaming (on-device STT)   │
│  No cloud. No latency. Runs on CPU.         │
└─────────────────────────────────────────────┘
    │  finalized transcript
    ▼
┌─────────────────────────────────────────────────────────────────┐
│  LangGraph StateGraph  (JARVIS Brain)                           │
│                                                                 │
│  reasoning_node  ──► should_continue?                          │
│       ▲                    │                                    │
│       │           ┌────────┴────────┐                          │
│       │        tools?           respond?                       │
│       │           │                │                            │
│       └───── tools_node      format_response_node              │
│              (MCP calls)          │                            │
│                              clean spoken text                 │
└────────────────────────────────────────────────────────────────┘
    │  two MCP servers via stdio subprocess
    ├── 📒 Notes MCP Server     (PostgreSQL — notes, vocabulary, spaced repetition)
    └── 🌐 Web Search MCP Server (Tavily — real-time search, page content, vocabulary lookup)
    │
    ▼
┌─────────────────────────────────────────────┐
│  Kokoro-82M KPipeline (on-device TTS)       │
│  24 kHz · CPU · No cloud                   │
└─────────────────────────────────────────────┘
    │
    ▼
🔊 Speaker output  →  mic resumes (half-duplex)
```

---

## Project Structure

```
Voice Agent/
├── .env                        ← API keys & DB connection (never committed)
├── .gitignore
├── README.md                   ← This file
├── Speach2text.py              ← Moonshine STT service (reusable library)
│
├── brain/                      ← JARVIS orchestration brain
│   ├── pyproject.toml
│   ├── README.md               ← Brain-specific deep docs
│   ├── configs/
│   │   ├── brain.yaml          ← Agent, memory, observability config
│   │   ├── mcp_servers.yaml    ← MCP server launch commands
│   │   └── voice.yaml          ← STT / TTS / audio settings
│   ├── scripts/
│   │   ├── setup_models.py     ← Download & pre-warm AI models
│   │   ├── setup_checkpointer.py ← Create DB checkpoint tables
│   │   ├── preflight.py        ← Pre-launch system check
│   │   └── health_check.py     ← Active diagnostic (APIs + TTS)
│   ├── src/jarvis_brain/
│   │   ├── main.py             ← CLI entry-point
│   │   ├── lifecycle.py        ← Startup / shutdown orchestrator
│   │   ├── config.py           ← Root .env discovery + YAML loading
│   │   ├── agent/              ← LangGraph brain (graph, nodes, routing)
│   │   ├── mcp/                ← MCP stdio client manager
│   │   ├── memory/             ← Conversation checkpointing
│   │   ├── voice/              ← STT bridge, TTS, audio, voice loop
│   │   └── observability/      ← Logging (secret-redacted) + metrics
│   └── tests/
│       ├── unit/               ← 23 tests, fully offline (all APIs mocked)
│       ├── integration/        ← Live MCP + DeepSeek tests
│       └── safety/             ← Prompt injection & policy guards
│
└── mcpservers/
    ├── notes/                  ← Notes & vocabulary MCP server (PostgreSQL)
    │   ├── migrations/
    │   │   └── 001_create_notes_schema.sql
    │   └── src/notes_server/
    │       ├── server.py
    │       ├── tools/          ← 11 MCP tools (create, search, review...)
    │       └── repositories/   ← SQL queries (parameterized)
    └── web_search/             ← Tavily web search MCP server
        └── src/web_search_server/
            ├── server.py
            └── tools/          ← search_web, get_page_content, find_vocabulary
```

---

## Prerequisites

| Requirement | Notes |
|---|---|
| **Windows 10 / 11** | Tested on Ryzen CPU — no GPU needed |
| **Python 3.11+** | Download from [python.org](https://www.python.org/downloads/) |
| **PostgreSQL 14+** | For notes storage and conversation memory |
| **DeepSeek API key** | [platform.deepseek.com](https://platform.deepseek.com) |
| **Tavily API key** | [tavily.com](https://tavily.com) (free tier available) |
| **Microphone** | Any default Windows audio input |

---

## Installation — Step by Step

### Step 1 — Clone the repository

```powershell
git clone https://github.com/your-username/voice-agent.git
cd "voice-agent"
```

### Step 2 — Create a Python virtual environment

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

> If you get a script execution error, run this first:
> ```powershell
> Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
> ```

### Step 3 — Install all packages

```powershell
# Install JARVIS brain
pip install -e brain

# Install the MCP servers
pip install -e mcpservers\notes
pip install -e mcpservers\web_search
```

> The `-e` flag installs in **editable mode** — source changes take effect immediately.

### Step 4 — Create your `.env` file

Create a file named `.env` in the project root with the following content:

```env
# DeepSeek API — get your key at platform.deepseek.com
DeepSeek_api=sk-your-deepseek-key-here

# Tavily Web Search — get your key at tavily.com
TAVILY_API_KEY=tvly-your-tavily-key-here

# PostgreSQL — your local or remote database
DATABASE_URL=postgresql://postgres:yourpassword@localhost:5432/voiceagent

# DeepSeek model (optional — deepseek-flash maps to deepseek-chat automatically)
model=deepseek-flash
```

> **Never commit this file.** It is already listed in `.gitignore`.

### Step 5 — Create the PostgreSQL database

```powershell
# Create the database (run in psql or pgAdmin)
psql -U postgres -c "CREATE DATABASE voiceagent;"

# Run the Notes schema migration
psql -U postgres -d voiceagent -f mcpservers\notes\migrations\001_create_notes_schema.sql
```

### Step 6 — Set up conversation memory tables

```powershell
python brain\scripts\setup_checkpointer.py
```

### Step 7 — Download and pre-warm AI models

This downloads Kokoro-82M weights from Hugging Face and verifies Moonshine. **Internet required on first run only.**

```powershell
python brain\scripts\setup_models.py
```

> First run takes 2–5 minutes depending on your connection. Subsequent launches are instant.

### Step 8 — Run preflight checks

Verifies your audio devices, environment variables, MCP packages, and local models before launch:

```powershell
python brain\scripts\preflight.py
```

All checks should show `[PASS]`. Fix any failures before proceeding.

---

## Running JARVIS

```powershell
python -m jarvis_brain.main
```

### What happens on startup

1. ✅ Loads Moonshine STT model into memory
2. ✅ Loads Kokoro-82M TTS model into memory
3. ✅ Probes DeepSeek API connectivity
4. ✅ Connects to Notes and Web Search MCP servers
5. ✅ Compiles LangGraph reasoning graph
6. 🔊 **Speaks the welcome greeting:**
   > *"Welcome back, Nithish! It's good to have you here. I'm ready to chat, explore something interesting, and help you practise your communication skills. What's on your mind today?"*
7. 🎙️ **Microphone activates** — JARVIS is now listening

Press **Ctrl+C** to exit cleanly.

### Launch options

```powershell
# Standard launch
python -m jarvis_brain.main

# Skip DeepSeek ping at startup (faster boot)
python -m jarvis_brain.main --skip-readiness

# Enable verbose debug logging
python -m jarvis_brain.main --debug
```

---

## How JARVIS Works — Turn by Turn

```
1. Moonshine continuously transcribes audio in the background on CPU.
2. In-place RMS audio energy calculation monitors vocal activity (VAD).
3. If no wake phrase ("Hey Jarvis" / "Jarvis") is present:
       → The transcript is completely discarded. Zero DeepSeek calls.
4. When "Hey Jarvis" or "Jarvis" is detected:
       → MicGateState transitions from LISTENING_FOR_WAKE_WORD to CAPTURING_COMMAND.
       → Wake phrase is stripped, remaining text capitalized.
5. 3.0-Second Silence Endpointing:
       → A background monitor detects 3.0 continuous seconds of silence below threshold.
       → Command is validated (non-empty) and enqueued into the FIFO CommandQueue (cap: 5).
6. VoiceLoop sequentially dequeues the command and invokes LangGraph Brain:
       → DeepSeek reasons (streaming: false) and optionally loops over MCP tools.
       → The microphone remains unmuted during LLM/MCP processing, allowing concurrent command capture.
7. format_response_node produces the complete final answer.
8. Full-Waveform Kokoro TTS Synthesis:
       → Kokoro synthesizes all sentences in memory.
       → Concatenates chunks into a single 1D continuous waveform (float32, 24 kHz).
       → Amplitude is normalized within [-1.0, 1.0] to prevent audio clipping.
9. Half-Duplex Playback:
       → Microphone is muted to prevent acoustic feedback / self-triggering loops.
       → sounddevice plays the entire continuous waveform without sentence gaps.
       → After playback + 300ms reverberation settle delay, microphone unblocks and resumes listening.
```

---

## MCP Tool Reference

### Notes MCP Server (`mcpservers/notes`)

| Tool | Description |
|---|---|
| `create_note` | Save a note with category, tags, and source metadata |
| `get_note` | Retrieve a note by ID |
| `search_notes` | Full-text search across notes |
| `update_note` | Edit fields of an existing note |
| `archive_note` | Soft-archive a note (non-destructive) |
| `save_vocabulary` | Save a word + meaning; sets first spaced-repetition review |
| `search_vocabulary` | Search your vocabulary list |
| `get_due_reviews` | Get items ready for spaced-repetition recall |
| `submit_review` | Rate your recall (0=forgot → 3=easy); reschedules next review |
| `get_daily_summary` | Notes and vocabulary learned today |
| `get_learning_stats` | Overall learning statistics |

### Web Search MCP Server (`mcpservers/web_search`)

| Tool | Description |
|---|---|
| `search_web` | Real-time Tavily web search with source attribution |
| `get_page_content` | Fetch and extract clean text from a URL |
| `find_vocabulary` | Look up word meaning, examples, and pronunciation |

---

## Running the Tests

```powershell
# Fast offline tests — unit + safety (no API calls, ~15 seconds)
python -m pytest brain\tests\unit brain\tests\safety -v

# MCP integration test — launches real MCP subprocesses (~15 seconds)
python -m pytest brain\tests\integration\test_mcp_connections.py -v

# Voice pipeline test — loads Kokoro locally, mocks DeepSeek (~3 min first run)
python -m pytest brain\tests\integration\test_voice_pipeline.py -v

# Live DeepSeek API test — uses real API credits (opt-in only)
$env:LIVE_TEST = "1"
python -m pytest brain\tests\integration\test_deepseek.py::test_deepseek_live_call -v

# Full suite
python -m pytest brain\tests -v
```

**Test results:** 54 passed · 1 skipped (live API opt-in) · 100% offline passing (55 total)

---

## Security

- 🔒 `.env` is git-ignored — credentials never touch version control
- 🔒 API keys are **regex-redacted** in all log output
- 🔒 API keys are **never passed** to MCP child processes as environment variables
- 🔒 Retrieved web content is **sanitized** before entering LLM context (prompt injection neutralization)
- 🔒 Tool calls are validated against a registered allowlist — unknown tools are rejected
- 🔒 Tool string arguments are bounded at 20,000 characters (anti context-stuffing)

---

## Diagnostics

```powershell
# Pre-launch environment check
python brain\scripts\preflight.py

# Active health check (probes DeepSeek API + MCP servers + TTS)
python brain\scripts\health_check.py
```

---

## Troubleshooting

### `ModuleNotFoundError: No module named 'jarvis_brain'`
The package isn't installed yet:
```powershell
pip install -e brain
```

### `ModuleNotFoundError: No module named 'notes_server'` or `web_search_server`
```powershell
pip install -e mcpservers\notes
pip install -e mcpservers\web_search
```

### PowerShell script execution error
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
.venv\Scripts\Activate.ps1
```

### `UndefinedTable: relation "checkpoints" does not exist`
```powershell
python brain\scripts\setup_checkpointer.py
```

### Kokoro TTS slow on first launch
Kokoro-82M weights download from Hugging Face on first use. Pre-cache them:
```powershell
python brain\scripts\setup_models.py
```

### Microphone not detected
Check **Windows Settings → System → Sound → Input device**. Then run:
```powershell
python brain\scripts\preflight.py
```

### DeepSeek API authentication error
Verify `DeepSeek_api=sk-...` is set correctly in your root `.env`. Then:
```powershell
python brain\scripts\health_check.py
```

---

## Configuration

All tuneable settings live in `brain/configs/`. No Python editing required for common changes.

**`brain/configs/brain.yaml`** — reasoning and memory:
```yaml
agent:
  temperature: 0.7        # Response creativity (0.0 = deterministic)
  max_tool_steps: 6       # Max MCP tool calls per turn
  timeout_seconds: 30.0   # DeepSeek request timeout
  readiness_check: true   # Ping DeepSeek at startup

memory:
  thread_id: "jarvis_main_session"
  checkpointer_type: "postgres"  # or "memory" for no-DB mode
  max_history_messages: 20
```

**`brain/configs/voice.yaml`** — speech and audio:
```yaml
tts:
  voice: "af_heart"   # Kokoro voice: af_heart, af_bella, af_sarah, am_adam...
  speed: 1.0          # Speech rate (0.5 = slow, 2.0 = fast)
  device: "cpu"
```

---

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Make changes and run tests: `python -m pytest brain\tests\unit brain\tests\safety -v`
4. Commit: `git commit -m "feat: describe your change"`
5. Push and open a Pull Request

---

## License

MIT License — see [LICENSE](LICENSE) for details.

---

<div align="center">
Built with ❤️ for learning, vocabulary building, and personal growth.<br/>
<em>JARVIS listens, learns, and helps you grow.</em>
</div>

