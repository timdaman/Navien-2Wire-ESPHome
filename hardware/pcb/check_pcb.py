"""Independent checks of navien-bus-if.kicad_pcb (run with KiCad's Python, like make_pcb.py).

1. Every net connects exactly the pins of the interface board's wiring list (hardware/README.md),
   written here in pin-function terms (zener K/A, transistor E/B/C) so that a footprint
   pin-order mistake is caught too.
2. KiCad's connectivity engine reports no unrouted connections.
3. Distance between heater-side and ESP-side copper (isolation).
"""
import os
import sys

import pcbnew

BOARD = os.path.join(os.path.dirname(os.path.abspath(__file__)), "navien-bus-if.kicad_pcb")

EXPECT = {
    "BUS_A_IN": {"J1.1", "F1.1"},
    "BUS_A": {"F1.2", "D1.K", "D2.K", "D3.1", "R3.1"},
    "CLAMP": {"D1.A", "R1.1"},
    "SENSE_TOP": {"R1.2", "R2.1", "R4.1"},
    "LED_A": {"R4.2", "U1.1"},
    "SENSE_BOT": {"R2.2", "Q1.C", "U1.2"},
    "Q1_BASE": {"R3.2", "Q1.B", "U2.4"},
    "BUS_GND": {"J1.2", "Q1.E", "D2.A", "D3.2", "U2.3"},
    "+3V3": {"J2.1", "U1.6", "R5.1", "C1.1"},
    "RX": {"J2.2", "U1.4", "R5.2"},
    "TX": {"J2.3", "R6.2"},
    "TX_LED": {"R6.1", "U2.1"},
    "GND": {"J2.4", "U1.5", "U2.2", "C1.2"},
}
# KiCad DO-41 pad 1 = cathode; 2N3904 in TO-92 = E, B, C
ALIAS = {("D1", "1"): "D1.K", ("D1", "2"): "D1.A", ("D2", "1"): "D2.K", ("D2", "2"): "D2.A",
         ("Q1", "1"): "Q1.E", ("Q1", "2"): "Q1.B", ("Q1", "3"): "Q1.C"}
BUS_NETS = {"BUS_A_IN", "BUS_A", "CLAMP", "SENSE_TOP", "LED_A", "SENSE_BOT", "Q1_BASE", "BUS_GND"}


def main():
    b = pcbnew.LoadBoard(BOARD)
    ok = True

    got = {}
    for fp in b.GetFootprints():
        for p in fp.Pads():
            if p.GetNetname():
                key = ALIAS.get((fp.GetReference(), p.GetNumber()), f"{fp.GetReference()}.{p.GetNumber()}")
                got.setdefault(p.GetNetname(), set()).add(key)
    for net, pins in EXPECT.items():
        if got.get(net) != pins:
            ok = False
            print(f"MISMATCH {net}: board {sorted(got.get(net, []))} expected {sorted(pins)}")
    for net in set(got) - set(EXPECT):
        ok = False
        print(f"EXTRA NET {net}: {sorted(got[net])}")
    print("netlist matches circuit:", ok)

    conn = b.GetConnectivity()
    conn.RecalculateRatsnest()
    unrouted = conn.GetUnconnectedCount(True)
    print("unrouted connections:", unrouted)
    ok &= unrouted == 0

    def shapes(bus_side):
        out = []
        for t in b.GetTracks():
            if (t.GetNetname() in BUS_NETS) == bus_side:
                out.append(t.GetEffectiveShape(pcbnew.F_Cu if t.Type() == pcbnew.PCB_VIA_T else t.GetLayer()))
        for fp in b.GetFootprints():
            for p in fp.Pads():
                if p.GetNetname() and (p.GetNetname() in BUS_NETS) == bus_side:
                    out.append(p.GetEffectiveShape(pcbnew.F_Cu))
        return out
    gap = min(a.GetClearance(c) for a in shapes(True) for c in shapes(False))
    zb = [z for z in b.Zones() if z.GetNetname() == "BUS_GND"][0].GetBoundingBox()
    ze = [z for z in b.Zones() if z.GetNetname() == "GND"][0].GetBoundingBox()
    print("isolation: pads/tracks %.2f mm, ground pours %.2f mm" % (pcbnew.ToMM(gap), pcbnew.ToMM(ze.GetX() - zb.GetRight())))
    ok &= pcbnew.ToMM(gap) >= 4.0

    print("ALL CHECKS PASSED" if ok else "CHECKS FAILED")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
