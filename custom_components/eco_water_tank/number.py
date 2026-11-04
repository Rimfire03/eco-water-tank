"""Correction inputs: type the real volume (L) or fill (%), then press "Apply correction"."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfVolume
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event

from .const import CONF_LEVEL, DOMAIN
from .sensor import correction_signal, device_info


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_entities(
        [
            CorrectionNumber(entry, "volume", UnitOfVolume.LITERS, 10_000_000, 1),
            CorrectionNumber(entry, "percent", PERCENTAGE, 100, 0.1),
        ]
    )


class CorrectionNumber(NumberEntity):
    """Pending value kept in the model until "Apply correction". The level reading defaults to
    the current level, so it only needs typing for a level noted earlier."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_mode = NumberMode.BOX
    _attr_entity_category = EntityCategory.CONFIG
    _attr_native_min_value = 0

    def __init__(self, entry: ConfigEntry, kind: str, unit: str, maximum: float, step: float) -> None:
        self._entry_id = entry.entry_id
        self._level = (entry.options or entry.data)[CONF_LEVEL]
        self._kind = kind  # "volume" | "percent"
        self._attr_unique_id = f"{entry.entry_id}_calibrate_{kind}"
        self._attr_translation_key = f"calibrate_{kind}"
        self._attr_native_unit_of_measurement = unit
        self._attr_native_max_value = maximum
        self._attr_native_step = step
        self._attr_device_info = device_info(entry)

    @property
    def native_value(self) -> float | None:
        model = self.hass.data.get(DOMAIN, {}).get(self._entry_id)
        if model is None:
            return None
        pending = model.pending[self._kind]
        if pending is not None or self._kind == "volume":
            return pending
        p = model.percent()  # default: the current level
        return None if p is None else round(p, 1)

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(self.hass, correction_signal(self._entry_id), self._refresh)
        )
        if self._kind == "percent":
            self.async_on_remove(
                async_track_state_change_event(self.hass, [self._level], self._refresh)
            )

    @callback
    def _refresh(self, *_) -> None:
        self.async_write_ha_state()

    async def async_set_native_value(self, value: float) -> None:
        # the model lives in hass.data once the sensor platform has set up
        self.hass.data[DOMAIN][self._entry_id].set_pending(self._kind, value)
        self.async_write_ha_state()
