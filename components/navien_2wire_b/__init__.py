# navien_2wire_b: navien_2wire plus a Listen mode and *_on_bus entities, for the untested
# comparator board in hardware/other-ideas.md. Use navien_2wire for the published board.
import esphome.codegen as cg
from esphome.components import remote_base
import esphome.config_validation as cv
from esphome.const import CONF_ID

CODEOWNERS = []
DEPENDENCIES = ["remote_receiver", "remote_transmitter"]
MULTI_CONF = False

CONF_NAVIEN_ID = "navien_id"
CONF_POLL_INTERVAL = "poll_interval"

navien_ns = cg.esphome_ns.namespace("navien_2wire_b")
NavienComponent = navien_ns.class_(
    "NavienComponent",
    cg.Component,
    remote_base.RemoteReceiverListener,
    remote_base.RemoteTransmittable,
)

CONFIG_SCHEMA = (
    cv.Schema(
        {
            cv.GenerateID(): cv.declare_id(NavienComponent),
            # The original remote sends one frame every 300-600 ms.
            cv.Optional(
                CONF_POLL_INTERVAL, default="400ms"
            ): cv.All(
                cv.positive_time_period_milliseconds,
                cv.Range(min=cv.TimePeriod(milliseconds=300)),
            ),
        }
    )
    .extend(remote_base.REMOTE_LISTENER_SCHEMA)
    .extend(remote_base.REMOTE_TRANSMITTABLE_SCHEMA)
    .extend(cv.COMPONENT_SCHEMA)
)


async def to_code(config):
    var = cg.new_Pvariable(config[CONF_ID])
    await cg.register_component(var, config)
    await remote_base.register_listener(var, config)
    await remote_base.register_transmittable(var, config)
    cg.add(var.set_poll_interval(config[CONF_POLL_INTERVAL]))
