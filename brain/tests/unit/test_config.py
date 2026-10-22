"""Unit tests for JARVIS configuration loading and secret handling."""

import os
from unittest.mock import patch

import pytest

from jarvis_brain.config import JarvisConfig, clear_config_cache, get_config, get_masked_deepseek_key


def test_config_resolution():
    """Verify that configuration locates root .env and resolves project root correctly."""
    config = get_config(reload=True)
    assert config.project_root.is_dir()
    assert (config.project_root / "Speech2text.py").is_file() or (config.project_root / "Speach2text.py").is_file()


def test_deepseek_key_masking():
    """Verify secrets are redacted and never logged or exposed in full."""
    with patch.dict(os.environ, {"DeepSeek_api": "sk-test1234567890abcdef"}):
        config = get_config(reload=True)
        masked = get_masked_deepseek_key()
        assert "sk-test1234567890abcdef" not in masked
        assert masked.startswith("sk-te")
        assert masked.endswith("cdef")


def test_model_alias_mapping():
    """Verify deepseek-flash is mapped to deepseek-chat for the API."""
    with patch.dict(os.environ, {"model": "deepseek-flash"}):
        config = get_config(reload=True)
        assert config.deepseek_model == "deepseek-chat"

    with patch.dict(os.environ, {"model": "deepseek-reasoner"}):
        config = get_config(reload=True)
        assert config.deepseek_model == "deepseek-reasoner"


def test_database_url_handling():
    """Verify database URL detection."""
    with patch.dict(os.environ, {"DATABASE_URL": "postgresql://user:pass@localhost:5432/notes_db"}):
        config = get_config(reload=True)
        assert config.has_database() is True
        assert "localhost:5432" in config.database_url
