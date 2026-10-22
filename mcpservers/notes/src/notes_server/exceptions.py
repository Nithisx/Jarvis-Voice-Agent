"""Custom exceptions for Notes MCP Server."""


class NotesMCPError(Exception):
    """Base exception for all Notes MCP server errors."""

    def __init__(self, message: str, details: dict | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class ConfigurationError(NotesMCPError):
    """Raised when environment or database configuration is missing or invalid."""
    pass


class DatabaseConnectionError(NotesMCPError):
    """Raised when the PostgreSQL database cannot be reached or connection fails."""
    pass


class DatabaseQueryError(NotesMCPError):
    """Raised when a database query fails execution."""
    pass


class RecordNotFoundError(NotesMCPError):
    """Raised when a requested note or vocabulary entry does not exist."""
    pass


class DuplicateRecordError(NotesMCPError):
    """Raised when a duplicate unique record is detected."""
    pass


class ValidationError(NotesMCPError):
    """Raised when input parameters fail domain or schema validation."""
    pass

