"""Database checkpointer initialization script for JARVIS.

Ensures the required LangGraph checkpointing tables are created in PostgreSQL.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Add project root and brain/src to path
project_root = Path(__file__).resolve().parent.parent.parent
brain_src = project_root / "brain" / "src"
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(brain_src))

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from jarvis_brain.config import get_config
from jarvis_brain.memory.checkpointer import checkpointer_manager


async def main_async() -> int:
    config = get_config()
    print("=" * 60)
    print("JARVIS LangGraph Checkpointer Setup")
    print("=" * 60)

    if not config.has_database():
        print("[INFO] No PostgreSQL DATABASE_URL configured.")
        print("[INFO] JARVIS will operate using in-memory checkpointing (MemorySaver).")
        return 0

    print(f"[INFO] Connecting to PostgreSQL at {config.database_url.split('@')[-1]}...")
    try:
        checkpointer = await checkpointer_manager.get_checkpointer()
        if hasattr(checkpointer, "setup"):
            print("[INFO] Running checkpointer.setup()...")
            await checkpointer.setup()
            print("[PASS] PostgreSQL checkpointing tables verified and ready.")
        else:
            print("[WARN] In-memory checkpointer in use.")
        return 0
    except Exception as exc:
        print(f"[ERROR] Failed to initialize PostgreSQL checkpointer: {exc}")
        print("[INFO] In-memory fallback will be used at runtime.")
        return 1
    finally:
        await checkpointer_manager.close()


def main() -> None:
    code = asyncio.run(main_async())
    sys.exit(code)


if __name__ == "__main__":
    main()

