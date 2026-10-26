"""Button: share a custom tank's settings (custom tanks only)."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_MODEL, DOMAIN
from .models import CUSTOM
from .sensor import device_info


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    if (entry.options or entry.data).get(CONF_MODEL, CUSTOM) == CUSTOM:
        async_add_entities([ShareButton(entry)])


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
