"""Configuration management for JARVIS Voice-to-Voice Agent.

Resolves project root, discovers credentials from root `.env` securely,
and loads YAML configurations.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from jarvis_brain.exceptions import ConfigurationError


def find_project_root() -> Path:
    """Find the project root by locating the directory containing .env and mcpservers."""
    candidates = [
        Path.cwd(),
        Path(__file__).resolve().parent,
        Path(__file__).resolve().parent.parent,
        Path(__file__).resolve().parent.parent.parent,
        Path(__file__).resolve().parent.parent.parent.parent,
    ]

    for start in candidates:
        current = start
        while current != current.parent:
            if (current / ".env").is_file() and (current / "mcpservers").is_dir():
                return current
            if (current / ".env").is_file():
                return current
            current = current.parent

    # Fallback to current working directory
    return Path.cwd()


def parse_env_file(env_path: Path) -> dict[str, str]:
    """Parse a .env file into key-value pairs without using external libraries."""
    env_vars: dict[str, str] = {}
    if not env_path.is_file():
        return env_vars

    try:
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, val = line.split("=", 1)
                    key = key.strip()
                    val = val.strip().strip("'\"")
                    if key:
                        env_vars[key] = val
    except Exception as exc:
        raise ConfigurationError(f"Failed to read .env file at {env_path}: {exc}") from exc

    return env_vars


def load_yaml_file(yaml_path: Path) -> dict[str, Any]:
    """Safely load a YAML configuration file."""
    if not yaml_path.is_file():
        return {}
    try:
        import yaml
        with open(yaml_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except ImportError:
        # Fallback basic parser for simple key-value YAML if PyYAML is not yet ready
        result: dict[str, Any] = {}
        with open(yaml_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and ":" in line:
                    k, v = line.split(":", 1)
                    result[k.strip()] = v.strip().strip("'\"")
        return result
    except Exception as exc:
        raise ConfigurationError(f"Failed to parse YAML file at {yaml_path}: {exc}") from exc


@dataclass(frozen=True)
class JarvisConfig:
    project_root: Path
    # DeepSeek credentials and settings
    deepseek_api_key: str
    deepseek_model: str = "deepseek-chat"
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_timeout: float = 30.0
    deepseek_temperature: float = 0.7
    max_tool_steps: int = 6
    readiness_check: bool = True

    # Database & Storage
    database_url: Optional[str] = None
    thread_id: str = "jarvis_main_session"
    checkpointer_type: str = "postgres"
    max_history_messages: int = 20

    # Tavily
    tavily_api_key: Optional[str] = None

    # STT & TTS
    stt_model_arch: int = 2
    stt_language: str = "en"
    tts_voice: str = "af_heart"
    tts_speed: float = 1.0
    tts_device: str = "cpu"
    tts_sample_rate: int = 24000
    greeting_phrase: str = (
        "Welcome back, Nithish! It's good to have you here. I'm ready to chat, "
        "explore something interesting, and help you practise your communication skills. "
        "What's on your mind today?"
    )
    interaction_mode: str = "half_duplex"
    log_level: str = "INFO"

    # Wake word and silence endpointing
    wake_word_enabled: bool = True
    wake_phrases: list[str] = field(default_factory=lambda: ["hey jarvis", "jarvis"])
    silence_timeout_seconds: float = 3.0
    energy_threshold: float = 0.015
    partial_eval_interval: float = 0.5
    max_turn_seconds: float = 30.0

    # Command queue
    command_queue_max_size: int = 5

    # Streaming & synthesis
    llm_streaming: bool = False
    full_response_synthesis: bool = True
    max_response_chars: int = 4000

    def has_database(self) -> bool:
        """Return True if a non-empty PostgreSQL database URL is configured."""
        return bool(self.database_url and self.database_url.strip())

    def has_deepseek_key(self) -> bool:
        """Return True if a valid DeepSeek API key is present."""
        return bool(self.deepseek_api_key and self.deepseek_api_key.strip())


_CONFIG_CACHE: Optional[JarvisConfig] = None


def get_config(reload: bool = False) -> JarvisConfig:
    """Load, validate, and cache the unified JARVIS configuration."""
    global _CONFIG_CACHE
    if reload:
        _CONFIG_CACHE = None
    if _CONFIG_CACHE is not None:
        return _CONFIG_CACHE

    root = find_project_root()
    env_file = root / ".env"
    env_vars = parse_env_file(env_file)

    # 1. Resolve DeepSeek API Key
    deepseek_key = (
        os.environ.get("DeepSeek_api")
        or os.environ.get("deepseek_api_key")
        or env_vars.get("DeepSeek_api")
        or env_vars.get("deepseek_api_key")
    )

    if not deepseek_key or not deepseek_key.strip():
        raise ConfigurationError(
            "Missing DeepSeek API key. Please ensure 'DeepSeek_api' (or 'deepseek_api_key') "
            "is defined in the root .env file or environment variables."
        )

    # 2. Resolve DeepSeek Model
    # Check .env variable (user has 'model = deepseek-flash' or 'DEEPSEEK_MODEL')
    model_name = (
        os.environ.get("DEEPSEEK_MODEL")
        or os.environ.get("model")
        or env_vars.get("DEEPSEEK_MODEL")
        or env_vars.get("model")
        or "deepseek-chat"
    ).strip()

    # DeepSeek official endpoint model names are deepseek-chat and deepseek-reasoner.
    # If set to deepseek-flash or similar custom string, deepseek-chat is the standard alias.
    if model_name.lower() in ("deepseek-flash", "deepseek_flash"):
        # deepseek-chat supports function calling and fast chat completions
        model_name = "deepseek-chat"

    # 3. Resolve PostgreSQL Connection
    db_url = (
        os.environ.get("DATABASE_URL")
        or env_vars.get("DATABASE_URL")
    )

    # 4. Resolve Tavily API Key
    tavily_key = (
        os.environ.get("TAVILY_API_KEY")
        or os.environ.get("tavily_api_key")
        or env_vars.get("TAVILY_API_KEY")
        or env_vars.get("tavily_api_key")
    )

    # 5. Load YAML configs if present
    configs_dir = root / "brain" / "configs"
    brain_yaml = load_yaml_file(configs_dir / "brain.yaml")
    voice_yaml = load_yaml_file(configs_dir / "voice.yaml")

    agent_cfg = brain_yaml.get("agent", {})
    memory_cfg = brain_yaml.get("memory", {})
    obs_cfg = brain_yaml.get("observability", {})

    stt_cfg = voice_yaml.get("stt", {})
    tts_cfg = voice_yaml.get("tts", {})
    interaction_cfg = voice_yaml.get("interaction", {})
    wake_cfg = voice_yaml.get("wake_word", {})
    queue_cfg = voice_yaml.get("queue", {})
    playback_cfg = voice_yaml.get("playback", {})

    _CONFIG_CACHE = JarvisConfig(
        project_root=root,
        deepseek_api_key=deepseek_key.strip(),
        deepseek_model=model_name,
        deepseek_base_url=agent_cfg.get("api_base_url", "https://api.deepseek.com"),
        deepseek_timeout=float(agent_cfg.get("timeout_seconds", 30.0)),
        deepseek_temperature=float(agent_cfg.get("temperature", 0.7)),
        max_tool_steps=int(agent_cfg.get("max_tool_steps", 6)),
        readiness_check=bool(agent_cfg.get("readiness_check", True)),
        database_url=db_url.strip() if db_url else None,
        thread_id=memory_cfg.get("thread_id", "jarvis_main_session"),
        checkpointer_type=memory_cfg.get("checkpointer_type", "postgres"),
        max_history_messages=int(memory_cfg.get("max_history_messages", 20)),
        tavily_api_key=tavily_key.strip() if tavily_key else None,
        stt_model_arch=int(stt_cfg.get("model_arch", 2)),
        stt_language=stt_cfg.get("language", "en"),
        tts_voice=tts_cfg.get("voice", "af_heart"),
        tts_speed=float(tts_cfg.get("speed", 1.0)),
        tts_device=tts_cfg.get("device", "cpu"),
        tts_sample_rate=int(tts_cfg.get("sample_rate", 24000)),
        greeting_phrase=interaction_cfg.get(
            "greeting",
            "Welcome back, Nithish! It's good to have you here. I'm ready to chat, "
            "explore something interesting, and help you practise your communication skills. "
            "What's on your mind today?",
        ),
        interaction_mode=interaction_cfg.get("mode", "half_duplex"),
        log_level=obs_cfg.get("log_level", "INFO"),
        wake_word_enabled=bool(wake_cfg.get("enabled", True)),
        wake_phrases=list(wake_cfg.get("wake_phrases", ["hey jarvis", "jarvis"])),
        silence_timeout_seconds=float(wake_cfg.get("silence_timeout_seconds", 3.0)),
        energy_threshold=float(wake_cfg.get("energy_threshold", 0.015)),
        partial_eval_interval=float(wake_cfg.get("partial_eval_interval", 0.5)),
        max_turn_seconds=float(wake_cfg.get("max_turn_seconds", 30.0)),
        command_queue_max_size=int(queue_cfg.get("max_size", 5)),
        llm_streaming=bool(agent_cfg.get("streaming", False)),
        full_response_synthesis=bool(playback_cfg.get("full_response_synthesis", True)),
        max_response_chars=int(playback_cfg.get("max_response_chars", 4000)),
    )
    return _CONFIG_CACHE


def get_masked_deepseek_key() -> str:
    """Return a masked representation of the DeepSeek API key for safe display."""
    try:
        cfg = get_config()
        k = cfg.deepseek_api_key
        if len(k) <= 8:
            return "sk-****"
        return f"{k[:5]}...{k[-4:]}"
    except Exception:
        return "<unconfigured-or-hidden>"


def get_masked_db_url() -> str:
    """Return a masked representation of the PostgreSQL connection string."""
    try:
        cfg = get_config()
        if not cfg.database_url:
            return "<none>"
        return re.sub(r"(://[^:]+:)([^@]+)(@)", r"\1*****\3", cfg.database_url)
    except Exception:
        return "<unconfigured-or-hidden>"


def clear_config_cache() -> None:
    """Clear cached configuration for test isolation."""
    global _CONFIG_CACHE
    _CONFIG_CACHE = None
