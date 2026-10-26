"""Tank sensors: level %, volume, water in, water out."""

from __future__ import annotations

from collections.abc import Callable

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfVolume
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.util.unit_conversion import VolumeConverter

from .const import CONF_CAPACITY, CONF_INLET, CONF_LEVEL, CONF_OUTLET, DOMAIN
from .tracker import InflowTracker


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


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    cfg = entry.options or entry.data
    capacity = float(cfg[CONF_CAPACITY])
    level = cfg[CONF_LEVEL]
    inlet = cfg.get(CONF_INLET)
    outlet = cfg.get(CONF_OUTLET)

    def volume() -> float | None:
        return _liters(hass, level, capacity)

    def percent() -> float | None:
        v = volume()
        return None if v is None else v / capacity * 100

    total = dict(
        unit=UnitOfVolume.LITERS,
        device_class=SensorDeviceClass.WATER,
        state_class=SensorStateClass.TOTAL_INCREASING,
    )
    entities: list[TankSensor] = [
        TankSensor(entry, "level", [level], percent, unit=PERCENTAGE,
                   state_class=SensorStateClass.MEASUREMENT, precision=1),
        TankSensor(entry, "volume", [level], volume, unit=UnitOfVolume.LITERS,
                   device_class=SensorDeviceClass.VOLUME_STORAGE,
                   state_class=SensorStateClass.MEASUREMENT, precision=0),
    ]
    if inlet:
        entities.append(
            TankSensor(entry, "water_in", [inlet], lambda: _liters(hass, inlet, None), **total)
        )
    else:
        entities.append(
            DerivedInflow(entry, hass, level, outlet, volume, capacity, **total)
        )
    if outlet:
        entities.append(
            TankSensor(entry, "water_out", [outlet], lambda: _liters(hass, outlet, None), **total)
        )
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
    ) -> None:
        self._sources = sources
        self._compute = compute
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_translation_key = key
        self._attr_native_unit_of_measurement = unit
        self._attr_state_class = state_class
        self._attr_device_class = device_class
        self._attr_suggested_display_precision = precision
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)}, name=entry.title
        )

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_track_state_change_event(self.hass, self._sources, self._changed)
        )
        self._attr_native_value = self._compute()

    @callback
    def _changed(self, _: Event) -> None:
        self._attr_native_value = self._compute()
        self.async_write_ha_state()


class DerivedInflow(TankSensor, RestoreEntity):
    """Water in = rise of volume + water drawn out (no inlet meter)."""

    def __init__(self, entry, hass, level, outlet, volume, capacity, **kw) -> None:
        self._outlet = outlet
        self._tracker = InflowTracker(threshold=capacity * 0.01)
        self._volume = volume
        sources = [level] + ([outlet] if outlet else [])
        super().__init__(entry, "water_in", sources, self._derive, **kw)

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
