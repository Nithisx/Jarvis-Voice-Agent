"""Speech text formatting and normalization for Kokoro TTS audio generation."""

from __future__ import annotations

import re
from typing import Iterator


def clean_for_speech(text: str) -> str:
    """Format raw assistant text into clean, natural English suitable for TTS.

    Removes Markdown syntax, code blocks, raw URLs, emojis, and formatting artifacts.
    """
    if not text:
        return ""

    s = text.strip()

    # 1. Strip fenced code blocks entirely
    s = re.sub(r"```[\s\S]*?```", " [code block omitted] ", s)

    # 2. Strip inline backtick code
    s = re.sub(r"`([^`]+)`", r"\1", s)

    # 3. Clean markdown links: [label](url) -> label
    s = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", s)

    # 4. Clean standalone URLs: http(s)://... -> domain name
    def _url_repl(match: re.Match) -> str:
        url = match.group(0)
        # Extract domain like bbc.co.uk or wikipedia.org
        m = re.search(r"https?://(?:www\.)?([^/]+)", url)
        if m:
            domain = m.group(1).split(".")[0]
            return f"on {domain}"
        return "the website"

    s = re.sub(r"https?://\S+", _url_repl, s)

    # 5. Remove markdown bold, italic, strikethrough: **text**, *text*, ~~text~~
    s = re.sub(r"\*\*([^*]+)\*\*", r"\1", s)
    s = re.sub(r"\*([^*]+)\*", r"\1", s)
    s = re.sub(r"__([^_]+)__", r"\1", s)
    s = re.sub(r"_([^_]+)_", r"\1", s)
    s = re.sub(r"~~([^~]+)~~", r"\1", s)

    # 6. Convert markdown headers: # Header -> Header.
    s = re.sub(r"^#{1,6}\s+(.*)$", r"\1.", s, flags=re.MULTILINE)

    # 7. Convert bullet points: - item -> item.
    s = re.sub(r"^\s*[-*•]\s+", "", s, flags=re.MULTILINE)

    # 8. Remove common emojis and unusual non-ASCII symbols
    # Keep standard English punctuation and letters
    s = re.sub(r"[^\w\s.,!?'\";:()\-]", "", s)

    # 9. Normalize multiple whitespace and newlines into single spaces
    s = re.sub(r"\s+", " ", s).strip()

    return s


def split_into_sentences(text: str) -> list[str]:
    """Split cleaned text into individual speakable sentences."""
    cleaned = clean_for_speech(text)
    if not cleaned:
        return []

    # Split by sentence-ending punctuation (. ! ?) followed by whitespace or end of string
    sentence_end_pattern = re.compile(r"(?<=[.!?])\s+")
    parts = sentence_end_pattern.split(cleaned)

    sentences = [p.strip() for p in parts if p.strip()]
    return sentences if sentences else [cleaned]

