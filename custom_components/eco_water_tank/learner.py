"""Learn the level % -> litres curve from metered flows."""

from __future__ import annotations

BINS = 10
WIDTH = 100 / BINS
PRIOR = 20.0  # pseudo-observation, in % units: weight of the entered capacity
CAL_WEIGHT = 5.0  # a manual calibration counts like this many metered samples


class Learner:
    """Per-bin litres-per-% (k), fitted by least squares through the origin.

    A sample is a level change (>= min_step %) with the metered net flow over
    the same period. It is split over the bins it crosses. The entered capacity
    is the prior, so the curve starts linear and bends toward what the meters say.
    A sample needs a meter that sees the direction of the change: outlet for a
    drop, inlet for a rise.
    """

    def __init__(
        self,
        capacity: float,
        has_in: bool,
        has_out: bool,
        data: dict | None = None,
        min_step: float = 2.0,
    ) -> None:
        self.k0 = capacity / 100
        self.has_in = has_in
        self.has_out = has_out
        self.min_step = min_step
        data = data or {}
        self.sxy: list[float] = data.get("sxy") or [0.0] * BINS
        self.sxx: list[float] = data.get("sxx") or [0.0] * BINS
        self._ref: tuple[float, float, float] | None = None

    def calibrate(self, percent: float, liters: float, weight: float = CAL_WEIGHT) -> None:
        """Manual truth: the tank holds `liters` at `percent`. Counts as `weight` samples 0 -> percent."""
        p = min(percent, 100.0)
        for i in range(BINS):
            overlap = min(p, (i + 1) * WIDTH) - i * WIDTH
            if overlap > 0:
                self.sxx[i] += weight * overlap
                self.sxy[i] += weight * liters * overlap / p

    def reset(self) -> None:
        self.sxy = [0.0] * BINS
        self.sxx = [0.0] * BINS
        self._ref = None

    def as_dict(self) -> dict:
        return {"sxy": self.sxy, "sxx": self.sxx}

    def _k(self, i: int) -> float:
        return (self.sxy[i] + self.k0 * PRIOR) / (self.sxx[i] + PRIOR)

    def volume(self, percent: float) -> float:
        p = min(max(percent, 0.0), 100.0)
        return sum(self._k(i) * max(0.0, min(p, (i + 1) * WIDTH) - i * WIDTH) for i in range(BINS))

    def update(self, percent: float, in_l: float | None, out_l: float | None) -> bool:
        """Feed current readings; True when a sample was learned."""
        if (self.has_in and in_l is None) or (self.has_out and out_l is None):
            return False
        cur = (percent, in_l or 0.0, out_l or 0.0)
        if self._ref is None:
            self._ref = cur
            return False
        p0, in0, out0 = self._ref
        dp = percent - p0
        if abs(dp) < self.min_step:
            return False
        self._ref = cur
        d_in, d_out = cur[1] - in0, cur[2] - out0
        if d_in < 0 or d_out < 0:  # meter reset
            return False
        if (dp > 0 and not self.has_in) or (dp < 0 and not self.has_out):
            return False
        d_l = d_in - d_out
        if d_l * dp <= 0:
            return False
        lo, hi = min(p0, percent), max(p0, percent)
        for i in range(BINS):
            overlap = min(hi, (i + 1) * WIDTH) - max(lo, i * WIDTH)
            if overlap > 0:
                self.sxx[i] += overlap
                self.sxy[i] += abs(d_l) * overlap / abs(dp)
        return True
