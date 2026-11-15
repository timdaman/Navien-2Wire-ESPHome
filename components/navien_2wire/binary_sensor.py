# The `binary_sensor: - platform: navien_2wire` block. Same pattern as sensor.py: for each key
# present, to_code() creates a binary sensor and calls set_<key>_binary_sensor() (navien.h).
import esphome.codegen as cg
from esphome.components import binary_sensor
import esphome.config_validation as cv
from esphome.const import (
    DEVICE_CLASS_CONNECTIVITY,
    DEVICE_CLASS_HEAT,
    DEVICE_CLASS_RUNNING,
    ENTITY_CATEGORY_DIAGNOSTIC,
)

from . import CONF_NAVIEN_ID, NavienComponent

BINARY_SENSORS = {
    # register 0x00 bits 0x08 / 0x80 / 0x20
    "burner": binary_sensor.binary_sensor_schema(device_class=DEVICE_CLASS_HEAT, icon="mdi:fire"),
    "pump": binary_sensor.binary_sensor_schema(device_class=DEVICE_CLASS_RUNNING, icon="mdi:pump"),
    "demand": binary_sensor.binary_sensor_schema(icon="mdi:water-pump"),
    # on while the heater has replied in the last 5 s
    "heater_link": binary_sensor.binary_sensor_schema(
        device_class=DEVICE_CLASS_CONNECTIVITY, entity_category=ENTITY_CATEGORY_DIAGNOSTIC
    ),
}

CONFIG_SCHEMA = cv.Schema(
    {cv.GenerateID(CONF_NAVIEN_ID): cv.use_id(NavienComponent)}
    | {cv.Optional(key): schema for key, schema in BINARY_SENSORS.items()}
)


async def to_code(config):
    parent = await cg.get_variable(config[CONF_NAVIEN_ID])
    for key in BINARY_SENSORS:
        if key in config:
            var = await binary_sensor.new_binary_sensor(config[key])
            cg.add(getattr(parent, f"set_{key}_binary_sensor")(var))
