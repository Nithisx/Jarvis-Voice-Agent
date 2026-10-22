"""Unit tests for local wake-word detection and command extraction."""

import pytest

from jarvis_brain.voice.wake_word import WakeWordDetector, default_wake_detector


def test_standard_wake_phrases():
    """Verify all specification examples extract the expected command."""
    cases = [
        ("Hey Jarvis, create a note to buy milk.", "Create a note to buy milk."),
        ("Jarvis, what's on my notes?", "What's on my notes?"),
        ("hey, jarvis can you tell me a story", "Can you tell me a story"),
        ("I was speaking to my friend.", None),
        ("I like large cars.", None),
        ("Hey Jarvis", None),
        ("The word jarvis is part of a discussion, with no following command.", None),
        ("Hello, unrelated speech. Hey Jarvis, search for vocabulary.", "Search for vocabulary."),
    ]
    for inp, expected in cases:
        result = default_wake_detector.extract_command(inp)
        assert result == expected, f"Failed for input {inp!r}: got {result!r}, expected {expected!r}"


def test_case_insensitivity():
    """Verify wake phrases are matched regardless of casing."""
    assert default_wake_detector.extract_command("JARVIS, read my notes") == "Read my notes"
    assert default_wake_detector.extract_command("hEy JaRvIs what time is it") == "What time is it"
    assert default_wake_detector.extract_command("jarvis find vocabulary for eloquent") == "Find vocabulary for eloquent"


def test_punctuation_tolerance():
    """Verify punctuation variations (commas, colons, hyphens) are tolerated."""
    assert default_wake_detector.extract_command("Hey, Jarvis: save a note") == "Save a note"
    assert default_wake_detector.extract_command("Hey - Jarvis, tell me a joke") == "Tell me a joke"
    assert default_wake_detector.extract_command("Jarvis! What is the weather?") == "What is the weather?"


def test_no_match_inside_larger_words():
    """Verify word boundaries prevent matching inside larger words."""
    assert default_wake_detector.extract_command("This is a disjarvis device") is None
    assert default_wake_detector.extract_command("They were jarvising all afternoon") is None


def test_wake_phrase_only_with_punctuation():
    """Verify wake phrases followed only by punctuation yield no command."""
    assert default_wake_detector.extract_command("Hey Jarvis?") is None
    assert default_wake_detector.extract_command("Jarvis...") is None
    assert default_wake_detector.extract_command("   Hey Jarvis!   ") is None


def test_has_wake_word_predicate():
    """Verify has_wake_word returns True only when an actual addressing wake word is present."""
    assert default_wake_detector.has_wake_word("Hey Jarvis") is True
    assert default_wake_detector.has_wake_word("Jarvis, look here") is True
    assert default_wake_detector.has_wake_word("Good morning everyone") is False
    assert default_wake_detector.has_wake_word("The word jarvis is interesting") is False


def test_custom_wake_phrases():
    """Verify configurable wake phrases can be added."""
    custom_detector = WakeWordDetector(["computer", "ok computer"])
    assert custom_detector.extract_command("Computer, turn on the lights") == "Turn on the lights"
    assert custom_detector.extract_command("Ok computer, play music") == "Play music"
    assert custom_detector.extract_command("Hey Jarvis, do something") is None

