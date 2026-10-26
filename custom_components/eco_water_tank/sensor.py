"""Tank sensors: level %, volume, learned capacity, water in, water out."""

from __future__ import annotations

from collections.abc import Callable
import logging
import time

from homeassistant.components import persistent_notification

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfLength, UnitOfVolume
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect, async_dispatcher_send
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.start import async_at_started
from homeassistant.helpers.storage import Store
from homeassistant.util.unit_conversion import DistanceConverter, VolumeConverter

from .const import (
    CONF_AREA,
    CONF_CAPACITY,
    CONF_DIAMETER,
    CONF_EFFICIENCY,
    CONF_HEIGHT,
    CONF_INLET,
    CONF_LENGTH,
    CONF_LEVEL,
    CONF_MODEL,
    CONF_OUTLET,
    CONF_RAIN,
    CONF_SHAPE,
    CONF_WIDTH,
    DOMAIN,
)
from .history import import_history
from .learner import Learner
from .models import CUSTOM, MODELS
from .rain import RainTracker
from .share import build, refusal
from .tracker import InflowTracker

_LOGGER = logging.getLogger(__name__)


def _liters(hass: HomeAssistant, entity_id: str, capacity: float | None) -> float | None:
    """State of `entity_id` in litres; a % state needs `capacity`."""
    state = hass.states.get(entity_id)
    if state is None:
        return None
    try:
        value = float(state.state)
    except ValueError:  # unknown / unavailable
        return None
    unit = state.attributes.get("unit_of_measurement")
    if unit == PERCENTAGE:
        return None if capacity is None else value * capacity / 100
    try:
        return VolumeConverter.convert(value, unit, UnitOfVolume.LITERS)
    except HomeAssistantError:
        return None


def _mm(hass: HomeAssistant, entity_id: str) -> float | None:
    """Cumulative rain gauge reading in mm."""
    state = hass.states.get(entity_id)
    if state is None:
        return None
    try:
        return DistanceConverter.convert(
            float(state.state), state.attributes.get("unit_of_measurement"), UnitOfLength.MILLIMETERS
        )
    except (ValueError, HomeAssistantError):
        return None


def refresh_signal(entry_id: str) -> str:
    return f"{DOMAIN}_refresh_{entry_id}"


def device_info(entry: ConfigEntry) -> DeviceInfo:
    spec = MODELS.get((entry.options or entry.data).get(CONF_MODEL))
    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name=entry.title,
        manufacturer="Plasteau" if spec else None,
        model=spec.label if spec else None,
    )


def learner_store(hass: HomeAssistant, entry_id: str) -> Store:
    return Store(hass, 1, f"{DOMAIN}.{entry_id}")


