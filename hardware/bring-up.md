# Bench bring-up: testing the board before it touches the heater

These tests check every function of the interface board with simple bench equipment. They take about 20 minutes.
Do them before plugging the board into the heater: if something is wrong, you find out on the bench, where nothing else can be affected.
For what each part does, see the [Detailed walkthrough of circuit operation](circuit-walkthrough.md).

**You need:**

| Item | Used for |
|---|---|
| Adjustable bench supply that reaches **20 V** | power for the fake heater |
| One of: **1.1 kΩ resistor** (1 kΩ + 100 Ω in series), **or** the supply's own current limit, **or** an LM317L + 100 Ω | turns the supply into a fake heater: about 12.5 mA into the board (step 1) |
| **1 kΩ** resistor (¼ W) | adds the heater's extra current when it "sends a 1" |
| A **3.3 V** source for the ESP side | the 3V3 and GND pins of any ESP board on USB (no firmware needed), or 2 × AA cells (3 V) |
| Multimeter, a few jumper wires / clip leads | |

> **Two separate grounds.** The board is isolated, so the heater side and the ESP side each have their own ground.
> - Measure **A+** and anything on the heater side against **B−**.
> - Measure **RX** and **TX** against the **GND pin of J2**.
>
> Measuring across the two sides gives meaningless readings.

---

## Step 0: Checks with the power off

1. **Part orientation:** D1 and D2 bands toward the **K** marks; U1's pin-1 dot top-left and U2's bottom-right (each on its square pad); Q1's flat face matching the silkscreen.
2. **Isolation:** set the meter to continuity/ohms and probe **B−** to **J2 GND**. It must read **open** (no beep, megohms or more). A beep means a solder bridge between the two sides: find it before going on.
3. **No short on the ESP side:** **J2 3V3** to **J2 GND** must not read close to 0 Ω.

---

## Step 1: Build the fake heater (about 12.5 mA into the board)

The real heater pushes a constant ~12.5 mA into the line (it is a *current source*). Any of these imitates it well enough for testing.
All of them connect to the board the same way: **SOURCE → A+** and **COMMON (supply −) → B−**.

**Option A: a resistor (simplest, no special parts).**

```
 Supply + (20 V) ──[ 1 kΩ ]──[ 100 Ω ]──► "SOURCE"  (to the board's A+)
 Supply − ─────────────────────────────► "COMMON"  (to the board's B−)
```

1.1 kΩ from 20 V gives about 12.4 mA at the board's 6.4 V. The current drops a little as the line voltage rises,
so the readings below are slightly lower than with the real heater, but every test still works. Both resistors stay under 0.2 W.

**Option B: the bench supply's current limit (CC mode),** if it has one. Set **20 V** and a current limit of **12.5 mA**, and connect it directly
(no resistor). The supply now behaves exactly like the heater. In step 3 you can then raise the limit to **≈ 24 mA** instead of adding the 1 kΩ.
Its display then shows the line voltage and current directly, and the **CC indicator** should be lit whenever the board is connected.
Connect the board with the **output switched off**, then switch it on: otherwise the supply's output capacitor, already charged to 20 V,
dumps a brief pulse into the board before the limit acts. Low-current limits are often only accurate to ±1 mA, which is fine here.

**Option C: an LM317L as a current source.** 1.25 V across 100 Ω gives 12.5 mA:

```
 Supply + (20 V) ─────────────► LM317L IN
                                LM317L OUT ──[ 100 Ω ]──┬── LM317L ADJ
                                                        └──► "SOURCE"  (to the board's A+)
 Supply − ──────────────────────────────────────────────► "COMMON"  (to the board's B−)
```

LM317L pins differ between makers: check your datasheet. Avoid fixed 3.3 V regulators (AMS1117 and similar) for this:
used as a current source they're inaccurate, and many are only rated to about 15 V input.

**Check before connecting the board:** with the meter on **mA**, connect it straight from SOURCE to COMMON.
That's safe for all three options. Expect **about 18 mA** for option A (the full 20 V across 1.1 kΩ; it drops to ≈ 12.4 mA once the board is connected), and **about 12.5 mA** for B or C.

The supply must reach about **18–20 V**. With less, step 4 can't reach 15 V (the line can't go above the supply), though seeing it rise still proves the switching works.

---

## Step 2: Idle: is the "valve" holding the right voltage?

