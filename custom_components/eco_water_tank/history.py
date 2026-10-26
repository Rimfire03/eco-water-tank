"""Import the long-term statistics of existing sensors into the tank sensors."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from functools import partial
import logging
from typing import TYPE_CHECKING

from homeassistant.const import PERCENTAGE, UnitOfVolume
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from homeassistant.util.unit_conversion import VolumeConverter

from .const import DOMAIN

if TYPE_CHECKING:
    from .sensor import TankModel

_LOGGER = logging.getLogger(__name__)
L = UnitOfVolume.LITERS


def _start(row: dict) -> datetime:
    s = row["start"]
    return datetime.fromtimestamp(s, tz=UTC) if isinstance(s, (int, float)) else s


def _metadata(entity_id: str, unit: str, has_mean: bool) -> dict:
    meta = {
        "source": "recorder",
        "statistic_id": entity_id,
        "name": None,
        "unit_of_measurement": unit,
        "has_sum": not has_mean,
    }
    try:  # HA >= 2025.4
        from homeassistant.components.recorder.models import StatisticMeanType

        meta["mean_type"] = StatisticMeanType.ARITHMETIC if has_mean else StatisticMeanType.NONE
        meta["unit_class"] = None if unit == PERCENTAGE else "volume"
    except ImportError:
        meta["has_mean"] = has_mean
    return meta


async def import_history(hass: HomeAssistant, model: TankModel) -> int:
    """Train the learner on past data and import statistics; returns rows imported."""
    from homeassistant.components.recorder import get_instance
    from homeassistant.components.recorder.models import StatisticData
    from homeassistant.components.recorder.statistics import (
        async_import_statistics,
        statistics_during_period,
    )

    registry = er.async_get(hass)
    keys = ["level", "volume"] + (["water_in"] if model.inlet else []) + (
        ["water_out"] if model.outlet else []
    )
    targets: dict[str, str] = {}
    for _ in range(15):  # entities register shortly after setup
        targets = {
            k: eid
            for k in keys
            if (eid := registry.async_get_entity_id("sensor", DOMAIN, f"{model.entry_id}_{k}"))
        }
        if len(targets) == len(keys):
            break
        await asyncio.sleep(2)
    if len(targets) != len(keys):
        _LOGGER.warning("History import skipped: tank entities not registered")
        return 0

    sources = {i for i in (model.level, model.inlet, model.outlet) if i}
    end = dt_util.utcnow().replace(minute=0, second=0, microsecond=0)
    stats = await get_instance(hass).async_add_executor_job(
        partial(
            statistics_during_period, hass, None, end, sources, "hour", None,
            {"mean", "min", "max", "state", "sum"},
        )
    )

    def factor(entity_id: str) -> float | None:
        """Multiplier source unit -> litres (None: unknown unit)."""
        state = hass.states.get(entity_id)
        unit = state.attributes.get("unit_of_measurement") if state else None
        try:
            return VolumeConverter.convert(1.0, unit, L)
        except HomeAssistantError:
            return None

    meters = {k: e for k, e in (("water_in", model.inlet), ("water_out", model.outlet)) if e}
    meter_f = {k: factor(e) for k, e in meters.items()}
    by_start = {
        i: {_start(r): r for r in stats.get(i, [])} for i in sources
    }

    # 1. learn the % -> litres curve from past hours
    level_rows = by_start[model.level]
    if model.level_is_percent():
        model.learner.reset()
        for start in sorted(level_rows):
            mean = level_rows[start].get("mean")
            vals = {}
            for k, e in meters.items():
                row = by_start[e].get(start)
                f = meter_f[k]
                vals[k] = None if row is None or f is None or row.get("state") is None else row["state"] * f
            if mean is not None:
                model.learner.update(mean, vals.get("water_in"), vals.get("water_out"))

    # 2. import statistics
    imported = 0
    lf = None if model.level_is_percent() else factor(model.level)

    def to_l(percent: float | None) -> float | None:
        if percent is None:
            return None
        return model.learner.volume(percent)

    def level_row(start, row):
        if model.level_is_percent() and row.get("mean") is not None:
            p = {k: row.get(k) for k in ("mean", "min", "max")}
        elif lf is not None and row.get("mean") is not None:
            p = {k: row[k] * lf / model.capacity * 100 for k in ("mean", "min", "max")}
        else:
            return None
        return StatisticData(start=start, **p)

    def volume_row(start, row):
        if model.level_is_percent() and row.get("mean") is not None:
            v = {k: to_l(row.get(k)) for k in ("mean", "min", "max")}
        elif lf is not None and row.get("mean") is not None:
            v = {k: row[k] * lf for k in ("mean", "min", "max")}
        else:
            return None
        return StatisticData(start=start, **v) if v["mean"] is not None else None

    series: dict[str, tuple[list, str, bool]] = {
        "level": ([x for s, r in level_rows.items() if (x := level_row(s, r))], PERCENTAGE, True),
        "volume": ([x for s, r in level_rows.items() if (x := volume_row(s, r))], L, True),
    }
    for k, e in meters.items():
        f = meter_f[k]
        if f is None:
            continue
        series[k] = (
            [
                StatisticData(start=s, state=r["state"] * f, sum=r["sum"] * f)
                for s, r in by_start[e].items()
                if r.get("state") is not None and r.get("sum") is not None
            ],
            L,
            False,
        )
    for k, (rows, unit, has_mean) in series.items():
        if rows:
            rows.sort(key=lambda d: d["start"])
            async_import_statistics(hass, _metadata(targets[k], unit, has_mean), rows)
            imported += len(rows)
    return imported
