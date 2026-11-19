# The `number: - platform: navien_2wire` block: the setpoint control. Like switch.py, it has
# its own C++ class (NavienSetpointNumber in navien.h) whose control() passes HA's value on
# to the component's set_setpoint().
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
                # Full range of the heater (98-140 °F). Above 120 °F the component rounds to 5 °F steps
                # (see valid_setpoint in navien_codec.h). Narrow it here to limit what HA offers.
                cv.Optional(CONF_MIN_VALUE, default=98): cv.int_range(min=98, max=140),
                cv.Optional(CONF_MAX_VALUE, default=140): cv.int_range(min=98, max=140),
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
        await cg.register_parented(var, parent)  # sets the number's parent_ (used by control)
        cg.add(parent.set_setpoint_number(var))
