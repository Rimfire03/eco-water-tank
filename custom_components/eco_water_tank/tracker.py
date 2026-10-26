"""Derive water inflow from tank volume and outflow (no inlet meter)."""


class InflowTracker:
    """Cumulative inflow = rise in volume + water drawn out, ignoring sensor noise.

    Balance since last reference point: net = d(volume) + d(outflow).
    Only a net gain above `threshold` is counted; a net loss above it
    (leak, meter reset) just moves the reference, so noise never accumulates.
    """

    def __init__(self, threshold: float, total: float = 0.0) -> None:
        self.threshold = threshold
        self.total = total
        self._ref: tuple[float, float] | None = None

    def update(self, volume: float, outflow: float = 0.0) -> float:
        if self._ref is None:
            self._ref = (volume, outflow)
            return self.total
        net = (volume - self._ref[0]) + (outflow - self._ref[1])
        if abs(net) > self.threshold:
            if net > 0:
                self.total += net
            self._ref = (volume, outflow)
        return self.total
