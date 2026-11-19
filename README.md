# navien-esphome

ESPHome replacement for the 2-wire wall remote of older **Navien NR-series** tankless water heaters (developed on an NR-210A).
It brings temperatures, burner and pump status, setpoint, power and **preheat (recirculation) control** into Home Assistant.

> ⚠️ Status: protocol decoded; the interface board is built, passes every bench test ([reference readings](hardware/bring-up.md#reference-readings-from-a-working-board)),
> and runs on a NR-210A (heater link, temperatures and burner status confirmed).
> The board only sends frames the original remote was seen sending.

## How it works

The board takes the place of the original 2Wire controls. It plugs into the same connector on the heater's control board (CN12, JST VH), so going back to stock controller is a matter of moving one plug.
See [docs/protocol.md](docs/protocol.md) for the bus details and [hardware/](hardware/) for the isolated interface board (schematics, parts, PCB).
For a part-by-part explanation of the board, see the [Detailed walkthrough of circuit operation](hardware/circuit-walkthrough.md). To test a built board, follow [hardware/bring-up.md](hardware/bring-up.md).
[Other ideas, untested](hardware/other-ideas.md) collects designs that were never built, such as a board that can listen alongside the original remote.

## ESPHome

The `navien_2wire` component should work on any board that ESPHome's `remote_receiver` / `remote_transmitter` support: Was tested with a ESP32 dev board. It needs two GPIOs, Ground, and 3.3 V.

Everything Navien-related is in one package file, [example/navien-package.yaml](example/navien-package.yaml).
Add it to any device's YAML and set the two pins:

```yaml
external_components:
  - source: github://<you>/navien-esphome
    components: [navien_2wire]

packages:
  navien: github://<you>/navien-esphome/example/navien-package.yaml   # or a local !include

substitutions:
  navien_rx_pin: GPIO4      # interface board RX (output of the H11L1)
  navien_tx_pin: GPIO5      # interface board TX (drives the PC817)
```

[example/navien-remote.yaml](example/navien-remote.yaml) is a complete dedicated-board config (shown for an ESP32-DevKitC).

### Pins

Use two of the chip's **internal** GPIOs. The receive pin needs edge interrupts (or RMT on ESP32).
**I2C/SPI port expanders (MCP23017, PCF8574, …) can't be used.** ESPHome rejects them for `remote_receiver`/`remote_transmitter`,
and the bus needs edge timing to about ±0.1 ms, which an I2C round trip can't deliver (see below).

* **ESP32 family:** RX and TX each use one RMT channel (shared with LED strips and IR). You can add `non_blocking: true` to the transmitter.
* **ESP8266 / RP2040:** the transmitter bit-bangs each 34 ms frame, briefly blocking the main loop about every 0.4 s. That's fine for a few other sensors, but on a very busy device prefer an ESP32.

### Why not a GPIO expander?

The bus sends a level change every 0.5 or 1 ms, and the receiver must time each edge to within about ±0.1 ms to tell them apart.
An expander only reports pin changes through an interrupt line followed by an I2C read: ≈0.1–0.3 ms at 400 kHz, plus however long the main loop takes to get around to it.
That's the same size as the margin, and transmitting would need a timed I2C write every 0.5 ms for 34 ms at a stretch.

The interface board's 3V3 pin can come from any 3.3 V supply on the device (it draws a few mA). The heater bus is fully **galvanically isolated**, there are no ground connections between the microcontroller and heater.

### Entities

Every entity is optional. The package enables all the useful ones:

| Platform | Keys |
|---|---|
| `sensor` | `outlet_temperature`, `inlet_temperature`, `status_raw`, `register_d3`, `frames_ok`, `frames_bad` |
| `binary_sensor` | `burner`, `pump`, `demand`, `heater_link` |
| `switch` | `power`, `preheat` |
| `number` | `setpoint` (`min_value` / `max_value`, default 98–140 °F; the steps aren't even, see [Setpoint steps](#setpoint-steps)) |

The board is the bus master: it starts polling the heater as soon as it boots, like the original remote. Setpoint, power and preheat are saved in flash
(defaults on first boot: 120 °F, power on, preheat off).
Heater does not transmit it's internal settings so set point, power and preheat status are managed blindly. Heater reports measured values; burner status, demand, and internal temperatures.

### Setpoint steps

The setpoint doesn't go up in even steps. Like the original remote, it moves **1 °F at a time up to 120 °F, then 5 °F at a time**:

| Range | Step | Values the heater can be sent |
|---|---|---|
| 98–120 °F | 1 °F | 98, 99, 100, … 119, 120 |
| 120–140 °F | 5 °F | 125, 130, 135, 140 |

Home Assistant's slider still moves 1 °F at a time across the whole range, because an ESPHome number can only have one step size.
When you pick a value between the 5 °F steps, the board rounds it to the nearest valid one, sends that, and the slider jumps to it:

| You set | Heater gets |
|---|---|
| 121 or 122 | 120 |
| 123 to 127 | 125 |
| 128 to 132 | 130 |
| 133 to 137 | 135 |
| 138 to 140 | 140 |

An automation that sets, say, 124 °F will see the setpoint read back as 125 °F. Use one of the values in the first table to avoid that.

Two more limits:

* **DIP switches 7/8 on the heater board cap the maximum** at 110, 120, 130 or 140 °F. The heater doesn't report this cap over the bus,
  so if you set a setpoint above it, HA shows your value but the heater quietly uses its cap. Check the switches (power off first)
  and set `max_value` to match, so HA only offers what the heater will actually do.
* **Water above 125 °F can scald.** Set `max_value` lower if that's a concern.

### Fail-safes and operating mode (optional)

[example/navien-failsafe.yaml](example/navien-failsafe.yaml) adds a **Navien operating mode** select (saved in flash) and keeps the heater
working sensibly when Home Assistant is down. Add it after the main package:

```yaml
packages:
  navien: !include navien-package.yaml
  navien_failsafe: !include navien-failsafe.yaml
```

| Mode | When chosen | 2 min after boot, or HA gone for 5 min |
|---|---|---|
| Off | power off, preheat off | nothing |
| On | power on, preheat off | power on, preheat off |
| On + preheat | power on, preheat on | power on, preheat on |
| Auto | power on; HA controls preheat | power on, preheat on |

ESPHome counts any API client as "connected", including the dashboard's log viewer, so the 5-minute timer doesn't run while you watch the logs.
In Auto mode, have your HA automation also trigger when `switch.navien_preheat` becomes available, so it re-applies preheat after an outage.

## Repository

```
components/          ESPHome external components: navien_2wire (use this), navien_2wire_b (untested, see hardware/other-ideas.md)
example/             example device config
hardware/            schematics, parts, wiring lists, PCB, and a circuit walkthrough
docs/protocol.md     bus protocol
tests/               codec test (real bus frames, including late-edge ones, + 40k jittered round trips)
tools/               Rigol SCPI capture / Manchester decode scripts used for the reverse engineering
```

Disclaimer: This is a personal project. The views, code, and opinions expressed here are my own and do not represent those of my current or past employers.