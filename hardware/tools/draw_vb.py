import schemdraw, schemdraw.elements as elm
import sys
out=sys.argv[1]
schemdraw.config(fontsize=11, unit=2.2, bgcolor="white")
def save(d,n): d.save(f"{out}/{n}.svg"); d.save(f"{out}/{n}.png", dpi=110)

def opto_box(d, at, name, pins_left, pins_right, w=2.6, h=2.4):
    p=[elm.IcPin(name=n, side="left") for n in pins_left]+[elm.IcPin(name=n, side="right") for n in pins_right]
    u=elm.Ic(pins=p, size=(w,h), pinspacing=1.2).at(at).anchor(pins_left[0].replace("+","p").replace("-","m") if False else pins_left[0])
    d.add(u); d.add(elm.Label().at((u.center[0], u.center[1]+h/2+0.4)).label(name))
    return u

with schemdraw.Drawing(show=False) as d:
    # bus side (left) ---------------------------------------------------
    elm.Dot(open=True).at((-2,0)).label("J1-1  A (+)", loc="left")
    elm.Resistor().right(4).label("F1  PTC 50 mA", loc="top"); a=elm.Dot()
    elm.Line().right(3); s=elm.Dot()
    elm.Line().right(2.5); t=elm.Dot()
    elm.DiodeTVS().at(t.center).down(2.2).label("D3  SMBJ24A", loc="bottom", ofst=0.2); elm.Ground()
    elm.Zener().at(s.center).down(2.2).reverse().label("D2  1N4744A\n15 V 1 W", loc="bottom", ofst=0.2); elm.Ground()
    # clamp chain under A
    elm.Zener().at(a.center).down().reverse().label("D1  1N4732A\n4.7 V 1 W", loc="bottom", ofst=0.2)
    elm.Resistor().down().label("R1  47 Ω", loc="bottom", ofst=0.2); top=elm.Dot()
    elm.Resistor().down().label("R2  82 Ω 1%\n(sense)", loc="bottom", ofst=0.2); bot=elm.Dot()
    q1=elm.BjtNpn(circle=True).right().anchor("collector").label("Q1  2N3904", loc="right", ofst=0.3)
    elm.Ground().at(q1.emitter)
    # base bias from the bus via R3, pulled down by the PC817 transistor
    elm.Line().at(a.center).left(3); b0=elm.Dot()
    elm.Resistor().down().toy(q1.base).label("R3  10 kΩ", loc="top", ofst=0.2); bb=elm.Dot()
    elm.Line().right().tox(q1.base)
    elm.Line().at(bb.center).down(1.5); pc=elm.Dot().label("PC817 pin 4 (C)", loc="left")
    elm.Ground().at((bb.center[0]+1.5, pc.center[1]-1.6)).label("PC817 pin 3 (E) → bus GND", loc="right")
    # H11L1 LED across the sense resistor
    elm.Line().at(top.center).right(3)
    elm.Resistor().right(2.5).label("R4  330 Ω", loc="top"); elm.Dot(open=True).label("H11L1 pin 1 (A)", loc="right")
    elm.Line().at(bot.center).right(5.5); elm.Dot(open=True).label("H11L1 pin 2 (K)", loc="right")
    elm.Dot(open=True).at((-2,-14)).label("J1-2  B (−)", loc="left")
    elm.Line().right(2.5); elm.Ground().label("bus GND (isolated)", loc="right")
    save(d,"vb_bus")

with schemdraw.Drawing(show=False) as d:
    # ESP side -----------------------------------------------------------
    elm.Vdd().at((0,0)).label("ESP 3.3 V"); v=elm.Dot()
    elm.Line().right(4); v2=elm.Dot()
    elm.Resistor().at(v.center).down().label("R5  4.7 kΩ", loc="bottom", ofst=0.2); o=elm.Dot()
    elm.Line().left(2); elm.Dot(open=True).label("H11L1 pin 4 (OUT)", loc="left")
    elm.Line().at(o.center).right(2); elm.Dot(open=True).label("ESP RX pin", loc="right")
    elm.Line().at(v2.center).right(3); elm.Dot(open=True).label("H11L1 pin 6 (VCC)", loc="right")
    elm.Capacitor().at(v2.center).down().label("C1  100 nF", loc="bottom", ofst=0.2); elm.Ground().label("ESP GND  +  H11L1 pin 5", loc="right")
    elm.Dot(open=True).at((0,-6)).label("ESP TX pin", loc="left")
    elm.Resistor().right(3).label("R6  220 Ω", loc="top"); elm.Dot(open=True).label("PC817 pin 1 (A)", loc="right")
    elm.Dot(open=True).at((5.2,-7.6)).label("PC817 pin 2 (K)", loc="right")
    elm.Line().at((5.2,-7.6)).left(1.5); elm.Ground().label("ESP GND", loc="left")
    save(d,"vb_esp")
print("ok")
