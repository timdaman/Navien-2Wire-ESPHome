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
    "burner": binary_sensor.binary_sensor_schema(device_class=DEVICE_CLASS_HEAT, icon="mdi:fire"),
    "pump": binary_sensor.binary_sensor_schema(device_class=DEVICE_CLASS_RUNNING, icon="mdi:pump"),
    "demand": binary_sensor.binary_sensor_schema(icon="mdi:water-pump"),
    "heater_link": binary_sensor.binary_sensor_schema(
        device_class=DEVICE_CLASS_CONNECTIVITY, entity_category=ENTITY_CATEGORY_DIAGNOSTIC
    ),
    "power_on_bus": binary_sensor.binary_sensor_schema(entity_category=ENTITY_CATEGORY_DIAGNOSTIC),
    "preheat_on_bus": binary_sensor.binary_sensor_schema(entity_category=ENTITY_CATEGORY_DIAGNOSTIC),
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