class TankModel:
    """Level sensor -> % and litres. A % level sensor feeds the learned curve."""

    def __init__(self, hass, entry_id, level, inlet, outlet, capacity, learner, store, data) -> None:
        self.hass = hass
        self.entry_id = entry_id
        self.level, self.inlet, self.outlet = level, inlet, outlet
        self.capacity = capacity
        self.learner = learner
        self.store = store
        self.history_done = bool((data or {}).get("history_done"))
        self.last_share = float((data or {}).get("last_share", 0))
        self.entry: ConfigEntry | None = None  # set by async_setup_entry
        self.rain: RainTracker | None = None
        self.rain_entity: str | None = None
        self.intake_tracker: InflowTracker | None = None  # set by DerivedInflow

    def persisted(self) -> dict:
        return {
            **self.learner.as_dict(),
            "history_done": self.history_done,
            "last_share": self.last_share,
            **({"rain": self.rain.as_dict()} if self.rain else {}),
        }

    @callback
    def on_rain(self, _: Event) -> None:
        mm = _mm(self.hass, self.rain_entity)
        if mm is None:
            return
        if self.inlet:
            intake = _liters(self.hass, self.inlet, None)
        else:
            intake = self.intake_tracker.total if self.intake_tracker else None
        self.rain.update(mm, intake, self.percent())
        self.store.async_delay_save(self.persisted, 60)

    async def share(self) -> dict:
        """Notify a pre-filled GitHub issue link + the settings (any tank, rate limited)."""
        cfg = self.entry.options or self.entry.data
        spec = MODELS.get(cfg.get(CONF_MODEL))
        now = time.time()
        reason = refusal(now, self.last_share, sum(self.learner.sxx))
        if reason:
            raise ServiceValidationError(reason)
        payload = {
            "name": spec.label if spec else self.entry.title,
            "model": cfg.get(CONF_MODEL, CUSTOM),
            "capacity": cfg[CONF_CAPACITY],
            **{k: cfg[k] for k in (CONF_SHAPE, CONF_WIDTH, CONF_LENGTH, CONF_DIAMETER, CONF_HEIGHT) if cfg.get(k)},
            "curve": self.learner.curve(),
            "samples": self.learner.samples(),
        }
        url, text = build(payload)
        self.last_share = now  # before the await: concurrent presses hit the cooldown
        await self.store.async_save(self.persisted())
        persistent_notification.async_create(
            self.hass,
            f"[Open a pre-filled GitHub issue]({url})\n\nOr copy these settings:\n\n```json\n{text}\n```",
            title="Eco Water Tank: share your tank",
            notification_id=f"{DOMAIN}_share_{self.entry_id}",
        )
        return payload

    def level_is_percent(self) -> bool:
        state = self.hass.states.get(self.level)
        return state is not None and state.attributes.get("unit_of_measurement") == PERCENTAGE

    async def run_import(self) -> int:
        """Import past statistics + train the curve (once at startup, or on demand)."""
        try:
            count = await import_history(self.hass, self)
        except Exception:  # noqa: BLE001 - history is best effort, never break setup
            _LOGGER.exception("History import failed")
            return 0
        self.history_done = True
        await self.store.async_save(self.persisted())
        _LOGGER.info("History import: %s statistic rows", count)
        return count

    async def calibrate(self, volume: float | None, percent: float | None) -> None:
        """Teach the curve a manual truth: the tank holds `volume` L (or `percent` % of capacity) now."""
        if (volume is None) == (percent is None):
            raise ServiceValidationError("Give either a volume (L) or a fill percentage")
        p = self._percent_state()
        if p is None or p <= 0:
            raise ServiceValidationError("Calibration needs a level sensor in % reading above 0")
        liters = volume if volume is not None else percent / 100 * self.capacity
        self.learner.calibrate(p, liters)
        await self.store.async_save(self.persisted())
        async_dispatcher_send(self.hass, refresh_signal(self.entry_id))

    def _percent_state(self) -> float | None:
        state = self.hass.states.get(self.level)
        if state is None or state.attributes.get("unit_of_measurement") != PERCENTAGE:
            return None
        try:
            return float(state.state)
        except ValueError:
            return None

    def percent(self) -> float | None:
        p = self._percent_state()
        if p is not None:
            return p
        v = _liters(self.hass, self.level, None)
        return None if v is None else v / self.capacity * 100

    def volume(self) -> float | None:
        p = self._percent_state()
        if p is not None:
            return self.learner.volume(p)
        return _liters(self.hass, self.level, None)

    def full_volume(self) -> float:
        """Litres at 100 %: learned if the level is a %, else the entered capacity."""
        if self._percent_state() is not None:
            return self.learner.volume(100)
        return self.capacity

    @callback
    def on_change(self, _: Event) -> None:
        p = self._percent_state()
        if p is None:
            return
        in_l = _liters(self.hass, self.inlet, None) if self.inlet else None
        out_l = _liters(self.hass, self.outlet, None) if self.outlet else None
        if self.learner.update(p, in_l, out_l):
            self.store.async_delay_save(self.persisted, 60)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    cfg = entry.options or entry.data
    capacity = float(cfg[CONF_CAPACITY])
    level = cfg[CONF_LEVEL]
    inlet = cfg.get(CONF_INLET)
    outlet = cfg.get(CONF_OUTLET)

    store = learner_store(hass, entry.entry_id)
    data = await store.async_load()
    learner = Learner(capacity, bool(inlet), bool(outlet), data)
    model = TankModel(hass, entry.entry_id, level, inlet, outlet, capacity, learner, store, data)
    model.entry = entry
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = model
    entry.async_on_unload(lambda: hass.data[DOMAIN].pop(entry.entry_id, None))
    if not model.history_done:
        entry.async_on_unload(
            async_at_started(
                hass,
                lambda _: entry.async_create_background_task(
                    hass, model.run_import(), "eco_water_tank history import"
                ),
            )
        )
    rain_id = cfg.get(CONF_RAIN)
    if rain_id:
        model.rain = RainTracker(
            float(cfg[CONF_AREA]), float(cfg.get(CONF_EFFICIENCY, 85)) / 100, (data or {}).get("rain")
        )
        model.rain_entity = rain_id
        entry.async_on_unload(async_track_state_change_event(hass, [rain_id], model.on_rain))
    meters = [m for m in (inlet, outlet) if m]
    entry.async_on_unload(
        async_track_state_change_event(hass, [level, *meters], model.on_change)
    )

    total = dict(
        unit=UnitOfVolume.LITERS,
        device_class=SensorDeviceClass.WATER,
        state_class=SensorStateClass.TOTAL_INCREASING,
    )
    entities: list[TankSensor] = [
        TankSensor(entry, "level", [level], model.percent, unit=PERCENTAGE,
                   state_class=SensorStateClass.MEASUREMENT, precision=1),
        TankSensor(entry, "volume", [level], model.volume, unit=UnitOfVolume.LITERS,
                   device_class=SensorDeviceClass.VOLUME_STORAGE,
                   state_class=SensorStateClass.MEASUREMENT, precision=0),
        TankSensor(entry, "capacity", [level, *meters], model.full_volume,
                   unit=UnitOfVolume.LITERS, device_class=SensorDeviceClass.VOLUME_STORAGE,
                   state_class=SensorStateClass.MEASUREMENT, precision=0,
                   category=EntityCategory.DIAGNOSTIC),
    ]
    if inlet:
        entities.append(
            TankSensor(entry, "water_in", [inlet], lambda: _liters(hass, inlet, None), **total)
        )
    else:
        entities.append(DerivedInflow(entry, level, outlet, model, capacity, **total))
    if outlet:
        entities.append(
            TankSensor(entry, "water_out", [outlet], lambda: _liters(hass, outlet, None), **total)
        )
    if rain_id:
        entities += [
            TankSensor(entry, "rain_in", [rain_id], lambda: model.rain.total, estimated=True, **total),
            TankSensor(entry, "overflow", [rain_id], lambda: model.rain.overflow, estimated=True, **total),
            TankSensor(entry, "rain_efficiency", [rain_id],
                       lambda: round(model.rain.efficiency() * 100, 1), unit=PERCENTAGE,
                       state_class=SensorStateClass.MEASUREMENT, precision=0,
                       category=EntityCategory.DIAGNOSTIC),
        ]
    async_add_entities(entities)


