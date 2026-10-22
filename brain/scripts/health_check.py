"""Active diagnostic health check script for JARVIS subsystems."""

from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

# Add project root and brain/src to path
project_root = Path(__file__).resolve().parent.parent.parent
brain_src = project_root / "brain" / "src"
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(brain_src))

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from jarvis_brain.agent.deepseek_client import check_deepseek_readiness
from jarvis_brain.config import get_config
from jarvis_brain.mcp.client_manager import mcp_client_manager
from jarvis_brain.voice.tts_kokoro import tts_service


async def check_deepseek() -> bool:
    print("[1] Probing DeepSeek API...")
    start = time.perf_counter()
    try:
        ok = await check_deepseek_readiness()
        elapsed = time.perf_counter() - start
        if ok:
            print(f"    [PASS] DeepSeek responded in {elapsed:.2f}s.")
            return True
        else:
            print(f"    [FAIL] DeepSeek readiness returned False.")
            return False
    except Exception as exc:
        print(f"    [FAIL] DeepSeek check failed: {exc}")
        return False


async def check_mcps() -> bool:
    print("[2] Probing MCP Servers (Notes & Web Search)...")
    start = time.perf_counter()
    try:
        await mcp_client_manager.connect_all()
        tools = mcp_client_manager.get_all_tools()
        elapsed = time.perf_counter() - start
        print(f"    [PASS] Connected to MCP servers in {elapsed:.2f}s. Discovered {len(tools)} tools:")
        for t in tools:
            print(f"           - {t.name}: {t.description[:60]}...")
        await mcp_client_manager.close()
        return True
    except Exception as exc:
        print(f"    [FAIL] MCP connection check failed: {exc}")
        await mcp_client_manager.close()
        return False


async def check_tts() -> bool:
    print("[3] Testing Kokoro TTS audio generation...")
    start = time.perf_counter()
    try:
        tts_service.load()
        audio = await tts_service.synthesize_async("Diagnostic test sound.")
        elapsed = time.perf_counter() - start
        print(f"    [PASS] Synthesized {len(audio)} audio samples in {elapsed:.2f}s.")
        return True
    except Exception as exc:
        print(f"    [FAIL] TTS generation failed: {exc}")
        return False


async def main_async() -> int:
    print("=" * 60)
    print("             JARVIS ACTIVE HEALTH DIAGNOSTICS")
    print("=" * 60)

    results = []
    results.append(await check_tts())
    results.append(await check_mcps())
    results.append(await check_deepseek())

    print("\n" + "=" * 60)
    if all(results):
        print("ALL ACTIVE HEALTH CHECKS PASSED.")
        print("=" * 60)
        return 0
    else:
        print("SOME ACTIVE HEALTH CHECKS REPORTED FAILURES.")
        print("=" * 60)
        return 1


def main() -> None:
    code = asyncio.run(main_async())
    sys.exit(code)


if __name__ == "__main__":
    main()