1. Connect **SOURCE → A+** and **COMMON → B−** (the two J1 pads, or the pigtail's wires).
2. Measure **A+ to B−**.

| Reading | Meaning |
|---|---|
| **6.2–6.8 V** | ✓ correct: the clamp is working like the real remote (6.5 V). Option A typically gives about 6.4 V |
| 7–7.5 V | a bit high: lower **R1** (47 Ω → 39 Ω) |
| 5.5–6 V | a bit low: raise **R1** (47 Ω → 56 Ω) |
| ≈ 15 V | the clamp isn't conducting: check **Q1** orientation and solder, **R3**, and **D1**'s direction |
| close to the full supply voltage | nothing on the board is conducting: check J1's solder joints and **F1** |
| ≈ 0.7–1 V | A+ and B− are swapped (harmless: swap them) or **D1/D2** are reversed |

Leave it connected. Nothing on the board should get warm (the whole board uses about 0.1 W).

---

## Step 3: Receive: does the board notice the heater "sending"?

1. Power the **ESP side**: connect a 3.3 V source to **J2 3V3** and **J2 GND**. Leave **TX** unconnected.
2. Measure **RX to J2 GND**: expect **about 3.3 V** (the H11L1 is off; RX is pulled up by R5).
3. **Simulate the heater sending a '1':** connect the **1 kΩ resistor from Supply + (20 V) to A+**
   (with option B you can instead raise the current limit to ≈ 24 mA).
   This pushes about 11–12 mA of extra current into the board, just like the heater does.

| With the 1 kΩ connected | Expected | If not |
|---|---|---|
| **A+ to B−** | rises to **7.6–8.3 V** (≈ 7.8 V with option A) | |
| **RX to J2 GND** | drops to **below 0.4 V** | stays high: check **U1** orientation, **R4**, and **R2** (76–85 Ω) |

4. **Remove the 1 kΩ.** A+ goes back to about 6.5 V and RX back to about 3.3 V.
   *If RX stays low even without the 1 kΩ, R2 is too large (the H11L1 is switching on at idle).*


---

## Step 4: Transmit: can the board "talk" to the heater?

1. Keep SOURCE/COMMON connected and the ESP side powered. Remove the 1 kΩ from step 3.
2. **Simulate the ESP sending a '1':** connect **J2 TX to J2 3V3** with a jumper wire. R6 on the board limits the LED current.
3. Measure **A+ to B−**: it should jump to **14–15.8 V** (D2, the 15 V zener, now holds the line, as the real remote does). Option A gives the lower end, around 14.5 V.
4. Remove the jumper: A+ falls back to about 6.5 V.

| If A+ stays near 6.5 V with TX high | check **U2** orientation, **R6**, and that the ESP side really has 3.3 V |
|---|---|
| If A+ goes to nearly the full supply voltage instead of ≈ 15 V | **D2** is missing or not soldered |

RX should stay **high** throughout step 4: the board doesn't hear its own transmissions.

---

## Step 5: Fail-safe: a crashed ESP looks like a quiet remote

1. Disconnect the **ESP-side 3.3 V** completely, so J2 is unconnected.
2. A+ to B− should still read **about 6.5 V**. R3 keeps Q1 on using the heater's own power, so with no ESP the heater sees a normal, silent remote.

---

## Step 6 (optional): Reversed wires are harmless

Swap SOURCE and COMMON at the board (SOURCE → B−, COMMON → A+). The meter (A+ to B−) reads about **−0.8 V**, and nothing gets warm.
Swap them back. This is why connecting the pigtail backwards to the heater does no damage.

---

## Reference readings from a working board

My results from my board, measured with a DP100 bench supply in current-limit (CC) mode as the fake heater
(R2 built as 100 Ω ∥ 470 Ω = 83 Ω):

| Step | Condition | Line (A+ to B−) | RX (to J2 GND) |
|---|---|---|---|
| 2 / 3 | idle, 13 mA | ≈ 7.0 V | 3.3 V |
| 3 | heater sends '1', 24 mA | 8.2 V | 0.18 V |
| 4 | TX tied to 3V3 | ≈ 16 V | 3.3 V (no echo) |
| 5 | ESP side unpowered | ≈ 7.0 V | n/a |

An idle reading of 7.0 V rather than 6.5 V is doesn't matter: the heater only distinguishes idle from ≈ 15–16 V,
and the receive threshold depends on R2 only.
---

## Step 7: On the heater

1. Wire J2 to your ESP: **3V3 → 3.3 V, GND → GND, RX → `navien_rx_pin`, TX → `navien_tx_pin`**, and flash the firmware (see the main README).
   RX goes to RX and TX goes to TX, **not crossed** as you would for a serial port: J2's labels name the ESP pin each one connects to.
   Use ordinary GPIOs, not the chip's serial pins (GPIO1/GPIO3 on ESP32 and ESP8266, which carry the boot log).
2. With the heater's **power off**, unplug the remote's cable from **CN12** and plug in the board's pigtail. Power the heater back on.
3. The board starts polling the heater as soon as it boots. In Home Assistant, check that **Navien power** is on; within a few seconds:
   * **Heater link** turns **on**, and **Inlet/Outlet temperature** show sensible values.
   * Open a hot tap: **Hot water demand**, then **Burner**, turn on.
   * Turn **Preheat** on: **Recirculation pump** turns on within a few seconds. Turn it off again.
4. **Anything wrong?** Power the heater off and move the CN12 plug back to the remote's cable. The heater is exactly as it was.

If *Heater link* stays off: first try swapping the pigtail's two wires (harmless; see step 6), then check the *Bad frames* sensor and the ESPHome log.