class TankSensor(SensorEntity):
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        entry: ConfigEntry,
        key: str,
        sources: list[str],
        compute: Callable[[], float | None],
        *,
        unit: str,
        state_class: SensorStateClass,
        device_class: SensorDeviceClass | None = None,
        precision: int | None = None,
        category: EntityCategory | None = None,
        estimated: bool = False,
    ) -> None:
        self._sources = sources
        self._compute = compute
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_translation_key = key
        self._attr_native_unit_of_measurement = unit
        self._attr_state_class = state_class
        self._attr_device_class = device_class
        self._attr_suggested_display_precision = precision
        self._attr_entity_category = category
        if estimated:
            self._attr_extra_state_attributes = {"estimated": True}
        self._attr_device_info = device_info(entry)
        self._signal = refresh_signal(entry.entry_id)

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_track_state_change_event(self.hass, self._sources, self._changed)
        )
        self.async_on_remove(async_dispatcher_connect(self.hass, self._signal, self._changed))
        self._attr_native_value = self._compute()

    @callback
    def _changed(self, _: Event | None = None) -> None:
        self._attr_native_value = self._compute()
        self.async_write_ha_state()


class DerivedInflow(TankSensor, RestoreEntity):
    """Water in = rise of volume + water drawn out (no inlet meter)."""

    def __init__(self, entry, level, outlet, model, capacity, **kw) -> None:
        self._outlet = outlet
        self._tracker = InflowTracker(threshold=capacity * 0.01)
        self._volume = model.volume
        sources = [level] + ([outlet] if outlet else [])
        model.intake_tracker = self._tracker
        super().__init__(
            entry, "water_in_estimated", sources, self._derive, estimated=True, **kw
        )

    def _derive(self) -> float:
        vol = self._volume()
        out = _liters(self.hass, self._outlet, None) if self._outlet else 0.0
        if vol is None or out is None:
            return self._tracker.total
        return self._tracker.update(vol, out)

    async def async_added_to_hass(self) -> None:
        last = await self.async_get_last_state()
        try:
            self._tracker.total = float(last.state) if last else 0.0
        except ValueError:
            pass
        await super().async_added_to_hass()
