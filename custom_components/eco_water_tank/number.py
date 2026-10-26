"""Calibration inputs: type the real volume (L) or fill (%) of the tank now."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfVolume
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DOMAIN
from .sensor import device_info


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_entities(
        [
            CalibrationNumber(entry, "volume", UnitOfVolume.LITERS, 10_000_000, 1),
            CalibrationNumber(entry, "percent", PERCENTAGE, 100, 0.1),
        ]
    )


class CalibrationNumber(NumberEntity, RestoreEntity):
    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_mode = NumberMode.BOX
    _attr_entity_category = EntityCategory.CONFIG
    _attr_native_min_value = 0

    def __init__(self, entry: ConfigEntry, kind: str, unit: str, maximum: float, step: float) -> None:
        self._entry_id = entry.entry_id
        self._kind = kind  # "volume" | "percent": argument of TankModel.calibrate
        self._attr_unique_id = f"{entry.entry_id}_calibrate_{kind}"
        self._attr_translation_key = f"calibrate_{kind}"
        self._attr_native_unit_of_measurement = unit
        self._attr_native_max_value = maximum
        self._attr_native_step = step
        self._attr_device_info = device_info(entry)

    async def async_added_to_hass(self) -> None:
        last = await self.async_get_last_state()
        try:
            self._attr_native_value = float(last.state) if last else None
        except ValueError:
            self._attr_native_value = None

    async def async_set_native_value(self, value: float) -> None:
        # the model lives in hass.data once the sensor platform has set up
        args = {"volume": None, "percent": None, self._kind: value}
        await self.hass.data[DOMAIN][self._entry_id].calibrate(**args)
        self._attr_native_value = value
        self.async_write_ha_state()
