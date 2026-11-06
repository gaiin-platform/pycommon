"""Stage timing for the RAG pipeline.

Every stage reports one log line in a fixed, greppable format:

    [TIMING] stage=extract seconds=3.42 key=user/2026/doc.pdf pages=57

so slow stages can be found in CloudWatch with a single filter ("[TIMING]").
The same data goes to any registered sink, which is how the pipeline
walkthrough script shows timings without parsing logs.

Timing is observability only: nothing here can raise into the pipeline.
"""

import logging
import time
from contextlib import contextmanager

logger = logging.getLogger("rag_timing")
logger.setLevel(logging.INFO)

_sinks = []


def add_sink(sink):
    """sink(stage: str, seconds: float, fields: dict) is called per timing."""
    _sinks.append(sink)


def emit(stage, seconds, **fields):
    try:
        extra = " ".join(
            f"{name}={value}" for name, value in fields.items() if value is not None
        )
        logger.info(
            "[TIMING] stage=%s seconds=%.2f%s",
            stage,
            seconds,
            f" {extra}" if extra else "",
        )
        for sink in list(_sinks):
            sink(stage, seconds, dict(fields))
    except Exception:  # never let observability break ingestion
        pass


@contextmanager
def timed(stage, **fields):
    started = time.perf_counter()
    try:
        yield
    finally:
        emit(stage, time.perf_counter() - started, **fields)


class Stopwatch:
    """Accumulates time per label across many calls, then emits one summary."""

    def __init__(self):
        self.started = time.perf_counter()
        self.totals = {}

    def call(self, label, function, *args, **kwargs):
        begun = time.perf_counter()
        try:
            return function(*args, **kwargs)
        finally:
            elapsed = time.perf_counter() - begun
            self.totals[label] = self.totals.get(label, 0.0) + elapsed

    def emit(self, stage, **fields):
        total = time.perf_counter() - self.started
        parts = {
            label: f"{seconds:.2f}" for label, seconds in sorted(self.totals.items())
        }
        emit(stage, total, **parts, **fields)
