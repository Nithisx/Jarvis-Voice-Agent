# JARVIS — Voice-to-Voice Personal AI Assistant

JARVIS is a production-grade, **voice-first** AI assistant running entirely on your local Windows machine (Ryzen CPU, no NVIDIA GPU required). Say something; JARVIS listens, reasons using DeepSeek, optionally calls your Notes or Web Search tools, and speaks back using local Kokoro-82M text-to-speech — all in real time.

---

## Architecture

```
Microphone
    │  (PortAudio Audio Frames)
    ▼
SpeechToTextService (Speach2text.py / Moonshine Tiny Streaming)
    │  • Real-time RMS Frame Energy Calculation (VAD)
    │  • Continuous Local Transcription (no cloud, CPU)
    │  • Cumulative Partial Transcript Reconciliation
    ▼
SpeechInputManager (Local Wake-Word & Silence Endpointing Gate)
    │  • Wake Phrases: "Hey Jarvis", "Jarvis" (Regex boundary, case-insensitive)
    │  • 3.0s Silence Endpoint Monitor (0 API calls for background talk or empty wake words)
    │  • Wake-word stripped, command capitalized
    ▼
CommandQueue (Bounded FIFO asyncio.Queue, Capacity = 5)
    │  • Non-blocking capture while agent is reasoning or calling tools
    │  • Sequential execution per conversation thread
    ▼
VoiceLoop Worker
    │
    ▼
LangGraph StateGraph  (JARVIS Brain) ────────────────────────────────────────┐
    │                                                                        │
    ├── DeepSeek API (deepseek-chat, streaming: false)                      │
    │      reasoning_node → should_continue? ──► tools_node                 │
    │                              ▲                  │                      │
    │                              └──────────────────┘                      │
    │                                (tool loop, max 6 steps)                │
    │                                                                        │
    ├── MCP Client Manager (stdio subprocess)                                │
    │      ├── Notes MCP Server      (mcpservers/notes)                      │
    │      └── Web Search MCP Server (mcpservers/web_search)                 │
    │                                                                        │
    └── format_response_node → clean spoken text ◄──────────────────────────┘
              │  (Complete Final Answer)
              ▼
    Kokoro-82M TTS (synthesize_full_waveform)
              │  • Sentence segmentation & in-memory synthesis
              │  • Concatenation into a single continuous 1D float32 waveform (24kHz)
              │  • Amplitude normalization guard [-1.0, 1.0]
              ▼
    AudioOutputPlayer (Single continuous playback via sounddevice)
              │  • Microphone muted during playback + 300ms reverberation settle delay
              ▼
    Microphone unmuted → Resumes LISTENING_FOR_WAKE_WORD (Half-Duplex)
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
│           ├── wake_word.py        # Local wake-word gate ("Hey Jarvis", "Jarvis")
│           ├── state.py            # MicGateState and WorkerState models
│           ├── command_queue.py    # Bounded FIFO command queue (capacity 5)
│           ├── speech_input.py     # Moonshine VAD + cumulative partials + 3s silence gate
│           ├── tts_kokoro.py       # KokoroTTSService (full-waveform gapless synthesis)
│           ├── audio_output.py     # Thread-safe sounddevice player
│           ├── voice_loop.py       # Sequential turn-taking worker & queue consumer
│           ├── speech_formatter.py # Markdown → clean spoken text
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

| Suite | Count | External calls | Description |
|---|---|---|---|
| `unit/test_wake_word.py` | 7 tests | None | Regex boundaries, punctuation tolerance, case insensitivity |
| `unit/test_command_queue.py` | 3 tests | None | FIFO order, non-blocking overflow drop, metrics tracking |
| `unit/test_concurrency.py` | 3 tests | None | Concurrent command capture, error resilience, playback muting |
| `unit/test_full_synthesis.py` | 4 tests | None | Full-waveform concatenation, normalization guard, single playback |
| `unit/test_audio_pipeline.py` | 3 tests | None | Streaming disabled check, greeting speaks first, no partial leaks |
| `unit/test_speech_input.py` | 4 tests | None | RMS energy VAD, partial transcript wake detection, 3s silence endpointing |
| `unit/test_tts_kokoro.py` | 4 tests | None | Kokoro synthesis, empty string handling, mock pipeline, async speak |
| `unit/test_voice_loop.py` | 2 tests | None | Single turn execution, queue error recovery |
| `unit/test_graph.py` | 6 tests | None | LangGraph routing, tool cutoff, response formatting |
| `unit/test_config.py` | 4 tests | None | Config resolution, model mapping, key masking, DB URL |
| `unit/test_speech_formatter.py` | 4 tests | None | Markdown stripping, code block removal, sentence splitting |
| `safety/` | 6 tests | None | Prompt injection neutralization, tool authorization, argument bounds |
| `integration/test_mcp_connections.py` | 1 test | Stdio Subprocesses | Live Notes + Web Search MCP servers discovery & tool calls |
| `integration/test_deepseek.py` | 3 tests | Mocked (1 live opt-in) | Model parameter verification, mock readiness, live chat |
| `integration/test_voice_pipeline.py` | 1 test | Local Kokoro CPU | End-to-end simulated speech turn through Kokoro TTS |
| **Total** | **55 tests** | **54 passed, 1 skipped (live API opt-in)** | **100% offline passing** |

---

## Voice Pipeline Deep Dive

### 1. Local Wake-Word Gating (`Hey Jarvis`, `Jarvis`)
JARVIS uses on-device Moonshine Tiny Streaming for continuous transcription, but will **never invoke DeepSeek or external APIs** until a valid wake phrase is recognized.

- **Supported Wake Phrases:** `"Hey Jarvis"`, `"Jarvis"`.
- **Matching Rules:** Case-insensitive, robust to punctuation (`"Hey Jarvis!"`, `"jarvis,"`), word-boundary enforced (`\b`), and meta-mention filtered (e.g. *"the word jarvis"* does not trigger commands).
- **Phrase Stripping:** The wake phrase is automatically stripped from the transcribed text, and the remaining command is capitalized before passing to the LangGraph brain (e.g. *"Hey Jarvis, what time is it?"* → *"What time is it?"*).
- **Zero API Call Guarantee:** Ambient noise, casual conversations, or background chatter without a wake word are discarded completely locally. If a user says *"Hey Jarvis"* alone without any command, it resets after 3 seconds of silence without sending any request to DeepSeek.

### 2. 3-Second Silence Endpointing & RMS VAD
- **Real-Time VAD:** In `Speach2text.py`, the PortAudio input stream callback computes frame root-mean-square (RMS) energy (`np.sqrt(np.mean(in_data ** 2))`) in-place, without opening a secondary audio stream.
- **Transcript Reconciliation:** Moonshine's real-time partial updates and committed line tokens (`on_line`) are reconciled without word duplication.
- **Silence Timer:** Once a wake word is detected and command words begin streaming in, a 3.0-second background silence monitor tracks continuous silence below the energy threshold (`0.015`).
- Only when 3.0 consecutive seconds of actual silence elapse is the command finalized and dispatched to the command queue.

### 3. Full-Response Gapless Speech Synthesis
Token-by-token and sentence-by-sentence streaming into Kokoro creates awkward pauses and robotic cadence. JARVIS solves this by synthesizing the **complete response as a single continuous waveform**:

1. DeepSeek generates the full response with `streaming: false`.
2. LangGraph completes all tool iterations and outputs the final markdown-free text.
3. Kokoro-82M synthesizes all sentence chunks in memory into NumPy arrays.
4. All chunks are concatenated into a single 1D continuous array (`float32`, 24 kHz).
5. An amplitude normalization guard scales the waveform safely within `[-1.0, 1.0]` to prevent digital clipping.
6. The entire response is played back in a **single continuous call** to `sounddevice`, guaranteeing zero sentence gaps.

### 4. Command Queue & Half-Duplex Concurrency
- **Bounded FIFO Queue:** Uses an `asyncio.Queue` with a default capacity of 5 commands.
- **Concurrent Capture:** While JARVIS is actively reasoning with DeepSeek or waiting for MCP tools, the microphone remains unmuted so you can speak your next command. The command is captured, gated, and enqueued.
- **Sequential Execution:** The `VoiceLoop` worker consumes commands sequentially from the queue, maintaining conversation thread consistency in PostgreSQL.
- **Half-Duplex Playback Muting:** The microphone is muted strictly during Kokoro audio playback (plus a 300ms reverberation settle delay), completely preventing acoustic echo from re-triggering the assistant.
- **Queue Overflow Protection:** If the queue exceeds capacity 5, excess commands are dropped cleanly with a logged warning, preventing memory exhaustion.

### 5. State Architecture

JARVIS maintains two explicit, thread-safe state machines:

```
MicGateState:
  LISTENING_FOR_WAKE_WORD ──(wake phrase detected)──► CAPTURING_COMMAND
           ▲                                                  │
           │                                          (3s silence elapsed)
           │                                                  ▼
           └──────────────(audio playback finished)◄─── MUTED_FOR_PLAYBACK

