"""Share a custom tank: a pre-filled GitHub issue link. Nothing is sent automatically."""

from __future__ import annotations

import json
from urllib.parse import urlencode

REPO = "https://github.com/Rimfire03/eco-water-tank"
COOLDOWN = 24 * 3600  # s between two shares of the same tank
MIN_SAMPLES = 100.0  # learned % units (about one full fill/drain) before a tank is worth sharing


def build(payload: dict) -> tuple[str, str]:
    """(issue URL, pretty JSON). Payload keys are the issue form field ids."""
    fields = {k: json.dumps(v) if isinstance(v, list) else str(v) for k, v in payload.items()}
    query = urlencode({"template": "tank-model.yml", "title": f"[Tank] {payload['name']}", **fields})
    return f"{REPO}/issues/new?{query}", json.dumps(payload, ensure_ascii=False, indent=2)


def refusal(now: float, last_share: float, samples: float) -> str | None:
    """Why sharing is refused (anti-spam), or None when allowed."""
    if samples < MIN_SAMPLES:
        return f"Not enough learning to share yet ({samples:.0f}/{MIN_SAMPLES:.0f}): use the tank for a while or calibrate it"
    wait = last_share + COOLDOWN - now
    if wait > 0:
        return f"Already shared recently, try again in {wait / 3600:.1f} h"
    return None
