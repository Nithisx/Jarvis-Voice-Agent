"""Custom exception hierarchy for the Web Search MCP Server."""

from __future__ import annotations

from typing import Any, Optional


class WebSearchMCPError(Exception):
    """Base exception for Web Search MCP Server."""

    def __init__(self, message: str, details: Optional[dict[str, Any]] = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class ConfigurationError(WebSearchMCPError):
    """Raised when environment or provider configuration is missing or invalid."""
    pass


class ValidationError(WebSearchMCPError, ValueError):
    """Raised when tool arguments, parameters, or URLs fail safety/domain validation."""
    pass


class TavilyProviderError(WebSearchMCPError):
    """Raised when an operation against the Tavily search provider fails."""
    pass


class TavilyAuthError(TavilyProviderError):
    """Raised when authentication with Tavily fails."""
    pass


class TavilyRateLimitError(TavilyProviderError):
    """Raised when Tavily rate limits or quota are exceeded."""
    pass


class TavilyTimeoutError(TavilyProviderError):
    """Raised when Tavily search or content extraction times out."""
    pass
