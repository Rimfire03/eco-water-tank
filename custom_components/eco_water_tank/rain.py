"""Rainwater inflow estimate from a rain gauge, with a learned collection efficiency."""

from __future__ import annotations

PRIOR_L = 500.0  # weight (potential litres) of the configured efficiency
MIN_MM = 0.2  # smallest rain step worth a sample (gauge tick)
FULL = 90.0  # % above which a tank overflows instead of storing


class RainTracker:
    """1 mm on 1 m² = 1 L. Collected = rain x area x efficiency.

    Efficiency starts at the configured value and is learned from what the tank
    really gained (`intake`) while it is not nearly full. Near full, collected
    water the tank did not gain is counted as overflow. Samples where the tank
    gained more than twice the potential (mains top-up) are ignored.
    """

    def __init__(
        self, area_m2: float, efficiency: float, data: dict | None = None, cap: float = 0.0
    ) -> None:
        d = data or {}
        self.area = area_m2
        self.eff0 = efficiency
        self.total = d.get("total", 0.0)  # litres collected (estimate)
        self.overflow = d.get("overflow", 0.0)  # litres lost at full tank (estimate)
        self.s_in = d.get("s_in", 0.0)
        self.s_rain = d.get("s_rain", 0.0)
        self._ref: tuple[float, float | None] | None = None
        # Rain collected but not yet seen as a level step (the level moves by steps of `cap` litres).
        # Shown as estimated inflow, at most `cap`: a step of >= cap always absorbs it, so the
        # estimate never goes down.
        self.cap = cap
        self.pending = 0.0
        self._pend_base: float | None = None

    def _sync(self, intake_l: float) -> None:
        if self._pend_base is not None and intake_l > self._pend_base:
            self.pending = max(0.0, self.pending - (intake_l - self._pend_base))
        self._pend_base = intake_l

    def pending_gain(self, intake_l: float) -> float:
        """Litres of rain probably in the tank already, below the level step size."""
        self._sync(intake_l)
        return min(self.pending, self.cap)

    def efficiency(self) -> float:
        return (self.s_in + PRIOR_L * self.eff0) / (self.s_rain + PRIOR_L)

    def as_dict(self) -> dict:
        return {"total": self.total, "overflow": self.overflow, "s_in": self.s_in, "s_rain": self.s_rain}

    def update(self, rain_mm: float, intake_l: float | None, percent: float | None) -> None:
        """Feed cumulative rain (mm), cumulative litres the tank gained, and the level %."""
        if self._ref is None:
            self._ref = (rain_mm, intake_l)
            return
        d_rain = rain_mm - self._ref[0]
        if d_rain < 0:  # gauge reset
            self._ref = (rain_mm, intake_l)
            return
        if d_rain < MIN_MM:
            return
        potential = d_rain * self.area
        collected = potential * self.efficiency()
        self.total += collected
        if intake_l is not None:
            self._sync(intake_l)
        if percent is None or percent < FULL:
            self.pending += collected
        if intake_l is not None and self._ref[1] is not None:
            d_in = max(0.0, intake_l - self._ref[1])
            if percent is not None and percent >= FULL:
                self.overflow += max(0.0, collected - d_in)
            elif d_in <= 2 * potential:
                self.s_rain += potential
                self.s_in += d_in
        self._ref = (rain_mm, intake_l)
