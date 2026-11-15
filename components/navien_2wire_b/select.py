import esphome.codegen as cg
from esphome.components import select
import esphome.config_validation as cv
from esphome.const import ENTITY_CATEGORY_CONFIG

from . import CONF_NAVIEN_ID, NavienComponent, navien_ns

NavienModeSelect = navien_ns.class_("NavienModeSelect", select.Select)

CONFIG_SCHEMA = cv.Schema(
    {
        cv.GenerateID(CONF_NAVIEN_ID): cv.use_id(NavienComponent),
        cv.Optional("mode"): select.select_schema(
            NavienModeSelect, entity_category=ENTITY_CATEGORY_CONFIG, icon="mdi:swap-horizontal"
        ),
    }
)


async def to_code(config):
    parent = await cg.get_variable(config[CONF_NAVIEN_ID])
    if "mode" in config:
        # Index 0 = Listen, 1 = Master (matches BusMode in navien.h).
        var = await select.new_select(config["mode"], options=["Listen", "Master"])
        await cg.register_parented(var, parent)
        cg.add(parent.set_mode_select(var))
