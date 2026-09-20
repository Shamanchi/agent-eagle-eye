"""Unit-тесты вотчера: без сети, детерминированы."""

import pytest

from app.services.watch import Watcher


def test_threshold_rule_fires() -> None:
    eye = Watcher()
    eye.add_rule("cpu", "gt", 90)
    fired = eye.ingest("cpu", 95)
    assert len(fired) == 1
    assert fired[0].kind == "threshold"
    assert fired[0].detail == "cpu 95 gt 90"
    assert eye.ingest("cpu", 50) == []


def test_lt_rule() -> None:
    eye = Watcher()
    eye.add_rule("disk_free", "lt", 10)
    assert len(eye.ingest("disk_free", 5)) == 1
    assert eye.ingest("disk_free", 50) == []


def test_spike_detection() -> None:
    eye = Watcher(spike_window=3, spike_mult=3.0)
    for value in (10.0, 10.0, 10.0):
        assert eye.ingest("rps", value) == []
    fired = eye.ingest("rps", 40.0)
    assert len(fired) == 1
    assert fired[0].kind == "spike"


def test_stats() -> None:
    eye = Watcher()
    assert eye.stats("cpu") is None
    eye.ingest("cpu", 10)
    eye.ingest("cpu", 20)
    stats = eye.stats("cpu")
    assert stats is not None
    assert (stats.count, stats.last, stats.min, stats.max, stats.avg) == (2, 20, 10, 20, 15.0)


def test_bad_rule_rejected() -> None:
    eye = Watcher()
    with pytest.raises(ValueError):
        eye.add_rule("cpu", "ne", 90)
    with pytest.raises(ValueError):
        eye.add_rule("   ", "gt", 90)


def test_digest() -> None:
    eye = Watcher()
    assert "No alerts" in eye.digest()
    eye.add_rule("cpu", "gt", 90)
    eye.ingest("cpu", 95)
    assert "threshold" in eye.digest()
