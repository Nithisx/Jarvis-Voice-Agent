"""Configuration management for Web Search MCP Server.

Discovers and loads the Tavily API key from the root `.env` file or process
environment without exposing secrets or altering existing configuration files.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from web_search_server.exceptions import ConfigurationError


def find_root_env_file() -> Optional[Path]:
    """Locate the root .env file by traversing upwards from the package root.

    Starts from this module's directory and working directory, walking up until
    a .env file containing the Tavily key or project markers is encountered.
    """
    # Explicit custom override takes precedence if configured
    custom_env = os.environ.get("WEB_SEARCH_ENV_FILE")
    if custom_env is not None:
        if custom_env and Path(custom_env).is_file():
            return Path(custom_env)
        return None

    candidates = [
        Path(__file__).resolve().parent,
        Path(__file__).resolve().parent.parent,
        Path(__file__).resolve().parent.parent.parent,
        Path(__file__).resolve().parent.parent.parent.parent,
        Path.cwd(),
    ]

    for start_dir in candidates:
        current = start_dir
        while current != current.parent:
            env_file = current / ".env"
            if env_file.is_file():
                try:
                    with open(env_file, "r", encoding="utf-8") as f:
                        for line in f:
                            if re.match(r"^\s*(TAVILY_API_KEY|tavily_api_key)\s*=", line, re.IGNORECASE):
                                return env_file
                except Exception:
                    pass
            current = current.parent

    custom_env = os.environ.get("WEB_SEARCH_ENV_FILE")
    if custom_env and Path(custom_env).is_file():
        return Path(custom_env)

    return None


def parse_env_file(env_path: Path) -> dict[str, str]:
    """Parse .env file into key-value pairs, stripping whitespace and quotes."""
    env_vars: dict[str, str] = {}
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


@dataclass(frozen=True)
class Settings:
    tavily_api_key: str
    timeout_seconds: float = 30.0
    max_results_limit: int = 10
    log_level: str = "INFO"


_SETTINGS_CACHE: Optional[Settings] = None


def get_settings() -> Settings:
    """Load settings from process environment and project root .env."""
    global _SETTINGS_CACHE
    if _SETTINGS_CACHE is not None:
        return _SETTINGS_CACHE

    # 1. Check process environment first (respecting runtime overrides)
    api_key = os.environ.get("TAVILY_API_KEY") or os.environ.get("tavily_api_key")

    # 2. If not found in process environment, inspect root .env
    if not api_key:
        env_path = find_root_env_file()
        if env_path:
            parsed = parse_env_file(env_path)
            api_key = parsed.get("TAVILY_API_KEY") or parsed.get("tavily_api_key")

    if not api_key or not api_key.strip():
        raise ConfigurationError(
            "Missing required Tavily API key. Please ensure 'TAVILY_API_KEY' (or 'tavily_api_key') "
            "is defined in the project root .env file or available in the environment variables."
        )

    timeout = float(os.environ.get("WEB_SEARCH_TIMEOUT_SECONDS", 30.0))
    max_results = int(os.environ.get("WEB_SEARCH_MAX_RESULTS_LIMIT", 10))
    log_level = os.environ.get("WEB_SEARCH_LOG_LEVEL", "INFO").upper()

    _SETTINGS_CACHE = Settings(
        tavily_api_key=api_key.strip(),
        timeout_seconds=timeout,
        max_results_limit=max_results,
        log_level=log_level,
    )
    return _SETTINGS_CACHE


def get_tavily_api_key() -> str:
    """Retrieve raw Tavily API key securely."""
    return get_settings().tavily_api_key


def get_masked_api_key() -> str:
    """Return a masked representation of the API key for safe diagnostic logging."""
    try:
        key = get_tavily_api_key()
        if len(key) <= 8:
            return "tvly-****"
        return f"{key[:5]}...{key[-4:]}"
    except Exception:
        return "<unconfigured-or-hidden>"


def clear_settings_cache() -> None:
    """Clear cached settings (useful for isolated testing)."""
    global _SETTINGS_CACHE
    _SETTINGS_CACHE = None
