"""Unit tests for bounded FIFO command queue and metrics."""

import asyncio
import pytest

from jarvis_brain.voice.command_queue import CommandQueue


@pytest.mark.asyncio
async def test_fifo_ordering():
    """Verify commands are processed in strict arrival order."""
    q = CommandQueue(maxsize=5)
    cmd1 = q.enqueue("First command")
    cmd2 = q.enqueue("Second command")
    cmd3 = q.enqueue("Third command")

    assert cmd1 is not None and cmd2 is not None and cmd3 is not None
    assert q.qsize == 3

    out1 = await q.get()
    out2 = await q.get()
    out3 = await q.get()

    assert out1.command_text == "First command"
    assert out2.command_text == "Second command"
    assert out3.command_text == "Third command"
    assert q.qsize == 0


@pytest.mark.asyncio
async def test_queue_overflow_non_blocking():
    """Verify queue overflow does not block, preserves FIFO order, and sets overflow flag."""
    q = CommandQueue(maxsize=2)
    c1 = q.enqueue("Command 1")
    c2 = q.enqueue("Command 2")
    c3 = q.enqueue("Command 3 (overflow)")

    assert c1 is not None
    assert c2 is not None
    assert c3 is None  # Dropped due to capacity
    assert q.has_pending_overflow_notice is True
    assert q.qsize == 2

    # Verify FIFO contents preserved
    first = await q.get()
    second = await q.get()
    assert first.command_text == "Command 1"
    assert second.command_text == "Command 2"

    metrics = q.get_metrics()
    assert metrics["total_enqueued"] == 2
    assert metrics["total_overflows"] == 1


@pytest.mark.asyncio
async def test_queue_metrics_tracking():
    """Verify metrics accurately reflect throughput."""
    q = CommandQueue(maxsize=5)
    c = q.enqueue("Test task")
    assert c is not None
    assert q.get_metrics()["total_enqueued"] == 1

    fetched = await q.get()
    q.mark_processed(fetched)
    metrics = q.get_metrics()
    assert metrics["total_processed"] == 1
    assert metrics["current_depth"] == 0

