"""Startup greeting generator for JARVIS."""

from __future__ import annotations

from datetime import datetime
from jarvis_brain.config import get_config


def get_startup_greeting() -> str:
    """Generate the mandatory startup greeting for JARVIS.

    Must begin with the exact phrase: 'Welcome back, Nithish!'
    """
    config = get_config()
    # Default configured greeting
    base_greeting = config.greeting_phrase

    # Ensure it starts with the mandatory phrase
    mandatory_prefix = "Welcome back, Nithish!"
    if not base_greeting.startswith(mandatory_prefix):
        return f"{mandatory_prefix} It's good to have you here. I'm ready to chat, explore something interesting, and help you practise your communication skills. What's on your mind today?"

    return base_greeting

