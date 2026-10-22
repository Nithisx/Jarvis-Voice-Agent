"""Structured logging configuration with automatic secret redaction for JARVIS."""

from __future__ import annotations

import logging
import re
import sys
from typing import Optional

# Regular expression patterns for sensitive values
_SECRET_PATTERNS = [
    re.compile(r"sk-[a-zA-Z0-9]{20,}", re.IGNORECASE),
    re.compile(r"tvly-[a-zA-Z0-9_-]{20,}", re.IGNORECASE),
    re.compile(r"(://[^:]+:)([^@]+)(@)", re.IGNORECASE),
]


class RedactingFormatter(logging.Formatter):
    """Logging formatter that redacts known API keys and credentials."""

    def format(self, record: logging.LogRecord) -> str:
        orig = super().format(record)
        redacted = orig
        for pattern in _SECRET_PATTERNS:
            if pattern.pattern.startswith("(://"):
                redacted = pattern.sub(r"\1*****\3", redacted)
            else:
                redacted = pattern.sub(r"[REDACTED_SECRET]", redacted)
        return redacted


def setup_logging(log_level: str = "INFO") -> None:
    """Configure root logger to output to stderr with secret redaction."""
    level = getattr(logging, log_level.upper(), logging.INFO)

    formatter = RedactingFormatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Replace existing handlers
    for h in root_logger.handlers[:]:
        root_logger.removeHandler(h)
    root_logger.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    """Get a named logger."""
    return logging.getLogger(f"jarvis.{name}")

