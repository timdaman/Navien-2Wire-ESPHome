import schemdraw, schemdraw.elements as elm
from schemdraw import flow
import sys
out = sys.argv[1]
schemdraw.config(fontsize=11, unit=2.2, bgcolor="white")

def save(d, name):
    d.save(f"{out}/{name}.svg"); d.save(f"{out}/{name}.png", dpi=110)

# ---------------- 1. H port: "fake remote" ----------------
with schemdraw.Drawing(show=False) as d:
    top = elm.Dot().label("H-A\n(K1 pole 1 NO)", loc="top")
    elm.Line().right(2.5)
    n1 = elm.Dot()
    elm.Line().right(3)
    n2 = elm.Dot()
    elm.Line().right(3)
    elm.DiodeTVS().down().label("D3\nSMBJ24A", loc="bottom", ofst=0.2)
    elm.Ground()
    # 15 V zener
    elm.Zener().at(n2.center).down().reverse().label("D2\n1N4744A\n15 V 1 W", loc="bottom", ofst=0.2)
    elm.Ground()
    # clamp branch
    elm.Resistor().at(n1.center).down().label("R1  130 Ω\n(tune 120–150)", loc="bottom", ofst=0.2)
    elm.Zener().down().reverse().label("D1\n1N4732A\n4.7 V 1 W", loc="bottom", ofst=0.2)
    q = elm.BjtNpn(circle=True).anchor("collector").label("Q1\n2N3904", loc="right", ofst=0.1)
    elm.Ground().at(q.emitter)
    elm.Resistor().at(q.base).left().label("R2  1 kΩ", loc="top")
    elm.Dot(open=True).label("GPIO25\n(H_TX)", loc="left")
    elm.Label().at((0,-12.5)).label("GPIO25 HIGH → clamp ON → bus idles ≈ 6.5 V (8 V when heater sends)\n"
                                   "GPIO25 LOW  → clamp OFF → heater current flows into D2 → bus ≈ 15 V = '1' to heater", halign="left")
    save(d, "h_port")

# ---------------- 2. R port: "fake heater" ----------------
with schemdraw.Drawing(show=False) as d:
    vin = elm.Dot().label("+22 V\n(boost OUT+)", loc="left")
    elm.Line().right(1.5)
    sp = elm.Dot()
    # source 1
    elm.Line().right(1)
    u1 = elm.Ic(pins=[elm.IcPin(name="IN", side="left"), elm.IcPin(name="OUT", side="right"),
                      elm.IcPin(name="ADJ", side="bottom")], size=(2.2, 1.6), label="U1\nLM317L").anchor("IN")
    elm.Resistor().at(u1.OUT).right(3).label("R3  100 Ω 1%", loc="top")
    x1 = elm.Dot()
    elm.Line().at(u1.ADJ).down(1)
    elm.Line().right().tox(x1.center)
    elm.Line().up().toy(x1.center)
    elm.Diode().at(x1.center).right().label("D4\n1N4148", loc="top")
    j = elm.Dot()
    elm.Line().right(2)
    ra = elm.Dot().label("R-A\n(K1 pole 2 NO)", loc="right")
    elm.DiodeTVS().at(ra.center).down().label("D6\nSMBJ24A", loc="bottom", ofst=0.2)
    elm.Ground()
    elm.Label().at((x1.center[0]-1.5, x1.center[1]+0.9)).label("12.5 mA always")
    # source 2 with high-side switch
    elm.Line().at(sp.center).down(5.5)
    qp = elm.BjtPnp(circle=True).anchor("emitter").right().label("Q3\n2N3906", loc="top", ofst=0.2)
    # Not pretty to rotate; place PNP with emitter at left
    elm.Line().at(qp.collector).right(0.6)
    u2 = elm.Ic(pins=[elm.IcPin(name="IN", side="left"), elm.IcPin(name="OUT", side="right"),
                      elm.IcPin(name="ADJ", side="bottom")], size=(2.2, 1.6), label="U2\nLM317L").anchor("IN")
    elm.Resistor().at(u2.OUT).right(3).label("R4  110 Ω 1%", loc="top")
    x2 = elm.Dot()
    elm.Line().at(u2.ADJ).down(1)
    elm.Line().right().tox(x2.center)
    elm.Line().up().toy(x2.center)
    elm.Diode().at(x2.center).right().label("D5\n1N4148", loc="top")
    elm.Line().right().tox(j.center)
    elm.Line().up().toy(j.center)
    elm.Label().at((x2.center[0]-1.5, x2.center[1]+0.9)).label("+11.4 mA when R_TX")
    # PNP base drive
    elm.Line().at(qp.base).down(1.5)
    b = elm.Dot()
    elm.Resistor().down().label("R6  10 kΩ", loc="bottom")
    qn = elm.BjtNpn(circle=True).anchor("collector").label("Q4\n2N3904", loc="right")
    elm.Ground().at(qn.emitter)
    elm.Resistor().at(qn.base).left().label("R7  4.7 kΩ", loc="top")
    elm.Dot(open=True).label("GPIO26\n(R_TX)", loc="left")
    elm.Resistor().at(b.center).left(2.5).label("R5  10 kΩ\n(pull-up)", loc="bottom")
    elm.Line().up().toy(qp.emitter)
    elm.Label().at((0,-15)).label("GPIO26 LOW  → Q3 off → only U1 → 12.5 mA → remote clamps ≈ 6.5 V\n"
                                  "GPIO26 HIGH → Q3 on → U1+U2 ≈ 24 mA → remote sees ≈ 8 V = '1' from heater", halign="left")
    save(d, "r_port")

