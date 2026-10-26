"""Eco Water Tank: a water tank (level + inlet/outlet meters) as sensors."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN

PLATFORMS = ["sensor", "number", "button"]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    async def import_history(call: ServiceCall) -> None:
        for model in list(hass.data.get(DOMAIN, {}).values()):
            await model.run_import()

    async def calibrate(call: ServiceCall) -> None:
        await pick(call).calibrate(call.data.get("volume"), call.data.get("percent"))

    def pick(call: ServiceCall):
        models = hass.data.get(DOMAIN, {})
        model = models.get(call.data.get("config_entry")) or (
            next(iter(models.values())) if len(models) == 1 else None
        )
        if model is None:
            raise ServiceValidationError("Select the tank (config_entry)")
        return model

    async def share_tank(call: ServiceCall) -> dict:
        return await pick(call).share()

    hass.services.async_register(DOMAIN, "import_history", import_history)
    hass.services.async_register(
        DOMAIN,
        "share_tank",
        share_tank,
        schema=vol.Schema({vol.Optional("config_entry"): cv.string}),
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN,
        "calibrate",
        calibrate,
        schema=vol.Schema(
            {
                vol.Optional("config_entry"): cv.string,
                vol.Optional("volume"): vol.Coerce(float),
                vol.Optional("percent"): vol.Coerce(float),
            }
        ),
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_reload))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    from .sensor import learner_store

    await learner_store(hass, entry.entry_id).async_remove()


async def _reload(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
