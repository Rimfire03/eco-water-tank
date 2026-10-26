"""Tank catalogue: Plasteau ECOCITER Habitat (catalogue Plasteau, édition 0526)."""

from __future__ import annotations

from typing import NamedTuple

CUSTOM = "custom"


class TankModelSpec(NamedTuple):
    reference: str
    liters: int

    @property
    def label(self) -> str:
        return f"Plasteau ECOCITER {self.liters} L ({self.reference})"


def box_liters(width_cm: float, length_cm: float, height_cm: float) -> float:
    """Volume of a rectangular tank in litres (1 L = 1000 cm³)."""
    return round(width_cm * length_cm * height_cm / 1000, 1)


# References are spelled as in the catalogue (ET07000 / ET08000 have no "Y" there).
MODELS: dict[str, TankModelSpec] = {
    s.reference: s
    for s in (
        TankModelSpec("ETY01000", 1000),
        TankModelSpec("ETY01500", 1500),
        TankModelSpec("ETY02000", 2000),
        TankModelSpec("ETY03000", 3000),
        TankModelSpec("ETY04000", 4000),
        TankModelSpec("ETY05000", 5000),
        TankModelSpec("ETY06000", 6000),
        TankModelSpec("ET07000", 7000),
        TankModelSpec("ET08000", 8000),
        TankModelSpec("ETM10000", 10000),
    )
}
