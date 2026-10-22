"""Unit tests for speech text formatting and sentence splitting."""

from jarvis_brain.voice.speech_formatter import clean_for_speech, split_into_sentences


def test_clean_markdown_formatting():
    """Verify markdown tags, bolding, code blocks, and bullets are cleaned for TTS."""
    raw = "Here is **bold** and *italic* text, along with `inline code` and [links](http://example.com)."
    cleaned = clean_for_speech(raw)
    assert "**" not in cleaned
    assert "*" not in cleaned
    assert "`" not in cleaned
    assert "http" not in cleaned
    assert "Here is bold and italic text, along with inline code and links." == cleaned


def test_clean_code_blocks():
    """Verify multiline code blocks are replaced with natural audio phrasing."""
    raw = "Here is the code:\n```python\nprint('hello')\n```\nLet me know what you think."
    cleaned = clean_for_speech(raw)
    assert "```" not in cleaned
    assert "print('hello')" not in cleaned
    assert "code block omitted" in cleaned


def test_sentence_splitting():
    """Verify sentences are split cleanly for streaming synthesis."""
    text = "Hello Nithish! How are you doing today? I am ready to help you."
    sentences = split_into_sentences(text)
    assert len(sentences) == 3
    assert sentences[0] == "Hello Nithish!"
    assert sentences[1] == "How are you doing today?"
    assert sentences[2] == "I am ready to help you."


def test_empty_text():
    """Verify empty or whitespace strings return empty list."""
    assert split_into_sentences("") == []
    assert split_into_sentences("   \n\t  ") == []
    assert clean_for_speech("") == ""
