"""Comprehensive preflight diagnostics script for JARVIS.

Verifies all hardware, OS, audio devices, environment variables,
MCP servers, models, and dependencies before launching.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Add project root and brain/src to path
project_root = Path(__file__).resolve().parent.parent.parent
brain_src = project_root / "brain" / "src"
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(brain_src))

from jarvis_brain.config import get_config, get_masked_deepseek_key


def check_python_environment() -> bool:
    print("[1] Python & OS Environment:")
    py_ver = sys.version.split()[0]
    print(f"    - Python Version: {py_ver}")
    print(f"    - Platform: {sys.platform}")
    if sys.version_info < (3, 10):
        print("    [FAIL] Python 3.10+ required.")
        return False
    print("    [PASS] Python version compatible.")
    return True


def check_audio_devices() -> bool:
    print("\n[2] Audio Hardware (Microphone & Speaker):")
    try:
        import sounddevice as sd

        devices = sd.query_devices()
        default_in = sd.default.device[0]
        default_out = sd.default.device[1]

        in_name = devices[default_in]["name"] if default_in is not None and default_in >= 0 else "None"
        out_name = devices[default_out]["name"] if default_out is not None and default_out >= 0 else "None"

        print(f"    - Default Input Device  (Mic): [{default_in}] {in_name}")
        print(f"    - Default Output Device (Spk): [{default_out}] {out_name}")

        if default_in is None or default_in < 0:
            print("    [WARN] No default microphone detected.")
        if default_out is None or default_out < 0:
            print("    [WARN] No default output speaker detected.")

        print("    [PASS] Audio device querying successful.")
        return True
    except Exception as exc:
        print(f"    [WARN] Audio device check warning: {exc}")
        return True


def check_configuration() -> bool:
    print("\n[3] Environment Configuration & Secrets:")
    config = get_config()
    print(f"    - Project Root: {config.project_root}")
    print(f"    - DeepSeek Key: {get_masked_deepseek_key()}")
    print(f"    - DeepSeek Model: {config.deepseek_model}")

    if not config.has_deepseek_key():
        print("    [FAIL] DeepSeek API key not found in root .env or environment!")
        return False

    tavily_key = os.environ.get("TAVILY_API_KEY", "")
    masked_tavily = f"{tavily_key[:4]}...{tavily_key[-4:]}" if len(tavily_key) >= 8 else ("Set" if tavily_key else "Missing")
    print(f"    - Tavily API Key: {masked_tavily}")

    db_url = config.database_url
    if db_url:
        masked_db = db_url.split("@")[-1] if "@" in db_url else "Configured"
        print(f"    - PostgreSQL: host={masked_db}")
    else:
        print("    - PostgreSQL: Not configured (In-Memory checkpointing will be used)")

    print("    [PASS] Required configuration present.")
    return True


def check_mcp_servers() -> bool:
    print("\n[4] MCP Server Packages:")
    notes_dir = project_root / "mcpservers" / "notes"
    web_dir = project_root / "mcpservers" / "web_search"

    notes_ok = (notes_dir / "pyproject.toml").is_file() and (notes_dir / "src" / "notes_server" / "server.py").is_file()
    web_ok = (web_dir / "pyproject.toml").is_file() and (web_dir / "src" / "web_search_server" / "server.py").is_file()

    print(f"    - Notes MCP Server: {'[PASS]' if notes_ok else '[FAIL]'} ({notes_dir})")
    print(f"    - Web Search MCP Server: {'[PASS]' if web_ok else '[FAIL]'} ({web_dir})")

    return notes_ok and web_ok


def check_local_models() -> bool:
    print("\n[5] Local AI Model Packages:")
    try:
        import kokoro
        import misaki
        print("    - Kokoro & Misaki: [PASS] installed.")
    except ImportError as e:
        print(f"    - Kokoro TTS: [FAIL] missing dependency {e}")
        return False

    try:
        from Speach2text import SpeechToTextService
        print("    - Moonshine Speech-to-Text: [PASS] available.")
    except ImportError as e:
        print(f"    - Moonshine STT: [FAIL] missing dependency {e}")
        return False

    return True


def main() -> None:
    print("=" * 60)
    print("             JARVIS PREFLIGHT SYSTEM VERIFICATION")
    print("=" * 60)

    results = [
        check_python_environment(),
        check_audio_devices(),
        check_configuration(),
        check_mcp_servers(),
        check_local_models(),
    ]

    print("\n" + "=" * 60)
    if all(results):
        print("PREFLIGHT PASSED: ALL SYSTEMS OPERATIONAL FOR JARVIS.")
        print("=" * 60)
        sys.exit(0)
    else:
        print("PREFLIGHT WARNINGS OR FAILURES DETECTED.")
        print("=" * 60)
        sys.exit(1)


if __name__ == "__main__":
    main()

