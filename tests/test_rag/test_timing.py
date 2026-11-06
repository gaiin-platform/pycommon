"""Tests for pycommon.rag.timing."""

import logging

from pycommon.rag import timing


def test_timed_emits_a_greppable_line_and_notifies_sinks(caplog):
    """A timed block logs one [TIMING] line and calls every sink."""
    seen = []
    timing.add_sink(lambda stage, seconds, fields: seen.append((stage, fields)))
    with caplog.at_level(logging.INFO, logger="rag_timing"):
        with timing.timed("extract", key="u/doc.pdf", pages=57, skipped=None):
            pass
    messages = [r.message for r in caplog.records]
    assert any(
        "[TIMING] stage=extract seconds=" in m and "pages=57" in m for m in messages
    )
    assert not any("skipped" in m for m in messages)
    assert ("extract", {"key": "u/doc.pdf", "pages": 57, "skipped": None}) in seen


def test_emit_without_fields_logs_just_the_stage(caplog):
    """No extra fields means no trailing space."""
    with caplog.at_level(logging.INFO, logger="rag_timing"):
        timing.emit("bare", 0.5)
    assert any(r.message == "[TIMING] stage=bare seconds=0.50" for r in caplog.records)


def test_stopwatch_accumulates_per_label_and_emits_once(caplog):
    """Many calls under one label produce one summary line."""
    watch = timing.Stopwatch()
    assert watch.call("embed", lambda x: x * 2, 4) == 8
    watch.call("embed", lambda: None)
    with caplog.at_level(logging.INFO, logger="rag_timing"):
        watch.emit("embed_chunk_file", child=3)
    lines = [r.message for r in caplog.records if "[TIMING]" in r.message]
    assert len(lines) == 1 and "embed=" in lines[0] and "child=3" in lines[0]


def test_a_failing_sink_or_call_never_breaks_the_pipeline():
    """A broken sink is ignored; the callee's own error still propagates."""
    timing.add_sink(lambda *args: 1 / 0)
    timing.emit("anything", 0.1)  # must not raise
    watch = timing.Stopwatch()
    try:
        watch.call("x", lambda: 1 / 0)
    except ZeroDivisionError:
        pass
    assert "x" in watch.totals
