import esphome.codegen as cg
from esphome.components import sensor
import esphome.config_validation as cv
from esphome.const import (
    DEVICE_CLASS_TEMPERATURE,
    ENTITY_CATEGORY_DIAGNOSTIC,
    STATE_CLASS_MEASUREMENT,
    STATE_CLASS_TOTAL_INCREASING,
)

from . import CONF_NAVIEN_ID, NavienComponent

UNIT_FAHRENHEIT = "°F"

_TEMP = sensor.sensor_schema(
    unit_of_measurement=UNIT_FAHRENHEIT,
    accuracy_decimals=0,
    device_class=DEVICE_CLASS_TEMPERATURE,
    state_class=STATE_CLASS_MEASUREMENT,
)
_DIAG = sensor.sensor_schema(accuracy_decimals=0, entity_category=ENTITY_CATEGORY_DIAGNOSTIC)
_COUNT = sensor.sensor_schema(
    accuracy_decimals=0,
    state_class=STATE_CLASS_TOTAL_INCREASING,
    entity_category=ENTITY_CATEGORY_DIAGNOSTIC,
)

SENSORS = {
    "outlet_temperature": _TEMP,
    "inlet_temperature": _TEMP,
    "setpoint_on_bus": _TEMP,
    "status_raw": _DIAG,
    "register_d3": _DIAG,
    "frames_ok": _COUNT,
    "frames_bad": _COUNT,
}

CONFIG_SCHEMA = cv.Schema(
    {cv.GenerateID(CONF_NAVIEN_ID): cv.use_id(NavienComponent)}
    | {cv.Optional(key): schema for key, schema in SENSORS.items()}
)


async def to_code(config):
    parent = await cg.get_variable(config[CONF_NAVIEN_ID])
    for key in SENSORS:
        if key in config:
            var = await sensor.new_sensor(config[key])
            cg.add(getattr(parent, f"set_{key}_sensor")(var))
