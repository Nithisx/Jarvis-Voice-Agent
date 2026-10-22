"""Custom exceptions for the JARVIS Voice-to-Voice Assistant."""

from __future__ import annotations

from typing import Any, Optional


class JarvisError(Exception):
    """Base exception for all JARVIS brain errors."""

    def __init__(self, message: str, details: Optional[dict[str, Any]] = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class ConfigurationError(JarvisError):
    """Raised when environment or YAML configuration is missing or invalid."""
    pass


class DeepSeekError(JarvisError):
    """Base exception for DeepSeek API communication errors."""
    pass


class DeepSeekAuthError(DeepSeekError):
    """Raised when DeepSeek API authentication fails."""
    pass


class DeepSeekRateLimitError(DeepSeekError):
    """Raised when DeepSeek API quota or rate limits are exceeded."""
    pass


class DeepSeekTimeoutError(DeepSeekError):
    """Raised when a DeepSeek request times out."""
    pass


class MCPConnectionError(JarvisError):
    """Raised when connecting to or communicating with an MCP server fails."""
    pass


class MCPToolExecutionError(JarvisError):
    """Raised when an MCP tool invocation returns an unrecoverable failure."""
    pass


class STTError(JarvisError):
    """Raised when Moonshine speech-to-text encounters a hardware or model error."""
    pass


class TTSError(JarvisError):
    """Raised when Kokoro text-to-speech synthesis fails."""
    pass


class AudioOutputError(JarvisError):
    """Raised when speaker playback or audio output fails."""
    pass


class StateError(JarvisError):
    """Raised when LangGraph conversation state persistence encounters an error."""
    pass

