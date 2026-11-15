# The `switch: - platform: navien_2wire` block: the power and preheat controls.
# Unlike sensors, switches need their own C++ classes (NavienPowerSwitch, NavienPreheatSwitch in
# navien.h), because HA turning one on or off has to reach the component: ESPHome calls the
# class's write_state(), which calls the component's set_power() / set_preheat().
import esphome.codegen as cg
from esphome.components import switch
import esphome.config_validation as cv

from . import CONF_NAVIEN_ID, NavienComponent, navien_ns

NavienPowerSwitch = navien_ns.class_("NavienPowerSwitch", switch.Switch)
NavienPreheatSwitch = navien_ns.class_("NavienPreheatSwitch", switch.Switch)

CONFIG_SCHEMA = cv.Schema(
    {
        cv.GenerateID(CONF_NAVIEN_ID): cv.use_id(NavienComponent),
        cv.Optional("power"): switch.switch_schema(NavienPowerSwitch, icon="mdi:power"),
        cv.Optional("preheat"): switch.switch_schema(NavienPreheatSwitch, icon="mdi:water-boiler"),
    }
)


async def to_code(config):
    parent = await cg.get_variable(config[CONF_NAVIEN_ID])
    for key in ("power", "preheat"):
        if key in config:
            var = await switch.new_switch(config[key])
            await cg.register_parented(var, parent)  # sets the switch's parent_ (used by write_state)
            cg.add(getattr(parent, f"set_{key}_switch")(var))
