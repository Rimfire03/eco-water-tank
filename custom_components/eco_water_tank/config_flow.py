"""Config + options flow: model -> (size, only for a custom tank) -> sensors."""

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


def _number(maximum: float, unit: str) -> selector.NumberSelector:
    return selector.NumberSelector(
        selector.NumberSelectorConfig(
            min=1, max=maximum, mode=selector.NumberSelectorMode.BOX, unit_of_measurement=unit
        )
    )


def _suggest(d: dict[str, Any], key: str) -> dict[str, Any]:
    return {"suggested_value": d[key]} if d.get(key) else {}


def _model_schema(d: dict[str, Any], with_name: bool) -> vol.Schema:
    options = [selector.SelectOptionDict(value=k, label=m.label) for k, m in MODELS.items()]
    options.append(selector.SelectOptionDict(value=CUSTOM, label="Custom / Personnalisée"))
    fields: dict[Any, Any] = {}
    if with_name:
        fields[vol.Required(CONF_NAME, default=d.get(CONF_NAME, "Réservoir"))] = str
    fields[vol.Required(CONF_MODEL, default=d.get(CONF_MODEL, CUSTOM))] = selector.SelectSelector(
        selector.SelectSelectorConfig(options=options, mode=selector.SelectSelectorMode.DROPDOWN)
    )
    return vol.Schema(fields)


def _size_schema(d: dict[str, Any]) -> vol.Schema:
    capacity = None if d.get(CONF_CAPACITY) == _box(d) else d.get(CONF_CAPACITY)
    return vol.Schema(
        {
            vol.Optional(
                CONF_CAPACITY, description={"suggested_value": capacity} if capacity else {}
            ): _number(10_000_000, "L"),
            **{vol.Optional(k, description=_suggest(d, k)): _number(100_000, "cm") for k in DIMS},
        }
    )


def _sensors_schema(d: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_LEVEL, description=_suggest(d, CONF_LEVEL)): _entity(),
            vol.Optional(CONF_INLET, description=_suggest(d, CONF_INLET)): _entity(
                SensorDeviceClass.WATER
            ),
            vol.Optional(CONF_OUTLET, description=_suggest(d, CONF_OUTLET)): _entity(
                SensorDeviceClass.WATER
            ),
        }
    )


class _Steps:
    """Shared steps. Subclasses give `_with_name` and `_finish()`."""

    _with_name = True

    def __init__(self) -> None:
        super().__init__()
        self._data: dict[str, Any] = {}

    async def _model_step(self, step_id: str, user_input: dict[str, Any] | None):
        if user_input is None:
            return self.async_show_form(
                step_id=step_id, data_schema=_model_schema(self._data, self._with_name)
            )
        self._data.update(user_input)
        model = MODELS.get(user_input[CONF_MODEL])
        if model is None:
            return await self.async_step_size()
        # known model: its volume is used, no size to type
        self._data[CONF_CAPACITY] = model.liters
        for k in DIMS:
            self._data.pop(k, None)
        return await self.async_step_sensors()

    async def async_step_size(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}
        if user_input is not None:
            capacity = user_input.get(CONF_CAPACITY) or _box(user_input)
            if capacity is None:
                errors[CONF_CAPACITY] = "capacity_required"
            else:
                for k in (CONF_CAPACITY, *DIMS):
                    self._data.pop(k, None)
                self._data.update(user_input)
                self._data[CONF_CAPACITY] = capacity
                return await self.async_step_sensors()
        return self.async_show_form(
            step_id="size", data_schema=_size_schema(user_input or self._data), errors=errors
        )

    async def async_step_sensors(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            # full replacement so an emptied optional meter is really removed
            for k in (CONF_INLET, CONF_OUTLET):
                self._data.pop(k, None)
            self._data.update(user_input)
            return await self._finish()
        return self.async_show_form(step_id="sensors", data_schema=_sensors_schema(self._data))


class EcoWaterTankFlow(_Steps, ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        return await self._model_step("user", user_input)

    async def _finish(self):
        return self.async_create_entry(title=self._data.pop(CONF_NAME), data=self._data)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return TankOptionsFlow()


class TankOptionsFlow(_Steps, OptionsFlow):
    _with_name = False

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        if user_input is None:
            self._data = dict(self.config_entry.options or self.config_entry.data)
        return await self._model_step("init", user_input)

    async def _finish(self):
        return self.async_create_entry(data=self._data)
