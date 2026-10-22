"""Performance and latency metrics tracking for JARVIS voice-to-voice turns."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Optional

from jarvis_brain.observability.logging import get_logger

logger = get_logger("metrics")


@dataclass
class TurnMetrics:
    """Metrics recorded for a single voice-to-voice interaction turn."""
    turn_id: str
    user_transcript: str
    stt_duration_sec: float = 0.0
    llm_duration_sec: float = 0.0
    tool_calls_count: int = 0
    tools_duration_sec: float = 0.0
    tts_duration_sec: float = 0.0
    playback_duration_sec: float = 0.0
    total_latency_sec: float = 0.0
    created_at: float = field(default_factory=time.time)

    def log_summary(self) -> None:
        """Log a concise latency summary for the completed turn."""
        logger.info(
            "Turn [%s] completed in %.2fs | STT: %.2fs | LLM: %.2fs (%d tools, %.2fs) | TTS: %.2fs | Playback: %.2fs",
            self.turn_id,
            self.total_latency_sec,
            self.stt_duration_sec,
            self.llm_duration_sec,
            self.tool_calls_count,
            self.tools_duration_sec,
            self.tts_duration_sec,
            self.playback_duration_sec,
        )


class MetricsCollector:
    """Collects and aggregates performance metrics across session turns."""

    def __init__(self) -> None:
        self.turns: list[TurnMetrics] = []

    def record_turn(self, metrics: TurnMetrics) -> None:
        self.turns.append(metrics)
        metrics.log_summary()

    def get_averages(self) -> dict[str, float]:
        if not self.turns:
            return {}
        n = len(self.turns)
        return {
            "avg_total_latency_sec": sum(t.total_latency_sec for t in self.turns) / n,
            "avg_llm_duration_sec": sum(t.llm_duration_sec for t in self.turns) / n,
            "avg_tts_duration_sec": sum(t.tts_duration_sec for t in self.turns) / n,
            "total_turns": n,
        }


# Singleton collector
metrics_collector = MetricsCollector()

