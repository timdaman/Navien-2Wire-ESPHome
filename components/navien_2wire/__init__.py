# navien_2wire: replaces the 2-wire wall remote of a Navien NR-series heater (the board is the bus master).
#
# This file runs when the firmware is compiled, not on the ESP. It handles the top-level YAML block
#
#   navien_2wire:
#     receiver_id: navien_rx
#     transmitter_id: navien_tx
#     poll_interval: 400ms      # optional
#
# CONFIG_SCHEMA checks that block, and to_code() turns it into C++ that creates the
# NavienComponent (navien.h) at boot. The entity platforms (sensor.py, switch.py, ...) then
# attach their entities to that same object.
import esphome.codegen as cg
from esphome.components import remote_base
import esphome.config_validation as cv
from esphome.const import CONF_ID

CODEOWNERS = []
# ESPHome refuses to build unless these components are also in the YAML.
DEPENDENCIES = ["remote_receiver", "remote_transmitter"]
# Only one navien_2wire: block per device.
MULTI_CONF = False

# YAML key the entity platforms use to point at this component. It's filled in automatically
# when there's only one, so users never need to write it.
CONF_NAVIEN_ID = "navien_id"
CONF_POLL_INTERVAL = "poll_interval"

# Python handles for the C++ namespace and class, so generated code can name them.
# The base classes listed must match the ones in navien.h.
navien_ns = cg.esphome_ns.namespace("navien_2wire")
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
    # Adds the `receiver_id:` key (which remote_receiver to listen to) ...
    .extend(remote_base.REMOTE_LISTENER_SCHEMA)
    # ... the `transmitter_id:` key (which remote_transmitter to send with) ...
    .extend(remote_base.REMOTE_TRANSMITTABLE_SCHEMA)
    # ... and the keys every component accepts (e.g. setup_priority).
    .extend(cv.COMPONENT_SCHEMA)
)


# Generates the C++ for the validated config. Each line becomes one statement in the
# firmware's generated main.cpp.
async def to_code(config):
    var = cg.new_Pvariable(config[CONF_ID])  # new NavienComponent()
    await cg.register_component(var, config)  # ESPHome will call its setup()/loop()
    await remote_base.register_listener(var, config)  # receiver->register_listener(var): on_receive()
    await remote_base.register_transmittable(var, config)  # var->set_transmitter(...): transmitter_
    cg.add(var.set_poll_interval(config[CONF_POLL_INTERVAL]))  # milliseconds
