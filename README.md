# Eco Water Tank

[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-Donate-orange.svg?logo=buy-me-a-coffee&logoColor=white)](https://buymeacoffee.com/slide598b)

Home Assistant custom integration (HACS): model a water tank, a bit like the battery storage of the Energy dashboard.

## Setup

Settings → Devices & services → Add integration → **Eco Water Tank**.

| Field | Required | Notes |
|---|---|---|
| Capacity (L) | yes | Needed to convert % ↔ litres |
| Level sensor | yes | `%` or any volume unit (L, m³, gal…) |
| Inlet meter | no | Cumulative water meter. If absent, water in is derived |
| Outlet meter | no | Cumulative water meter |

## Entities

| Entity | Class | Notes |
|---|---|---|
| Level | % | Tank fill |
| Volume | L (`volume_storage`) | Water in the tank |
| Water in | L, `water`, `total_increasing` | Inlet meter, or derived: rise of volume + water drawn out |
| Water out | L, `water`, `total_increasing` | Outlet meter, converted to L |

## Energy dashboard

Energy → Water consumption → add **Water out** (consumption drawn from the tank).
**Water in** is available the same way (e.g. to track mains/rain refill).

Limit: the Energy dashboard has no native "tank" source type (batteries are built into core),
so the tank is exposed as standard water sensors that the dashboard accepts.

## Derived "Water in"

Without an inlet meter: `in = Δvolume + Δoutlet`, counted only when above 1 % of capacity
so sensor noise never accumulates. Unmetered losses (leaks) are not subtracted from the total.
Without an outlet meter either, only level rises are counted (draws are invisible).

## Support

If you find it useful, you can support the project:

<a href="https://buymeacoffee.com/slide598b" target="_blank"><img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Buy Me A Coffee" height="50"></a>
