"""Today's part of a cumulative total."""

from __future__ import annotations

from datetime import date


class DailyBaseline:
    """today = total - total at the start of the day (local midnight)."""

    def __init__(self, baseline: float | None = None, day: date | None = None) -> None:
        self.baseline = baseline
        self.day = day

    def today(self, total: float, day: date) -> float:
        if self.baseline is None or self.day != day:  # first reading, or midnight missed
            self.baseline, self.day = total, day
        elif total < self.baseline:  # meter reset during the day
            self.baseline = 0.0
        return total - self.baseline

    def rollover(self, total: float, day: date) -> None:
        self.baseline, self.day = total, day
