"""Main CLI entrypoint for the JARVIS Voice-to-Voice Assistant."""

from __future__ import annotations

import argparse
import asyncio
import os
import sys

from jarvis_brain.config import get_config
from jarvis_brain.lifecycle import jarvis_lifecycle
from jarvis_brain.observability.logging import get_logger, setup_logging

logger = get_logger("main")


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        prog="jarvis",
        description="JARVIS - Production Voice-to-Voice AI Assistant",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging output",
    )
    parser.add_argument(
        "--skip-readiness",
        action="store_true",
        help="Skip the DeepSeek API ping check at startup",
    )
    return parser.parse_args()


def configure_event_loop() -> None:
    """Configure platform-specific event loop policy."""
    if sys.platform == "win32":
        # Required on Windows for psycopg and asyncio subprocesses
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


def main() -> None:
    """Main execution function."""
    args = parse_args()

    configure_event_loop()

    # Load configuration
    config = get_config()
    if args.debug:
        config.log_level = "DEBUG"
    if args.skip_readiness:
        config.readiness_check = False

    setup_logging(config.log_level)

    try:
        asyncio.run(jarvis_lifecycle.run())
    except KeyboardInterrupt:
        logger.info("Process interrupted by user. Exiting cleanly.")
    except Exception as exc:
        logger.error("JARVIS encountered an unhandled exception: %s", exc, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()

