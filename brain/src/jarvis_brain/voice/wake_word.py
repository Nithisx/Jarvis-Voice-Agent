"""Local Wake-Word Detection and Command Extraction.

Evaluates local transcripts to detect wake phrases, strips the wake phrase,
discards any preceding speech, and extracts normalized commands without
triggering external API calls.
"""

from __future__ import annotations

import re
from typing import Optional, Sequence

# Meta patterns where the wake word is mentioned as a noun, not an invocation
_META_WAKE_PATTERNS = [
    re.compile(r"\b(?:the\s+(?:word|name|phrase|term))\s+['\"]?hey\s+jarvis['\"]?", re.IGNORECASE),
    re.compile(r"\b(?:the\s+(?:word|name|phrase|term))\s+['\"]?jarvis['\"]?", re.IGNORECASE),
]


class WakeWordDetector:
    """Detects configurable wake words and extracts clean commands."""

    def __init__(self, wake_phrases: Optional[Sequence[str]] = None) -> None:
        self.wake_phrases = list(wake_phrases or ["hey jarvis", "jarvis"])
        # Sort phrases longest first so "hey jarvis" matches before "jarvis"
        self._sorted_phrases = sorted(self.wake_phrases, key=len, reverse=True)

    def _build_phrase_pattern(self, phrase: str) -> re.Pattern:
        """Compile a regex pattern for a wake phrase with word boundaries and flexible punctuation."""
        # Split tokens, e.g. "hey", "jarvis"
        tokens = [re.escape(tok) for tok in phrase.strip().split()]
        # Allow optional punctuation/spaces between tokens (e.g. "hey, jarvis" or "hey jarvis")
        token_sep = r"[\s,.-]+"
        pattern_str = r"\b" + token_sep.join(tokens) + r"\b"
        return re.compile(pattern_str, re.IGNORECASE)

    def has_wake_word(self, transcript: str) -> bool:
        """Check if transcript contains an addressing wake word (ignoring meta mentions)."""
        if not transcript or not transcript.strip():
            return False

        # First check if the only mention of jarvis is in a meta context like "the word jarvis"
        cleaned_text = transcript.strip()
        for meta_pat in _META_WAKE_PATTERNS:
            # If meta pattern matches and removing it leaves no other wake word
            cleaned_text = meta_pat.sub("", cleaned_text)

        for phrase in self._sorted_phrases:
            pattern = self._build_phrase_pattern(phrase)
            if pattern.search(cleaned_text):
                return True
        return False

    def extract_command(self, transcript: str) -> Optional[str]:
        """Extract the command following the first detected wake phrase.

        Discards any unrelated words preceding the wake phrase.
        Strips the wake phrase itself and returns the clean command.
        Returns None if no wake phrase is found, or if no command remains.
        """
        if not transcript or not transcript.strip():
            return None

        text = transcript.strip()

        # Check for meta mentions: e.g. "The word jarvis is part of a discussion..."
        for meta_pat in _META_WAKE_PATTERNS:
            # If a meta pattern is present at the occurrence, check if there's any invocation
            if meta_pat.search(text):
                # If the wake phrase only exists inside meta context, reject
                stripped_meta = meta_pat.sub("___META___", text)
                has_other = False
                for phrase in self._sorted_phrases:
                    pat = self._build_phrase_pattern(phrase)
                    if pat.search(stripped_meta):
                        has_other = True
                        break
                if not has_other:
                    return None

        # Search for the earliest matching wake phrase
        earliest_match: Optional[re.Match] = None
        for phrase in self._sorted_phrases:
            pattern = self._build_phrase_pattern(phrase)
            match = pattern.search(text)
            if match:
                if earliest_match is None or match.start() < earliest_match.start():
                    earliest_match = match

        if not earliest_match:
            return None

        # Extract everything after the wake phrase match
        remaining = text[earliest_match.end():].strip()

        # Strip leading punctuation commonly following names: ",", ":", "-", "."
        remaining = re.sub(r"^[\s,:\-\.\?!]+", "", remaining).strip()

        # Verify remaining text contains actual word characters (not just punctuation)
        if not remaining or not re.search(r"\w", remaining):
            return None

        # Capitalize the first letter for natural command formatting
        if len(remaining) > 1:
            clean_cmd = remaining[0].upper() + remaining[1:]
        else:
            clean_cmd = remaining.upper()

        return clean_cmd


# Default detector instance
default_wake_detector = WakeWordDetector()

