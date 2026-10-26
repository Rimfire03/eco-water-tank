# Eco Water Tank

[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-Donate-orange.svg?logo=buy-me-a-coffee&logoColor=white)](https://buymeacoffee.com/slide598b)

Home Assistant custom integration (HACS): model a water tank, a bit like the battery storage of the Energy dashboard.

## Setup

Settings → Devices & services → Add integration → **Eco Water Tank**.

| Field | Required | Notes |
|---|---|---|
| Tank model | yes | Catalogue below, or *Custom* |
| Capacity (L) | only for *Custom* | Overrides the model's volume. Needed to convert % ↔ litres |
| Width / length / height (cm) | no | *Custom* only: if capacity is empty, capacity = width × length × height (rectangular tank). For other shapes type the capacity |
| Level sensor | yes | `%` or any volume unit (L, m³, gal…) |
| Inlet meter | no | Cumulative water meter. If absent, water in is derived |
| Outlet meter | no | Cumulative water meter |

## Tank models

Plasteau ECOCITER Habitat (catalogue Plasteau, édition 0526):

| Volume | Reference |
|---|---|
| 1000 L | ETY01000 |
| 1500 L | ETY01500 |
| 2000 L | ETY02000 |
| 3000 L | ETY03000 |
| 4000 L | ETY04000 |
| 5000 L | ETY05000 |
| 6000 L | ETY06000 |
| 7000 L | ET07000 |
| 8000 L | ET08000 |
| 10000 L | ETM10000 |

References are spelled as printed in the catalogue. Add a model in `models.py`.

## History import

At first startup (and with the `eco_water_tank.import_history` action) the long-term statistics
of the level sensor and meters are copied to the tank sensors, so the Energy dashboard and graphs
show the past: level %, volume, water in / out (meter totals). The level % → litres curve is
trained on the same history. "Water in" derived without an inlet meter has no history.

## Entities

| Entity | Class | Notes |
|---|---|---|
| Level | % | Tank fill |
| Volume | L (`volume_storage`) | Water in the tank |
| Water in | L, `water`, `total_increasing` | Inlet meter, or derived: rise of volume + water drawn out |
| Water out | L, `water`, `total_increasing` | Outlet meter, converted to L |

## Learning level % → litres

With a `%` level sensor and at least one meter, the integration learns the real curve:
10 bins of litres-per-%, fitted from level changes (≥ 2 %) against the metered flow.
A drop is learned from the outlet meter, a rise from the inlet meter (both: net flow).
The entered capacity is the starting point (linear curve) and fades as data comes in,
so non-linear tanks (horizontal cylinder…) and a wrong capacity are corrected over time.
The result is shown by the diagnostic **Learned capacity** entity and used by **Volume**.
The learned data is stored in `.storage/eco_water_tank.<entry_id>`.
With a level sensor in litres, nothing is learned (the volume is already known).

## Energy dashboard

Energy → Water consumption → add **Water out** (consumption drawn from the tank).
**Water in** is available the same way (e.g. to track mains/rain refill).

Limit: the Energy dashboard has no native "tank" source type (batteries are built into core),
so the tank is exposed as standard water sensors that the dashboard accepts.

## Derived "Water in"

Without an inlet meter: `in = Δvolume + Δoutlet`, counted only when above 1 % of capacity
so sensor noise never accumulates. Unmetered losses (leaks) are not subtracted from the total.
Without an outlet meter either, only level rises are counted (draws are invisible).

## Releases

Semantic versioning. To release: bump `version` in `custom_components/eco_water_tank/manifest.json`,
commit, then push the matching tag (`git tag vX.Y.Z && git push origin vX.Y.Z`).
The Release workflow checks tag = manifest version and publishes the GitHub release; HACS offers it as an update.

## Support

If you find it useful, you can support the project:

<a href="https://buymeacoffee.com/slide598b" target="_blank"><img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Buy Me A Coffee" height="50"></a>
