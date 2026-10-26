"""Button: share the tank's settings / learned curve."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .sensor import device_info


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_entities([ShareButton(entry), MarkButton(entry, True), MarkButton(entry, False)])


class ShareButton(ButtonEntity):
    _attr_has_entity_name = True
    _attr_translation_key = "share_tank"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, entry: ConfigEntry) -> None:
        self._entry_id = entry.entry_id
        self._attr_unique_id = f"{entry.entry_id}_share_tank"
        self._attr_device_info = device_info(entry)

    async def async_press(self) -> None:
        await self.hass.data[DOMAIN][self._entry_id].share()


class MarkButton(ButtonEntity):
    """Manual 'tank is full' / 'tank is empty' calibration point."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, entry: ConfigEntry, full: bool) -> None:
        self._entry_id = entry.entry_id
        self._full = full
        key = "mark_full" if full else "mark_empty"
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_translation_key = key
        self._attr_device_info = device_info(entry)

    async def async_press(self) -> None:
        await self.hass.data[DOMAIN][self._entry_id].mark_level(self._full)
