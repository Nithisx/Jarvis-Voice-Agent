"""Configuration management for Notes MCP Server.

Loads PostgreSQL connection settings securely from the root `.env` without
exposing credentials or modifying any files.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from notes_server.exceptions import ConfigurationError


def find_root_env_file() -> Optional[Path]:
    """Search for the root .env file by traversing parent directories.

    Starts from both the current working directory and the directory of this
    module, walking up until a .env file containing DATABASE_URL or a project root
    marker (e.g. .git, mcpservers) is found.
    """
    candidates = [
        Path.cwd(),
        Path(__file__).resolve().parent,
        Path(__file__).resolve().parent.parent,
        Path(__file__).resolve().parent.parent.parent,
        Path(__file__).resolve().parent.parent.parent.parent,
    ]

    for start_dir in candidates:
        current = start_dir
        # Traverse upwards to filesystem root
        while current != current.parent:
            env_file = current / ".env"
            if env_file.is_file():
                # Verify if it contains DATABASE_URL
                try:
                    with open(env_file, "r", encoding="utf-8") as f:
                        for line in f:
                            if re.match(r"^\s*DATABASE_URL\s*=", line):
                                return env_file
                except Exception:
                    pass
            current = current.parent

    # Fallback: check if an explicit ENV_FILE environment variable exists
    custom_env = os.environ.get("NOTES_ENV_FILE")
    if custom_env and Path(custom_env).is_file():
        return Path(custom_env)

    return None


def parse_env_file(env_path: Path) -> dict[str, str]:
    """Parse a .env file into key-value pairs, properly handling spaces and quotes."""
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
    database_url: str
    pool_min_size: int = 1
    pool_max_size: int = 10
    timeout_seconds: float = 10.0
    log_level: str = "INFO"


_SETTINGS_CACHE: Optional[Settings] = None


def get_settings() -> Settings:
    """Load and cache settings from environment and root .env."""
    global _SETTINGS_CACHE
    if _SETTINGS_CACHE is not None:
        return _SETTINGS_CACHE

    db_url = os.environ.get("DATABASE_URL")

    if not db_url:
        env_path = find_root_env_file()
        if env_path:
            parsed = parse_env_file(env_path)
            db_url = parsed.get("DATABASE_URL")

    if not db_url:
        raise ConfigurationError(
            "Missing required environment variable 'DATABASE_URL'. "
            "Please ensure DATABASE_URL=postgresql://user:password@host:port/dbname "
            "is defined in the project root .env or the system environment."
        )

    min_size = int(os.environ.get("NOTES_DB_POOL_MIN_SIZE", 1))
    max_size = int(os.environ.get("NOTES_DB_POOL_MAX_SIZE", 10))
    timeout = float(os.environ.get("NOTES_DB_TIMEOUT_SECONDS", 10.0))
    log_level = os.environ.get("NOTES_LOG_LEVEL", "INFO").upper()

    _SETTINGS_CACHE = Settings(
        database_url=db_url,
        pool_min_size=min_size,
        pool_max_size=max_size,
        timeout_seconds=timeout,
        log_level=log_level,
    )
    return _SETTINGS_CACHE


def get_database_url() -> str:
    """Retrieve raw database URL securely."""
    return get_settings().database_url


def get_masked_db_url() -> str:
    """Return a sanitized version of the database connection URL for diagnostics.

    Masks passwords and secret tokens.
    """
    try:
        url = get_database_url()
        # Mask password in postgresql://user:password@host:port/db
        masked = re.sub(r"(://[^:]+:)([^@]+)(@)", r"\1*****\3", url)
        return masked
    except Exception:
        return "<unconfigured-or-hidden>"

