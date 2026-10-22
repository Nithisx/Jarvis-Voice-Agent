"""Security, tool validation, and prompt injection defense policies."""

from __future__ import annotations

import re
from typing import Any, Optional

from jarvis_brain.exceptions import JarvisError
from jarvis_brain.observability.logging import get_logger

logger = get_logger("policies")

# Suspicious patterns in untrusted retrieved text that attempt to override system instructions
_INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?(previous|prior)\s+instructions", re.IGNORECASE),
    re.compile(r"system\s*:\s*you\s+are\s+now", re.IGNORECASE),
    re.compile(r"you\s+must\s+(now\s+)?act\s+as", re.IGNORECASE),
    re.compile(r"disregard\s+the\s+above", re.IGNORECASE),
]


class PolicyViolationError(JarvisError):
    """Raised when an operation violates security or safety policies."""
    pass


def sanitize_untrusted_content(text: str, source: str = "web") -> str:
    """Sanitize retrieved external text to protect against prompt injection."""
    if not text:
        return ""

    sanitized = text
    for pattern in _INJECTION_PATTERNS:
        if pattern.search(sanitized):
            logger.warning("Potential injection pattern detected and neutralized from source: %s", source)
            sanitized = pattern.sub("[Neutralized directive]", sanitized)

    # Cap maximum characters injected into prompt context to prevent context stuffing
    max_len = 12000
    if len(sanitized) > max_len:
        sanitized = sanitized[:max_len] + "... [Content truncated for safety]"

    return sanitized


def validate_tool_call_request(
    tool_name: str,
    tool_args: dict[str, Any],
    allowed_tools: set[str],
) -> None:
    """Validate that a requested tool call is authorized and arguments are bounded."""
    if tool_name not in allowed_tools:
        raise PolicyViolationError(f"Unauthorized tool call: '{tool_name}' is not in registered tools.")

    # Guard against oversized string arguments
    for k, v in tool_args.items():
        if isinstance(v, str) and len(v) > 20000:
            raise PolicyViolationError(f"Argument '{k}' exceeds maximum allowed length of 20000 characters.")

