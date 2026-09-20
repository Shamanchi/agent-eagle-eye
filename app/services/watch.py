"""Ряды метрик, правила и алерты (in-memory, офлайн)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel


class Point(BaseModel):
    metric: str
    value: float
    ts: str


class Rule(BaseModel):
    metric: str
    op: Literal["gt", "lt"]
    threshold: float


class Alert(BaseModel):
    metric: str
    value: float
    kind: str
    detail: str
    ts: str


class SeriesStats(BaseModel):
    metric: str
    count: int
    last: float
    min: float
    max: float
    avg: float


class Watcher:
    """Хранит точки, проверяет правила и всплески."""

    def __init__(self, spike_window: int = 5, spike_mult: float = 3.0, max_points: int = 1000) -> None:
        self._spike_window = max(spike_window, 1)
        self._spike_mult = spike_mult
        self._max_points = max(max_points, 1)
        self._series: dict[str, list[Point]] = {}
        self._rules: list[Rule] = []
        self._alerts: list[Alert] = []

    def add_rule(self, metric: str, op: str, threshold: float) -> Rule:
        if op not in ("gt", "lt"):
            raise ValueError("op must be gt or lt")
        name = metric.strip().lower()
        if not name:
            raise ValueError("metric must not be empty")
        rule = Rule(metric=name, op=op, threshold=threshold)  # type: ignore[arg-type]
        self._rules = [r for r in self._rules if not (r.metric == name and r.op == op)]
        self._rules.append(rule)
        return rule

    def rules(self) -> list[Rule]:
        return list(self._rules)

    def ingest(self, metric: str, value: float) -> list[Alert]:
        name = metric.strip().lower()
        if not name:
            raise ValueError("metric must not be empty")
        now = datetime.now(timezone.utc).isoformat()
        series = self._series.setdefault(name, [])
        previous = list(series)
        series.append(Point(metric=name, value=value, ts=now))
        del series[: max(len(series) - self._max_points, 0)]
        fired: list[Alert] = []
        for rule in self._rules:
            if rule.metric != name:
                continue
            breached = value > rule.threshold if rule.op == "gt" else value < rule.threshold
            if breached:
                fired.append(
                    Alert(
                        metric=name,
                        value=value,
                        kind="threshold",
                        detail=f"{name} {value:g} {rule.op} {rule.threshold:g}",
                        ts=now,
                    )
                )
        if len(previous) >= self._spike_window:
            window = [p.value for p in previous[-self._spike_window :]]
            mean = sum(window) / len(window)
            if mean > 0 and value > mean * self._spike_mult:
                fired.append(
                    Alert(
                        metric=name,
                        value=value,
                        kind="spike",
                        detail=f"{name} {value:g} > {self._spike_mult:g}x mean {mean:.2f}",
                        ts=now,
                    )
                )
        self._alerts.extend(fired)
        return fired

    def stats(self, metric: str) -> SeriesStats | None:
        series = self._series.get(metric.strip().lower(), [])
        if not series:
            return None
        values = [p.value for p in series]
        return SeriesStats(
            metric=metric.strip().lower(),
            count=len(values),
            last=values[-1],
            min=min(values),
            max=max(values),
            avg=round(sum(values) / len(values), 2),
        )

    def alerts(self) -> list[Alert]:
        return list(self._alerts)

    def digest(self) -> str:
        lines = ["# Eagle-eye digest", ""]
        if not self._alerts:
            lines.append("No alerts.")
            return "\n".join(lines) + "\n"
        lines.append(f"- Alerts: {len(self._alerts)}")
        for alert in self._alerts[-10:]:
            lines.append(f"- [{alert.kind}] {alert.detail}")
        return "\n".join(lines) + "\n"

    def clear(self) -> None:
        self._series.clear()
        self._rules.clear()
        self._alerts.clear()


_watcher: Watcher | None = None


def get_watcher(spike_window: int = 5, spike_mult: float = 3.0, max_points: int = 1000) -> Watcher:
    global _watcher
    if _watcher is None:
        _watcher = Watcher(spike_window, spike_mult, max_points)
    return _watcher
