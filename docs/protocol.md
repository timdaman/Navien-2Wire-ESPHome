# Navien NR-series remote bus protocol

Reverse engineered on a **Navien NR-210A** (c. 2010) with its wall remote (buttons: ▲ ▼ Function Lock PRO Power), using a Rigol DHO804. The capture and decoder scripts are in `tools/`.

Status: everything below was observed on one unit. Items marked *(guess)* are not confirmed.

## Electrical

Two wires, A (+) and B (−), on the heater board's **CN12 `Remote_Controller`** connector (JST VH, 3.96 mm; A = right pin with the latch side down). The heater powers the remote over the same pair, through fusible resistors FRM1/FRM2.

| Condition | A–B voltage | Current |
|---|---|---|
| Remote unplugged (open circuit) | 19.8 V | 0 |
| Idle (remote clamping) | 6.5 V | 13.4 mA |
| Heater sending a '1' | 8.0 V | 24.4 mA |
| Remote sending a '1' | 15.7 V | 11.9 mA |

* The heater is a ~12.5 mA **current source** (≈20 V compliance). It signals by stepping its current to ~24 mA.
* The remote is a **shunt clamp** (≈4.7 V + ≈130 Ω). It signals by releasing the clamp, which lets the line rise to ~15–16 V.
* Power available to the remote: ≈85 mW. Not enough to run an ESP32 from the bus.
* The bus floats relative to earth. B sits near earth potential.
* **With no remote connected, the heater starts preheating on its own.**

## Framing

* **Manchester** coding, 500 µs half-bit (1000 bit/s). `1` = high then low, `0` = low then high.
* Frame = start bit `1` + 32 data bits (MSB first) + end bit `1` = 34 bits, ≈34 ms.
* Data = 4 bytes: `[P|flags] [register] [data_hi] [data_lo]`
  * **P** (bit 7 of byte 0): even parity over all 32 bits.
  * `0x40`: frame is from the slave (heater).
  * `0x10`: master write. Otherwise a read; the heater fills in bytes 2–3.
* **Edge timing.** The heater's edges are normally within about ±10 µs of the 500 µs grid, and the original remote's within about ±60 µs (its clock runs a few % slow).
  **While the burner runs**, a few percent of heater frames have a single edge 160–200 µs late or early, and the edges after it are back on time
  (probably the heater's firmware busy with burner control). Measured pulse by pulse that looks like a 700 µs + 300 µs pair, so a receiver should
  place each edge on the frame's bit grid instead; the component's decoder does this.

## Roles and timing

* **The remote is the bus master.** It sends one frame every 300–600 ms in a fixed round robin: `1A, 38, D3, 96, C8, 00`.
* The heater replies to each one. Its frame starts 60–167 ms after the remote's frame starts.
* The remote occasionally repeats a register (a retry, *(guess)*).

## Registers

| Reg | Direction | Bytes 2–3 | Meaning |
|---|---|---|---|
| `0x38` | remote writes | `AA tt` | **Setpoint, °F** (tt = 118, 119, 120, 125 seen). `AA` is constant |
| `0xC8` | remote writes | `ff 00` | **Mode flags**: bit 7 = power on, bit 6 = always 1 *(meaning unknown)*, bit 5 = **preheat active now** |
| `0x1A` | heater replies | `AA tt` | **Outlet temperature, °F** |
| `0x96` | heater replies | `AA tt` | **Inlet temperature, °F** |
| `0x00` | heater replies | `00 ss` | **Status**: 0x20 = hot-water demand, 0x08 = burner on, 0x80 = recirculation pump on. Seen: 0x00, 0x20, 0x28, 0x80, 0x88 |
| `0xD3` | heater replies | `00 92` | constant *(unknown: model / capacity?)* |

The heater acknowledges writes with `[P|0x50] reg 00 00`.

### Preheat

The remote evaluates its own preheat schedule (30-minute blocks, on its own clock) and sets **bit 5 of 0xC8** while a block is active.
Editing the schedule produces no bus traffic. Clearing bit 5 stops preheat, and setting it starts preheat immediately (the pump starts, status 0x80, then the burner, 0x88).

## Example exchange

```
remote: 80 1A 00 00    read outlet            heater: C0 1A AA 78   120 °F
remote: 10 38 AA 78    write setpoint 120 °F   heater: D0 38 00 00   ack
remote: 80 D3 00 00                            heater: C0 D3 00 92
remote: 00 96 00 00    read inlet             heater: C0 96 AA 3F   63 °F
remote: 90 C8 E0 00    power on, preheat on    heater: D0 C8 00 00   ack
remote: 00 00 00 00    read status            heater: C0 00 00 88   pump + burner
```

## Open questions

* The setpoint range and step rules (remote steps 119 → 120 → 125).
* Bit 6 of 0xC8, register 0xD3, and the `AA` byte.
* Where error codes appear (probably the high byte of 0x00).
* Whether other NR / NP models use the same bus.
