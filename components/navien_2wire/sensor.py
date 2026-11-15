# The `sensor: - platform: navien_2wire` block. Every key is optional; for each one present,
# to_code() creates a sensor and hands it to the component with set_<key>_sensor() (navien.h).
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

# Shared settings for each kind of sensor. These are the defaults; the YAML can override them.
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

# YAML key -> schema. Each key needs a matching set_<key>_sensor() in navien.h.
SENSORS = {
    "outlet_temperature": _TEMP,  # register 0x1A
    "inlet_temperature": _TEMP,  # register 0x96
    "status_raw": _DIAG,  # register 0x00, both data bytes
    "register_d3": _DIAG,  # register 0xD3, both data bytes (meaning unknown)
    "frames_ok": _COUNT,  # frames decoded since boot
    "frames_bad": _COUNT,  # bursts that failed to decode since boot
}

CONFIG_SCHEMA = cv.Schema(
    # navien_id: which navien_2wire component these belong to (filled in automatically).
    {cv.GenerateID(CONF_NAVIEN_ID): cv.use_id(NavienComponent)}
    | {cv.Optional(key): schema for key, schema in SENSORS.items()}
)


async def to_code(config):
    parent = await cg.get_variable(config[CONF_NAVIEN_ID])  # the NavienComponent
    for key in SENSORS:
        if key in config:
            var = await sensor.new_sensor(config[key])
            cg.add(getattr(parent, f"set_{key}_sensor")(var))
