import schemdraw, schemdraw.elements as elm
from schemdraw import flow
import sys
out=sys.argv[1]
schemdraw.config(fontsize=11, unit=2.2, bgcolor="white")
def save(d,n): d.save(f"{out}/{n}.svg"); d.save(f"{out}/{n}.png", dpi=110)

with schemdraw.Drawing(show=False) as d:
    elm.Dot(open=True).at((-2,0)).label("J1-1  A (+)", loc="left")
    elm.Resistor().right(5).label("F1  PTC 50 mA", loc="top"); a=elm.Dot()
    elm.Line().right(6); s=elm.Dot()
    elm.Line().right(3); elm.Dot(open=True).label("to sense C1 / C2", loc="right")
    elm.DiodeTVS().at(s.center).down(2.2).label("D3  SMBJ24A", loc="bottom", ofst=0.2); elm.Ground()
    elm.Switch().at(a.center).down(2.2).label("JP1  (remove = listen-only)", loc="bottom", ofst=0.2); n=elm.Dot()
    # 15 V zener to the right
    elm.Line().at(n.center).right(3); elm.Zener().down().reverse().label("D2  1N4744A\n15 V 1 W", loc="bottom", ofst=0.2); elm.Ground()
    # clamp
    elm.Resistor().at(n.center).down().label("R1  130 Ω", loc="bottom", ofst=0.2)
    elm.Zener().down().reverse().label("D1  1N4732A\n4.7 V 1 W", loc="bottom", ofst=0.2)
    q1=elm.BjtNpn(circle=True).right().anchor("collector").label("Q1  2N3904", loc="right", ofst=0.3)
    elm.Ground().at(q1.emitter)
    # base bias from the bus: clamp ON by default
    elm.Line().at(n.center).left(3); r=elm.Dot()
    elm.Resistor().at(r.center).down().toy(q1.base).label("R2  4.7 kΩ", loc="top", ofst=0.2); bb=elm.Dot()
    elm.Line().right().tox(q1.base)
    elm.Line().at(bb.center).down(1.2)
    q2=elm.BjtNpn(circle=True).right().anchor("collector").label("Q2  2N3904", loc="right", ofst=0.3)
    elm.Ground().at(q2.emitter)
    elm.Resistor().at(q2.base).left(3).label("R3  1 kΩ", loc="top"); g=elm.Dot()
    elm.Line().left(1.5); elm.Dot(open=True).label("ESP TX pin", loc="left")
    elm.Resistor().at(g.center).down(2).label("R4  100 kΩ", loc="bottom", ofst=0.2); elm.Ground()
    elm.Dot(open=True).at((-2,-13)).label("J1-2  B (−)", loc="left")
    elm.Line().right(2.5); elm.Ground().label("GND", loc="right")
    save(d,"bus_if")

with schemdraw.Drawing(show=False) as d:
    for y,name,extra in ((0,"Original Navien remote\n(stock, untouched)",False),(-3.5,"ESPHome board\n(ESP32 / ESP8266 / RP2040)",True)):
        flow.Box(w=4.2, h=1.6).at((0,y)).anchor("W").label("Navien heater\ncontrol board")
        flow.Box(w=2.0, h=1.2).at((4.2,y)).anchor("W").label("CN12\nJST VH")
        elm.Line().at((6.2,y)).right(4).label("2-wire cable, VHR-2N plug", loc="top")
        flow.Box(w=4.8, h=1.6).at((10.2,y)).anchor("W").label(name)
        if extra:
            elm.Line().at((15,y)).right(1.5).label("5 V", loc="top")
            flow.Box(w=2.6, h=1.2).at((16.5,y)).anchor("W").label("USB supply")
    elm.Label().at((-0.2,1.5)).label("Stock / fallback:", halign="left")
    elm.Label().at((-0.2,-2.0)).label("With Home Assistant (move the plug on CN12):", halign="left")
    save(d,"overview_v2")
print("ok")