# ---------------- 3. One sense channel ----------------
with schemdraw.Drawing(show=False) as d:
    a = elm.Dot(open=True).label("Bus A\n(H-A or R-A)", loc="left")
    elm.Resistor().right(3).label("R  100 kΩ", loc="top")
    p = elm.Dot()
    elm.Resistor().down().label("10 kΩ", loc="bottom")
    elm.Ground()
    elm.Line().at(p.center).right(1.5)
    op = elm.Opamp(leads=True).anchor("in2").label("LM339\n(1 of 4)", loc="center", ofst=(-0.4,0))
    elm.Line().at(op.out).right(1.5)
    o = elm.Dot()
    elm.Line().right(1.5)
    elm.Dot(open=True).label("GPIO\n(see table)", loc="right")
    elm.Resistor().at(o.center).up().label("10 kΩ", loc="bottom")
    elm.Vdd().label("3.3 V")
    # hysteresis
    elm.Line().at(o.center).down(2.2)
    elm.Resistor().left().tox(p.center).label("1 MΩ  (hysteresis)", loc="bottom")
    elm.Line().up().toy(p.center)
    elm.Line().at(op.in1).left(1)
    elm.Dot(open=True).label("Vref_lo or Vref_hi", loc="left")
    save(d, "sense_channel")

# ---------------- 4. Reference divider ----------------
with schemdraw.Drawing(show=False) as d:
    elm.Vdd().label("5 V")
    elm.Resistor().down().label("1 kΩ", loc="bottom")
    r = elm.Dot().label("2.50 V", loc="left")
    elm.Zener().down().reverse().label("U3  LM4040-2.5\n(cathode up)", loc="bottom", ofst=0.2)
    elm.Ground()
    elm.Line().at(r.center).right(3)
    elm.Resistor().down().label("16 kΩ", loc="bottom")
    hi = elm.Dot().label("Vref_hi = 0.967 V\n(bus 10.6 V)", loc="right")
    elm.Resistor().down().label("3.3 kΩ", loc="bottom")
    lo = elm.Dot().label("Vref_lo = 0.651 V\n(bus 7.2 V)", loc="right")
    elm.Resistor().down().label("6.8 kΩ", loc="bottom")
    elm.Ground()
    save(d, "vref")

# ---------------- 5. Relay driver ----------------
with schemdraw.Drawing(show=False) as d:
    elm.Vdd().label("5 V")
    t = elm.Dot()
    elm.Line().down(0.5)
    c = elm.Inductor2(loops=3).down().label("K1 coil\n(5 V)", loc="bottom")
    bot = elm.Dot()
    elm.Line().at(t.center).right(2.5)
    elm.Diode().down().reverse().toy(bot.center).label("D7\n1N4148\n(flyback)", loc="bottom", ofst=0.2)
    elm.Line().left().tox(bot.center)
    q = elm.BjtNpn(circle=True).at(bot.center).anchor("collector").label("Q2\n2N3904", loc="right")
    elm.Ground().at(q.emitter)
    elm.Resistor().at(q.base).left().label("R8  4.7 kΩ", loc="top")
    elm.Dot(open=True).label("GPIO27\n(RELAY)", loc="left")
    save(d, "relay_driver")

# ---------------- 6. Overview ----------------
with schemdraw.Drawing(show=False) as d:
    d.config(unit=2)
    ha = elm.Dot(open=True).label("Heater A", loc="left")
    elm.Line().right(2)
    hs = elm.Dot()
    elm.Line().right(2)
    k1 = elm.SwitchSpdt2(action="close").anchor("a").right().label("K1 pole 1", loc="top", ofst=0.6)
    # k1: a = COM, b = one throw, c = other throw
    elm.Line().at(k1.b).right(1.5)
    elm.Line().right(5)
    nc = elm.Dot()
    elm.Line().right(5)
    ra = elm.Dot(open=True).label("Remote A", loc="right")
    elm.Label().at(k1.b).label("NC", loc="top", ofst=(0.3,0.1))
    elm.Line().at(k1.c).right(1.5)
    flow.Box(w=4, h=1.4).anchor("W").label("H port\n(fake remote)")
    elm.Label().at(k1.c).label("NO", loc="bottom", ofst=(0.3,-0.1))
    # pole 2 from Remote A side
    elm.Line().at(nc.center).down(3)
    k2 = elm.SwitchSpdt2().anchor("a").left().label("K1 pole 2", loc="bottom", ofst=0.6)
    elm.Line().at(k2.b).left(0.8)
    elm.Label().label("NC: n/c", loc="left")
    elm.Line().at(k2.c).left(1.5)
    flow.Box(w=4, h=1.4).anchor("E").label("R port\n(fake heater)")
    # sense taps
    elm.Line().at(hs.center).down(6.5)
    flow.Box(w=3.6, h=1.4).anchor("N").label("Sense C1, C2")
    elm.Line().at(ra.center).down(6.5)
    flow.Box(w=3.6, h=1.4).anchor("N").label("Sense C3, C4")
    elm.Label().at((0,-11)).label("Heater B ━━━━━━━━━━━━━━━━━━━━ GND (common) ━━━━━━━━━━━━━━━━━━━━ Remote B", halign="left")
    elm.Label().at((0,-12.3)).label("K1 de-energized (shown) = BYPASS: Heater A → NC → Remote A, exactly like today.\n"
                                   "K1 energized = PROXY: Heater A → H port,  Remote A → R port.", halign="left")
    save(d, "overview")
print("ok")
