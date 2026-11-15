import esphome.codegen as cg
from esphome.components import number
import esphome.config_validation as cv
from esphome.const import CONF_MAX_VALUE, CONF_MIN_VALUE, DEVICE_CLASS_TEMPERATURE

from . import CONF_NAVIEN_ID, NavienComponent, navien_ns

NavienSetpointNumber = navien_ns.class_("NavienSetpointNumber", number.Number)

CONFIG_SCHEMA = cv.Schema(
    {
        cv.GenerateID(CONF_NAVIEN_ID): cv.use_id(NavienComponent),
        cv.Optional("setpoint"): number.number_schema(
            NavienSetpointNumber,
            unit_of_measurement="°F",
            device_class=DEVICE_CLASS_TEMPERATURE,
            icon="mdi:thermometer-water",
        ).extend(
            {
                # Only the range observed on the original remote is allowed by default.
                cv.Optional(CONF_MIN_VALUE, default=100): cv.int_range(min=95, max=140),
                cv.Optional(CONF_MAX_VALUE, default=120): cv.int_range(min=95, max=140),
            }
        ),
    }
)


async def to_code(config):
    parent = await cg.get_variable(config[CONF_NAVIEN_ID])
    if "setpoint" in config:
        conf = config["setpoint"]
        var = await number.new_number(
            conf, min_value=conf[CONF_MIN_VALUE], max_value=conf[CONF_MAX_VALUE], step=1
        )
        await cg.register_parented(var, parent)
        cg.add(parent.set_setpoint_number(var))
