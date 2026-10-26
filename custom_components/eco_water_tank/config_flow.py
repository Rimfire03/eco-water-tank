"""Config + options flow."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    CONF_CAPACITY,
    CONF_HEIGHT,
    CONF_INLET,
    CONF_LENGTH,
    CONF_LEVEL,
    CONF_MODEL,
    CONF_OUTLET,
    CONF_WIDTH,
    DOMAIN,
)
from .models import CUSTOM, MODELS, box_liters

DIMS = (CONF_WIDTH, CONF_LENGTH, CONF_HEIGHT)


def _box(d: dict[str, Any]) -> float | None:
    """Litres of the typed width x length x height, if all three are set."""
    if all(d.get(k) for k in DIMS):
        return box_liters(*(d[k] for k in DIMS))
    return None


def _entity(device_class: SensorDeviceClass | None = None) -> selector.EntitySelector:
    cfg: dict[str, Any] = {"domain": ["sensor", "input_number"]}
    if device_class:
        cfg["device_class"] = [device_class]
    return selector.EntitySelector(selector.EntitySelectorConfig(**cfg))


def _schema(d: dict[str, Any], with_name: bool) -> vol.Schema:
    def suggested(key: str) -> dict[str, Any]:
        return {"suggested_value": d[key]} if d.get(key) else {}

    model = d.get(CONF_MODEL, CUSTOM)
    capacity = d.get(CONF_CAPACITY)
    # capacity equal to the model's / the dimensions' volume is not an override: leave it empty
    if (model in MODELS and capacity == MODELS[model].liters) or (
        model == CUSTOM and capacity == _box(d)
    ):
        capacity = None

    options = [selector.SelectOptionDict(value=k, label=m.label) for k, m in MODELS.items()]
    options.append(selector.SelectOptionDict(value=CUSTOM, label="Custom / Personnalisée"))

    fields: dict[Any, Any] = {}
    if with_name:
        fields[vol.Required(CONF_NAME, default="Réservoir")] = str
    fields[vol.Required(CONF_MODEL, default=model)] = selector.SelectSelector(
        selector.SelectSelectorConfig(options=options, mode=selector.SelectSelectorMode.DROPDOWN)
    )
    fields[
        vol.Optional(CONF_CAPACITY, description={"suggested_value": capacity} if capacity else {})
    ] = selector.NumberSelector(
        selector.NumberSelectorConfig(
            min=1, max=10_000_000, mode=selector.NumberSelectorMode.BOX,
            unit_of_measurement="L",
        )
    )
    for key in DIMS:  # custom rectangular tank: capacity = width x length x height
        fields[vol.Optional(key, description=suggested(key))] = selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=1, max=100_000, mode=selector.NumberSelectorMode.BOX,
                unit_of_measurement="cm",
            )
        )
    fields[vol.Required(CONF_LEVEL, description=suggested(CONF_LEVEL))] = _entity()
    fields[vol.Optional(CONF_INLET, description=suggested(CONF_INLET))] = _entity(
        SensorDeviceClass.WATER
    )
    fields[vol.Optional(CONF_OUTLET, description=suggested(CONF_OUTLET))] = _entity(
        SensorDeviceClass.WATER
    )
    return vol.Schema(fields)


def _resolve_capacity(user_input: dict[str, Any], errors: dict[str, str]) -> None:
    """Capacity = typed value, else the model's volume, else width x length x height."""
    if user_input.get(CONF_CAPACITY) is None:
        model = MODELS.get(user_input[CONF_MODEL])
        capacity = model.liters if model else _box(user_input)
        if capacity is None:
            errors[CONF_CAPACITY] = "capacity_required"
            return
        user_input[CONF_CAPACITY] = capacity


class EcoWaterTankFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}
        if user_input is not None:
            _resolve_capacity(user_input, errors)
            if not errors:
                return self.async_create_entry(title=user_input.pop(CONF_NAME), data=user_input)
        return self.async_show_form(
            step_id="user", data_schema=_schema(user_input or {}, True), errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return TankOptionsFlow()


class TankOptionsFlow(OptionsFlow):
    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}
        if user_input is not None:
            _resolve_capacity(user_input, errors)
            if not errors:
                # full replacement so an emptied optional meter is really removed
                return self.async_create_entry(data=user_input)
        current = user_input or dict(self.config_entry.options or self.config_entry.data)
        return self.async_show_form(
            step_id="init", data_schema=_schema(current, False), errors=errors
        )
