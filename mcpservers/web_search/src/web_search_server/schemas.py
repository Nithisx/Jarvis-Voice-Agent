"""Pydantic input validation models and response schemas for Web Search MCP Server."""

from __future__ import annotations

import ipaddress
import re
from typing import Any, Literal, Optional
from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator

from web_search_server.exceptions import ValidationError

SearchDepth = Literal["basic", "advanced"]
SearchTopic = Literal["general", "news"]
TimeRange = Literal["day", "week", "month", "year"]
DifficultyLevel = Literal["beginner", "intermediate", "advanced"]


def validate_public_http_url(url_str: str) -> str:
    """Validate that a URL is an absolute HTTP or HTTPS URL pointing to a public host.

    Rejects unsupported schemes (file:, javascript:, data:, ftp:), localhost,
    private RFC-1918 subnets, and cloud metadata services (169.254.169.254).
    """
    if not isinstance(url_str, str) or not url_str.strip():
        raise ValidationError("URL must be a non-empty string.")

    cleaned_url = url_str.strip()
    try:
        parsed = urlparse(cleaned_url)
    except Exception as exc:
        raise ValidationError(f"Invalid URL structure: {exc}") from exc

    if parsed.scheme.lower() not in ("http", "https"):
        raise ValidationError(
            f"Unsupported URL scheme '{parsed.scheme}'. Only 'http' and 'https' are allowed."
        )

    hostname = parsed.hostname
    if not hostname:
        raise ValidationError("URL must include a valid hostname.")

    hostname_lower = hostname.lower()

    # Reject localhost and common local aliases
    if hostname_lower in ("localhost", "localhost.localdomain", "127.0.0.1", "::1", "0.0.0.0"):
        raise ValidationError(f"Access to local loopback address '{hostname}' is forbidden.")

    # Check for IP address literals to reject private/link-local/metadata ranges
    is_ip = False
    try:
        ip = ipaddress.ip_address(hostname_lower)
        is_ip = True
    except ValueError:
        # Not an IP literal; it's a domain name
        if hostname_lower.endswith((".local", ".internal", ".localhost")):
            raise ValidationError(f"Access to internal domain '{hostname}' is forbidden.")

    if is_ip:
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved:
            raise ValidationError(f"Access to private/internal IP address '{hostname}' is forbidden.")
        if str(ip) == "169.254.169.254":
            raise ValidationError("Access to cloud metadata service is forbidden.")

    return cleaned_url


class SearchWebInput(BaseModel):
    query: str = Field(..., min_length=1, max_length=500, description="Information query to search for.")
    search_depth: SearchDepth = Field("basic", description="Search depth: 'basic' (fast) or 'advanced' (thorough).")
    topic: SearchTopic = Field("general", description="Search category: 'general' or 'news'.")
    max_results: int = Field(5, ge=1, le=10, description="Number of results to return (1-10).")
    time_range: Optional[TimeRange] = Field(None, description="Time filter: 'day', 'week', 'month', or 'year'.")
    include_domains: Optional[list[str]] = Field(None, description="Domains to prioritize or restrict to.")
    exclude_domains: Optional[list[str]] = Field(None, description="Domains to exclude from results.")
    include_raw_content: bool = Field(False, description="Whether to include cleaned full raw content.")

    @field_validator("query", mode="before")
    @classmethod
    def strip_query(cls, v: Any) -> str:
        if isinstance(v, str):
            v = v.strip()
            if not v:
                raise ValueError("Query must not be empty or whitespace only.")
        return v

    @field_validator("include_domains", "exclude_domains", mode="before")
    @classmethod
    def clean_domains(cls, v: Any) -> Optional[list[str]]:
        if v is None:
            return None
        if isinstance(v, list):
            cleaned = [str(d).strip().lower() for d in v if str(d).strip()]
            return cleaned if cleaned else None
        return None


class GetPageContentInput(BaseModel):
    url: str = Field(..., description="Absolute HTTP or HTTPS URL of the web page to extract.")
    max_characters: int = Field(
        12000,
        ge=100,
        le=20000,
        description="Maximum characters of extracted text to return (100 - 20000).",
    )

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        return validate_public_http_url(v)


class FindVocabularyInput(BaseModel):
    topic: str = Field(..., min_length=1, max_length=200, description="Topic, theme, or conversational situation.")
    level: DifficultyLevel = Field("intermediate", description="Target difficulty: beginner, intermediate, or advanced.")
    count: int = Field(5, ge=1, le=10, description="Number of vocabulary entries to discover (1-10).")
    include_idioms: bool = Field(True, description="Whether to include relevant English idioms.")
    include_phrasal_verbs: bool = Field(True, description="Whether to include phrasal verbs.")
    context: Optional[str] = Field(None, description="Specific context (e.g. office meetings, interview, storytelling).")

    @field_validator("topic", mode="before")
    @classmethod
    def strip_topic(cls, v: Any) -> str:
        if isinstance(v, str):
            v = v.strip()
            if not v:
                raise ValueError("Topic must not be empty or whitespace only.")
        return v


class SearchResultItem(BaseModel):
    title: str
    url: str
    content: str
    published_date: Optional[str] = None
    score: Optional[float] = None
    raw_content: Optional[str] = None


class SearchWebResponse(BaseModel):
    success: bool
    query: str
    total_results: int
    results: list[SearchResultItem]
    message: Optional[str] = None


class PageContentResponse(BaseModel):
    success: bool
    url: str
    canonical_url: Optional[str] = None
    title: Optional[str] = None
    content: str
    character_count: int
    truncated: bool
    retrieval_metadata: dict[str, Any] = Field(default_factory=dict)


class VocabularyItem(BaseModel):
    word: str
    word_type: Optional[str] = None
    meaning: str
    example_sentence: str
    synonyms: list[str] = Field(default_factory=list)
    source_url: str
    difficulty: str
    difficulty_note: str = "Estimated level based on search context"
    example_source_type: str = "source_grounded"


class FindVocabularyResponse(BaseModel):
    success: bool
    topic: str
    level: str
    count: int
    items: list[VocabularyItem]
    instructions: str = (
        "Vocabulary discovered from web resources. Save to Notes MCP server "
        "if revision tracking is desired."
    )
