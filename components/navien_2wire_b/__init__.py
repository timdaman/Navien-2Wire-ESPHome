# navien_2wire_b: navien_2wire plus a Listen mode and *_on_bus entities, for the untested
# comparator board in hardware/other-ideas.md. Use navien_2wire for the published board.
import esphome.codegen as cg
from esphome.components import remote_base
import esphome.config_validation as cv
from esphome.const import CONF_ID, CONF_INVERTED, CONF_PIN
import esphome.final_validate as fv

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


# ---- Receiver polarity check (runs while ESPHome validates the YAML, before compiling) ----
#
# The comparator board's output goes high while the heater sends, so the pin must not be inverted.
# With the wrong setting every frame fails to decode ("Decode failed: bad timing ..." in the log),
# so catch it here instead. If you built a different interface circuit with the opposite
# polarity, change RX_INVERTED to match it.
RX_INVERTED = False


def _check_rx_polarity(config):
    full = fv.full_config.get()
    receivers = full.get("remote_receiver", [])
    if isinstance(receivers, dict):
        receivers = [receivers]
    for rx in receivers:
        if str(rx[CONF_ID]) != str(config["receiver_id"]):
            continue
        inverted = rx[CONF_PIN].get(CONF_INVERTED, False)
        if inverted != RX_INVERTED:
            raise cv.Invalid(
                f"navien_2wire_b: the pin of remote_receiver '{rx[CONF_ID]}' has inverted: "
                f"{str(inverted).lower()}, but this board needs inverted: {str(RX_INVERTED).lower()}. "
                f"Set it like this:  pin: {{ number: ..., inverted: {str(RX_INVERTED).lower()} }}"
            )
    return config


# ESPHome calls this once the whole YAML is known (it needs to see the remote_receiver block).
FINAL_VALIDATE_SCHEMA = _check_rx_polarity


async def to_code(config):
    var = cg.new_Pvariable(config[CONF_ID])
    await cg.register_component(var, config)
    await remote_base.register_listener(var, config)
    await remote_base.register_transmittable(var, config)
    cg.add(var.set_poll_interval(config[CONF_POLL_INTERVAL]))
