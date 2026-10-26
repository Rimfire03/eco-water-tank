"""Correction inputs: type the real volume (L) or fill (%), then press "Apply correction"."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfVolume
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
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
    """Pending value: kept in the model, cleared once the correction is applied."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_mode = NumberMode.BOX
    _attr_entity_category = EntityCategory.CONFIG
    _attr_native_min_value = 0
    _attr_native_value = None

    def __init__(self, entry: ConfigEntry, kind: str, unit: str, maximum: float, step: float) -> None:
        self._entry_id = entry.entry_id
        self._kind = kind  # "volume" | "percent"
        self._attr_unique_id = f"{entry.entry_id}_calibrate_{kind}"
        self._attr_translation_key = f"calibrate_{kind}"
        self._attr_native_unit_of_measurement = unit
        self._attr_native_max_value = maximum
        self._attr_native_step = step
        self._attr_device_info = device_info(entry)

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(self.hass, correction_signal(self._entry_id), self._clear)
        )

    @callback
    def _clear(self, kind: str) -> None:
        """kind: the entry to clear ("all" once applied, or the one the user just left)."""
        if kind in ("all", self._kind) and self._attr_native_value is not None:
            self._attr_native_value = None
            self.async_write_ha_state()

    async def async_set_native_value(self, value: float) -> None:
        # the model lives in hass.data once the sensor platform has set up
        self.hass.data[DOMAIN][self._entry_id].set_pending(self._kind, value)
        self._attr_native_value = value
        self.async_write_ha_state()
