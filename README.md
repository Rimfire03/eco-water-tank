# 💧 Eco Water Tank

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![GitHub release](https://img.shields.io/github/v/release/Rimfire03/eco-water-tank?include_prereleases)](https://github.com/Rimfire03/eco-water-tank/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-Donate-orange.svg?logo=buy-me-a-coffee&logoColor=white)](https://buymeacoffee.com/slide598b)

> A water tank for **Home Assistant** (level, inlet and outlet meters, rain gauge), shown in the Energy dashboard like a battery storage, ready for **HACS**.  
> *Une cuve d'eau pour **Home Assistant** (niveau, compteurs d'entrée et de sortie, pluviomètre), affichée dans le dashboard Énergie comme un stockage batterie, prête pour **HACS**.*

---

## ☕ Support / Soutenir le projet

If you find this integration helpful, consider buying me a coffee to support the development!  
*Si vous appréciez cette intégration, vous pouvez m'offrir un café pour soutenir le développement !*

<a href="https://buymeacoffee.com/slide598b" target="_blank"><img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Buy Me A Coffee" style="height: 50px !important;width: 217px !important;" ></a>

---

## Setup

Settings → Devices & services → Add integration → **Eco Water Tank**.

| Field | Required | Notes |
|---|---|---|
| Tank model | yes | Catalogue below (volume known, nothing else to type), or *Custom* |
| Capacity (L) | *Custom* only | Last custom step, prefilled with the volume computed from the dimensions (editable). Needed to convert % ↔ litres |
| Shape + dimensions (cm) | *Custom* only | Optional: rectangular = width × length × height, circular = π × (diameter ÷ 2)² × height |
| Freeform shape | *Custom* only | Neither square nor round (cone, oval, irregular…): no dimensions, type the capacity; the learned curve follows the real shape |
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
| Usable volume | L (`volume_storage`) | Only with a **pumping limit** (L the pump can never draw): volume − limit, never below 0. The *Tank empty* button then means "at the pumping limit" (calibrates the limit, not 0 L) |
| Water in | L, `water`, `total_increasing` | Inlet meter, or derived: rise of volume + water drawn out |
| Water out | L, `water`, `total_increasing` | Outlet meter, converted to L |
| Water in / out today | L, `water`, `total_increasing` | Today's part of the totals (outlet meter, inlet meter, or the estimated water in), back to 0 at local midnight; kept across restarts the same day |

## Learning level % → litres

With a `%` level sensor and at least one meter, the integration learns the real curve:
10 bins of litres-per-%, fitted from level changes (≥ 2 %) against the metered flow.
A drop is learned from the outlet meter, a rise from the inlet meter (both: net flow).
The entered capacity is the starting point (linear curve) and fades as data comes in,
so non-linear tanks (horizontal cylinder…) and a wrong capacity are corrected over time.
The result is shown by the diagnostic **Learned capacity** entity and used by **Volume**.
The learned data is stored in `.storage/eco_water_tank.<entry_id>`.
With a level sensor in litres, nothing is learned (the volume is already known).

### Manual correction

If the volume is off, tell the tank what it really holds now. Either:

- the **Real volume (correction)** (L) or **Real fill (correction)** (% of capacity) config entities of the device, then press **Apply correction**: the typed value is only taken on that press, then the inputs are cleared (typing one clears the other; nothing is kept across restarts), or
- the `eco_water_tank.calibrate` action (`volume` or `percent`, plus `config_entry` when there are several tanks).

The current level reading and your value become a calibration point that weighs like 5 metered samples
in the learned curve (stored, survives restarts). Repeat at other levels to refine. Needs a level sensor in `%` above 0.

Quick version: the **Tank full** / **Tank empty** buttons. *Full* = the capacity at the current reading (also clears the pending rain estimate); *empty* = 0 L at the current reading (a reading above 0 when empty means a dead volume below the sensor or pump intake). Same weight as a manual correction.

## Rainwater and rain gauge

Fed by rain, no meter? Add a **cumulative rain gauge** (device class `precipitation`, mm or in)
and the **catchment area** (m², roof) in the sensors step. 1 mm on 1 m² = 1 L.

| Entity | Notes |
|---|---|
| Water in (estimated) | Without an inlet meter: rise of the volume + water drawn out (attribute `estimated: true`). With a rain gauge, rain collected since the last level step is added (at most one step, 1 % of capacity), so slow rain shows up before the level moves |
| Rainwater collected (estimated) | rain × area × efficiency, cumulative litres |
| Overflow (estimated) | Collected rain the tank could not take while nearly full (≥ 90 %) |
| Learned collection efficiency | Diagnostic %. Starts at the value you set (default 85 %), then learned from what the tank really gained while not nearly full |

Limits: a mains top-up (tank gains more than twice the rain potential) is ignored by the learning;
slow level steps (1 % of capacity) make the efficiency converge over several rains, not one.

## Share your tank / propose a curve update

Custom tank to add to the catalogue, or a known tank whose learned curve differs from the catalogue?
The **Share tank settings / propose curve** button (or the `eco_water_tank.share_tank` action) creates a
notification with a link to a pre-filled GitHub issue (model, capacity, shape and dimensions, learned curve,
samples per bin) so it can be used in a next release. Nothing is sent automatically: you review and submit
the issue yourself, with your GitHub account.

Anti-spam: only after enough learning (about one full fill/drain, or a calibration),
once per 24 h per tank (kept across restarts), and the issue form requires its fields.

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