WorkerState:
  IDLE ──► QUEUED ──► PROCESSING (LLM/MCP) ──► SPEAKING (TTS) ──► IDLE
                           │
                     (error occurred)
                           ▼
                      RECOVERING ──► IDLE
```

---

## Verification Procedures

### Verification 1: Background Chatter (Zero LLM API Calls)
1. Start JARVIS: `.\venv\Scripts\python.exe -m jarvis_brain.main`
2. Wait for the welcome greeting to play.
3. Speak normally without saying "Jarvis" (e.g., *"The weather is nice today, let's grab coffee"*).
4. **Observe:** The terminal shows Moonshine transcribing audio, but no command is dispatched, no LangGraph execution begins, and **zero calls are made to the DeepSeek API**.

### Verification 2: Wake Word & 3-Second Silence Endpointing
1. Speak: *"Hey Jarvis... what is the capital of France?"*
2. Pause and remain silent for 3 seconds.
3. **Observe:** At exactly 3.0 seconds of silence, JARVIS finalizes the command, DeepSeek processes *"What is the capital of France?"*, and Kokoro responds seamlessly.

### Verification 3: Gapless Audio Synthesis
1. Ask a multi-sentence question: *"Jarvis, tell me three facts about the moon."*
2. **Observe:** DeepSeek finishes generating the full response before audio plays. The synthesized voice speaks all three facts continuously with natural prosody and zero mid-sentence pauses.

### Verification 4: Concurrent Command Queueing
1. While JARVIS is reasoning on a complex query (or searching the web), speak: *"Jarvis, remind me to check email."*
2. **Observe:** The command is captured and placed in the FIFO queue (`Queue size: 1`). As soon as the current turn finishes speaking, JARVIS immediately processes the queued reminder.

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
  model_name: "deepseek-chat"
  api_base_url: "https://api.deepseek.com"
  temperature: 0.7         # DeepSeek sampling temperature
  max_tokens: 1024         # Output token limit per response
  max_tool_steps: 6        # Maximum MCP tool iterations per turn
  timeout_seconds: 30.0    # DeepSeek API request timeout
  readiness_check: true    # Probe DeepSeek at startup
  streaming: false         # Disabled for full-response continuous synthesis

memory:
  thread_id: "jarvis_main_session"
  checkpointer_type: "postgres"   # "postgres" or "memory"
  max_history_messages: 20

observability:
  log_level: "INFO"
  metrics_enabled: true
```

### `configs/voice.yaml`

```yaml
stt:
  model_arch: 2            # Moonshine Tiny Streaming architecture
  model_name: "moonshine/tiny-streaming"
  language: "en"

tts:
  model: "kokoro-82m"
  voice: "af_heart"        # Kokoro voice ID
  speed: 1.0
  device: "cpu"
  sample_rate: 24000
  language: "a"            # American English in Kokoro

interaction:
  mode: "half_duplex"      # Mic mutes during TTS playback (prevents feedback)
  auto_listen_after_greeting: true
  interruption_enabled: false

wake_word:
  enabled: true
  wake_phrases:
    - "hey jarvis"
    - "jarvis"
  silence_timeout_seconds: 3.0    # 3.0s silence to finalize spoken command
  energy_threshold: 0.015         # RMS frame energy threshold for VAD
  partial_eval_interval: 0.5
  max_turn_seconds: 30.0

queue:
  max_size: 5                     # FIFO command buffer capacity
  overflow_policy: "notify"       # Drop + notify on queue overflow

playback:
  full_response_synthesis: true   # Assemble 1D continuous waveform before playing
  max_response_chars: 4000
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

