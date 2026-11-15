import schemdraw, schemdraw.elements as elm
from schemdraw import flow
import sys
out=sys.argv[1]
schemdraw.config(fontsize=11, unit=2.2, bgcolor="white")
def save(d,n): d.save(f"{out}/{n}.svg"); d.save(f"{out}/{n}.png", dpi=110)

# ---------- sense channel ----------
with schemdraw.Drawing(show=False) as d:
    elm.Dot(open=True).at((0,0)).label("Bus A\n(H-A or R-A)", loc="left")
    elm.Resistor().right(3).label("100 kΩ", loc="top"); p=elm.Dot()
    elm.Resistor().at(p.center).down(2.5).label("10 kΩ", loc="bottom"); elm.Ground()
    elm.Line().at(p.center).right(2); p2=elm.Dot()
    elm.Line().right(1)
    op=elm.Opamp(leads=True).anchor("in2").label("LM339\n(1 of 4)", loc="center", ofst=(-0.4,0))
    elm.Line().at(op.out).right(1.5); o=elm.Dot()
    elm.Line().right(2); elm.Dot(open=True).label("to ESP GPIO\n(see table)", loc="right")
    elm.Resistor().at(o.center).up(2.5).label("10 kΩ", loc="bottom"); elm.Vdd().label("3.3 V")
    elm.Line().at(o.center).down(2.2)
    elm.Resistor().left().tox(p2.center).label("1 MΩ  (hysteresis)", loc="bottom")
    elm.Line().up().toy(p2.center)
    elm.Line().at(op.in1).left(1.5); elm.Dot(open=True).label("Vref_lo or Vref_hi", loc="left")
    save(d,"sense_channel")

# ---------- relay driver ----------
with schemdraw.Drawing(show=False) as d:
    elm.Vdd().at((0,0)).label("5 V")
    t=elm.Dot()
    elm.Inductor2(loops=3).down(3).label("K1 coil (5 V)", loc="bottom", ofst=0.3); bot=elm.Dot()
    elm.Line().at(t.center).right(3)
    elm.Diode().down(3).reverse().label("D7  1N4148\n(flyback, band to +5 V)", loc="bottom", ofst=0.3)
    elm.Line().left().tox(bot.center)
    elm.Line().at(bot.center).down(1)
    q=elm.BjtNpn(circle=True).right().anchor("collector").label("Q2  2N3904", loc="right", ofst=0.3)
    elm.Ground().at(q.emitter)
    elm.Resistor().at(q.base).left(3).label("R8  4.7 kΩ", loc="top")
    elm.Dot(open=True).label("ESP GPIO27\n(RELAY)", loc="left")
    save(d,"relay_driver")

# ---------- overview ----------
with schemdraw.Drawing(show=False) as d:
    d.config(unit=2)
    ha=elm.Dot(open=True).at((0,0)).label("Heater A", loc="left")
    elm.Line().right(2); hs=elm.Dot()
    elm.Line().right(2)
    k1=elm.SwitchSpdt2(action="close").anchor("a").right()
    elm.Label().at((k1.a[0]+0.6, k1.a[1]+1.2)).label("K1 pole 1")
    elm.Line().at(k1.b).right(9); nc=elm.Dot()
    elm.Line().right(3); ra=elm.Dot(open=True).label("Remote A", loc="right")
    elm.Label().at(k1.b).label("NC", loc="top", ofst=(0.4,0.15))
    elm.Line().at(k1.c).right(1.5)
    flow.Box(w=4.2, h=1.4).anchor("W").label("H port\n(fake remote)")
    elm.Label().at(k1.c).label("NO", loc="bottom", ofst=(0.4,-0.15))
    elm.Line().at(nc.center).down(4)
    k2=elm.SwitchSpdt2(action="close").anchor("a").left()
    elm.Label().at((k2.a[0]-0.4, k2.a[1]-1.3)).label("K1 pole 2")
    elm.Line().at(k2.b).left(1); elm.Label().label("NC: not connected", loc="left")
    elm.Line().at(k2.c).left(1.5)
    flow.Box(w=4.2, h=1.4).anchor("E").label("R port\n(fake heater)")
    elm.Line().at(hs.center).down(5.5)
    flow.Box(w=3.2, h=1.2).anchor("N").label("Sense C1, C2")
    elm.Line().at(ra.center).down(5.5)
    flow.Box(w=3.2, h=1.2).anchor("N").label("Sense C3, C4")
    elm.Dot(open=True).at((0,-9)).label("Heater B", loc="left")
    elm.Line().right(18); elm.Dot(open=True).label("Remote B", loc="right")
    elm.Label().at((9,-9)).label("common GND (ESP, comparators, all ports)", loc="top", ofst=0.15)
    save(d,"overview")
print("ok")
