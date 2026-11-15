"""Generate the isolated interface PCB for the Navien NR remote bus.

Run with KiCad's bundled Python (it provides the pcbnew module), e.g. on macOS:
  /Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3 make_pcb.py

Places the parts, routes every net with a small two-layer grid router (A*,
with vias), adds ground pours and silkscreen, and writes navien-bus-if.kicad_pcb.
The bus side (left) and the ESP side (right) are routed in separate regions,
so only the two optocouplers cross the isolation gap.
"""
import heapq
import math
import os
import sys

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "navien-bus-if.kicad_pcb")
FPLIB = os.environ.get(
    "KICAD_FP_DIR", "/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints"
)

# ---------------------------------------------------------------- board rules
W, H = 67.0, 46.0          # board size, mm
OX, OY = 100.0, 80.0       # board origin on the KiCad page
TRACK = 0.40               # track width
CLEAR = 0.30               # copper clearance
VIA_D, VIA_DRILL = 0.80, 0.40
EDGE = 0.60                # copper to board edge
GRID = 0.25                # router grid
BUS_MAX_X = 39.2           # bus-side nets stay left of this
ESP_MIN_X = 42.4           # ESP-side nets stay right of this
ZONE_BUS_X1 = 38.6         # bus-side pour ends here
ZONE_ESP_X0 = 43.3         # ESP-side pour starts here (gap ~4.7 mm)
VERSION = "v1.1"

# reference text placement: ref -> (dx, dy) from pad 1 in board coordinates, or None to hide
REF_POS = {
    "D1": (5.08, 0), "D2": (5.08, 0), "D3": (5.08, 0), "R1": (5.08, 0), "R2": (5.08, 0),
    "R3": (5.08, 0), "R4": (5.08, 0), "R6": (5.08, 0), "R5": (0, 5.08), "F1": (2.6, 0.8),
    "C1": (0, 4.4), "J1": (-6.3, -2.2), "H1": None, "H2": None,
}

# -------------------------------------------------------------------- parts
# ref: (library, footprint, value, x, y, rotation_deg)   x, y = pad 1, mm
PARTS = {
    "J1": ("Connector_Wire", "SolderWire-0.5sqmm_1x02_P4.6mm_D0.9mm_OD2.1mm_Relief", "VH pigtail to CN12", 15.0, 19.0, 270),
    "F1": ("Fuse", "Fuse_BelFuse_0ZRE0005FF_L8.3mm_W3.8mm", "0ZRE0005FF 50mA PTC", 22, 19.5, 0),
    "D2": ("Diode_THT", "D_DO-41_SOD81_P10.16mm_Horizontal", "1N4744A 15V", 22, 4.0, 0),
    "D3": ("Diode_THT", "D_DO-15_P10.16mm_Horizontal", "P6KE24CA", 22, 9.0, 0),
    "R3": ("Resistor_THT", "R_Axial_DIN0207_L6.3mm_D2.5mm_P10.16mm_Horizontal", "10k", 22, 14.0, 0),
    "D1": ("Diode_THT", "D_DO-41_SOD81_P10.16mm_Horizontal", "1N4732A 4.7V", 22, 25.5, 0),
    "R1": ("Resistor_THT", "R_Axial_DIN0207_L6.3mm_D2.5mm_P10.16mm_Horizontal", "47", 22, 30.0, 0),
    "R2": ("Resistor_THT", "R_Axial_DIN0207_L6.3mm_D2.5mm_P10.16mm_Horizontal", "82 1%", 22, 34.5, 0),
    "R4": ("Resistor_THT", "R_Axial_DIN0207_L6.3mm_D2.5mm_P10.16mm_Horizontal", "330", 22, 39.0, 0),
    "Q1": ("Package_TO_SOT_THT", "TO-92_Inline_Wide", "2N3904", 36, 34.5, 270),
    "U1": ("Package_DIP", "DIP-6_W7.62mm", "H11L1", 37, 8.0, 0),
    "U2": ("Package_DIP", "DIP-4_W7.62mm", "PC817", 44.62, 30.0, 180),
    "C1": ("Capacitor_THT", "C_Disc_D3.0mm_W1.6mm_P2.50mm", "100n", 48, 8.0, 270),
    "R5": ("Resistor_THT", "R_Axial_DIN0207_L6.3mm_D2.5mm_P10.16mm_Horizontal", "4.7k", 52, 5.0, 270),
    "R6": ("Resistor_THT", "R_Axial_DIN0207_L6.3mm_D2.5mm_P10.16mm_Horizontal", "220", 49, 36.0, 0),
    "J2": ("Connector_PinHeader_2.54mm", "PinHeader_1x04_P2.54mm_Vertical", "to ESP board", 62, 14.0, 0),
    "H1": ("MountingHole", "MountingHole_3.2mm_M3", "M3", 4.5, 41.5, 0),
    "H2": ("MountingHole", "MountingHole_3.2mm_M3", "M3", 62.5, 4.5, 0),
}

# net: (side, [(ref, pad), ...])
NETS = {
    "BUS_A_IN": ("bus", [("J1", "1"), ("F1", "1")]),
    "BUS_A": ("bus", [("F1", "2"), ("D2", "1"), ("D3", "1"), ("D1", "1"), ("R3", "1")]),
    "CLAMP": ("bus", [("D1", "2"), ("R1", "1")]),
    "SENSE_TOP": ("bus", [("R1", "2"), ("R2", "1"), ("R4", "1")]),
    "LED_A": ("bus", [("R4", "2"), ("U1", "1")]),
    "SENSE_BOT": ("bus", [("R2", "2"), ("Q1", "3"), ("U1", "2")]),
    "Q1_BASE": ("bus", [("R3", "2"), ("Q1", "2"), ("U2", "4")]),
    "BUS_GND": ("bus", [("J1", "2"), ("Q1", "1"), ("D2", "2"), ("D3", "2"), ("U2", "3")]),
    "+3V3": ("esp", [("J2", "1"), ("U1", "6"), ("R5", "1"), ("C1", "1")]),
    "RX": ("esp", [("J2", "2"), ("U1", "4"), ("R5", "2")]),
    "TX": ("esp", [("J2", "3"), ("R6", "2")]),
    "TX_LED": ("esp", [("R6", "1"), ("U2", "1")]),
    "GND": ("esp", [("J2", "4"), ("U1", "5"), ("U2", "2"), ("C1", "2")]),
}
ROUTE_ORDER = ["BUS_A", "SENSE_BOT", "Q1_BASE", "SENSE_TOP", "BUS_A_IN", "CLAMP", "LED_A",
               "+3V3", "RX", "TX", "TX_LED", "BUS_GND", "GND"]

SILK = [  # text, x, y, size_mm, rotation
    ("A+", 18.2, 19.0, 1.0, 0), ("B-", 18.2, 23.6, 1.0, 0),
    ("3V3", 65.2, 14.0, 0.9, 0), ("RX", 65.2, 16.54, 0.9, 0),
    ("TX", 65.2, 19.08, 0.9, 0), ("GND", 65.2, 21.62, 0.9, 0),
    ("HEATER BUS", 24, 44.3, 1.0, 0), ("ESP SIDE (isolated)", 54, 44.3, 1.0, 0),
    ("Navien NR bus IF " + VERSION, 56.0, 26.0, 1.0, 0),
]


def mm(v):
    return pcbnew.FromMM(v)


def pt(x, y):
    return pcbnew.VECTOR2I(mm(OX + x), mm(OY + y))


def build():
    board = pcbnew.BOARD()
    ds = board.GetDesignSettings()
    ds.SetCopperLayerCount(2)
    ds.m_TrackMinWidth = mm(0.2)
    ds.m_MinClearance = mm(0.2)

    nets = {}
    for name in NETS:
        n = pcbnew.NETINFO_ITEM(board, name)
        board.Add(n)
        nets[name] = n

    fps = {}
    for ref, (lib, name, value, x, y, rot) in PARTS.items():
        fp = pcbnew.FootprintLoad(os.path.join(FPLIB, lib + ".pretty"), name)
        fp.SetReference(ref)
        fp.SetValue(value)
        fp.SetOrientationDegrees(rot)
        fp.SetPosition(pt(x, y))  # footprint anchor = pad 1 for all of these
        board.Add(fp)
        fps[ref] = fp
        if ref in REF_POS:
            field = fp.Reference()
            if REF_POS[ref] is None:
                field.SetVisible(False)
            else:
                dx, dy = REF_POS[ref]
                field.SetPosition(pt(x + dx, y + dy))
                field.SetTextAngleDegrees(0)
                field.SetTextSize(pcbnew.VECTOR2I(mm(0.8), mm(0.8)))
                field.SetTextThickness(mm(0.12))

    for name, (_, members) in NETS.items():
        for ref, pad in members:
            p = fps[ref].FindPadByNumber(pad)
            if p is None:
                sys.exit(f"no pad {ref}.{pad}")
            p.SetNet(nets[name])

    # outline with rounded corners
    r = 2.0
    def seg(a, b):
        s = pcbnew.PCB_SHAPE(board)
        s.SetShape(pcbnew.SHAPE_T_SEGMENT)
        s.SetStart(pt(*a)); s.SetEnd(pt(*b))
        s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(mm(0.1)); board.Add(s)
    def arc(c, start, angle):
        s = pcbnew.PCB_SHAPE(board)
        s.SetShape(pcbnew.SHAPE_T_ARC)
        s.SetCenter(pt(*c)); s.SetStart(pt(*start)); s.SetArcAngleAndEnd(pcbnew.EDA_ANGLE(angle, pcbnew.DEGREES_T))
        s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(mm(0.1)); board.Add(s)
    seg((r, 0), (W - r, 0)); seg((W, r), (W, H - r)); seg((W - r, H), (r, H)); seg((0, H - r), (0, r))
    arc((W - r, r), (W - r, 0), 90); arc((W - r, H - r), (W, H - r), 90)
    arc((r, H - r), (r, H), 90); arc((r, r), (0, r), 90)

    return board, fps, nets


# ------------------------------------------------------------------ router
class Router:
    def __init__(self, board, fps):
        self.nx = int(W / GRID) + 1
        self.ny = int(H / GRID) + 1
        self.pads = []  # (net, layerset, x0, y0, x1, y1, cx, cy)
        for fp in fps.values():
            for p in fp.Pads():
                bb = p.GetBoundingBox()
                x0 = pcbnew.ToMM(bb.GetX()) - OX; y0 = pcbnew.ToMM(bb.GetY()) - OY
                x1 = pcbnew.ToMM(bb.GetRight()) - OX; y1 = pcbnew.ToMM(bb.GetBottom()) - OY
                c = p.GetPosition()
                self.pads.append((p.GetNetname(), (0, 1), x0, y0, x1, y1,
                                  pcbnew.ToMM(c.x) - OX, pcbnew.ToMM(c.y) - OY))
        self.segs = []   # (net, layer, x0, y0, x1, y1)
        self.vias = []   # (net, x, y)

    def cell_xy(self, i, j):
        return i * GRID, j * GRID

    def blocked_map(self, net, side):
        """Per-layer sets of cells a track (or via) of `net` may not occupy."""
        tr = TRACK / 2
        blocked = [set(), set()]
        via_block = set()
        lo = 0.0 if side == "esp" else 0.0
        for i in range(self.nx):
            x = i * GRID
            if (side == "bus" and x > BUS_MAX_X) or (side == "esp" and x < ESP_MIN_X):
                for j in range(self.ny):
                    blocked[0].add((i, j)); blocked[1].add((i, j))
        m = EDGE + tr
        for i in range(self.nx):
            for j in range(self.ny):
                x, y = i * GRID, j * GRID
                if x < m or y < m or x > W - m or y > H - m:
                    blocked[0].add((i, j)); blocked[1].add((i, j))

        def block_rect(x0, y0, x1, y1, infl, layers, also_via):
            vi = infl + (VIA_D / 2 - tr)
            ii0 = max(0, int((x0 - vi) / GRID)); ii1 = min(self.nx - 1, int((x1 + vi) / GRID) + 1)
            jj0 = max(0, int((y0 - vi) / GRID)); jj1 = min(self.ny - 1, int((y1 + vi) / GRID) + 1)
            for i in range(ii0, ii1 + 1):
                for j in range(jj0, jj1 + 1):
                    x, y = i * GRID, j * GRID
                    dx = max(x0 - x, 0, x - x1); dy = max(y0 - y, 0, y - y1)
                    d = math.hypot(dx, dy)
                    if d < infl:
                        for L in layers:
                            blocked[L].add((i, j))
                    if also_via and d < vi:
                        via_block.add((i, j))

        for (pn, layers, x0, y0, x1, y1, cx, cy) in self.pads:
            if pn != net:
                block_rect(x0, y0, x1, y1, CLEAR + tr, layers, True)
            else:
                # vias never inside our own pads (avoid via-in-pad)
                block_rect(x0, y0, x1, y1, 0.0, (), True)
        for (sn, L, x0, y0, x1, y1) in self.segs:
            if sn == net:
                continue
            self._block_seg(blocked[L], via_block, x0, y0, x1, y1, TRACK / 2 + CLEAR + tr, TRACK / 2 + CLEAR + VIA_D / 2)
        for (vn, x, y) in self.vias:
            if vn == net:
                continue
            for L in (0, 1):
                self._block_seg(blocked[L], via_block, x, y, x, y, VIA_D / 2 + CLEAR + tr, VIA_D + CLEAR)
        return blocked, via_block

    def _block_seg(self, cells, via_cells, x0, y0, x1, y1, infl, vinfl):
        r = max(infl, vinfl)
        ii0 = max(0, int((min(x0, x1) - r) / GRID)); ii1 = min(self.nx - 1, int((max(x0, x1) + r) / GRID) + 1)
        jj0 = max(0, int((min(y0, y1) - r) / GRID)); jj1 = min(self.ny - 1, int((max(y0, y1) + r) / GRID) + 1)
        dx, dy = x1 - x0, y1 - y0
        ll = dx * dx + dy * dy
        for i in range(ii0, ii1 + 1):
            for j in range(jj0, jj1 + 1):
                x, y = i * GRID, j * GRID
                t = 0 if ll == 0 else max(0, min(1, ((x - x0) * dx + (y - y0) * dy) / ll))
                d = math.hypot(x - (x0 + t * dx), y - (y0 + t * dy))
                if d < infl:
                    cells.add((i, j))
                if d < vinfl:
                    via_cells.add((i, j))

    def pad_cells(self, net, ref_pad_xy):
        x, y = ref_pad_xy
        return {(int(round(x / GRID)), int(round(y / GRID)))}

    def route_net(self, net, side, pad_pts):
        blocked, via_block = self.blocked_map(net, side)
        tree = set()
        first = pad_pts[0]
        c = (int(round(first[0] / GRID)), int(round(first[1] / GRID)))
        tree.add((c[0], c[1], 0)); tree.add((c[0], c[1], 1))
        remaining = list(pad_pts[1:])
        paths = []
        while remaining:
            # route to the remaining pad closest to the tree
            best = None
            for k, (x, y) in enumerate(remaining):
                tc = (int(round(x / GRID)), int(round(y / GRID)))
                dmin = min(abs(tc[0] - a) + abs(tc[1] - b) for (a, b, _) in tree)
                if best is None or dmin < best[0]:
                    best = (dmin, k, tc)
            _, k, target = best
            remaining.pop(k)
            path = self.astar(tree, target, blocked, via_block)
            if path is None:
                return None
            paths.append(path)
            for s in path:
                tree.add(s)
        return paths

    def astar(self, sources, target, blocked, via_block):
        tx, ty = target
        def h(i, j):
            dx, dy = abs(i - tx), abs(j - ty)
            return (dx + dy) + (math.sqrt(2) - 2) * min(dx, dy)
        openh = []
        g = {}
        parent = {}
        for s in sources:
            g[s] = 0.0
            heapq.heappush(openh, (h(s[0], s[1]), 0.0, s, None))
        dirs = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)]
        target_states = {(tx, ty, 0), (tx, ty, 1)}
        while openh:
            f, gc, s, d = heapq.heappop(openh)
            if gc > g.get(s, 1e18):
                continue
            if s in target_states:
                path = [s]
                while s in parent:
                    s = parent[s]
                    path.append(s)
                return path[::-1]
            i, j, L = s
            for (di, dj) in dirs:
                ni, nj = i + di, j + dj
                if not (0 <= ni < self.nx and 0 <= nj < self.ny):
                    continue
                if (ni, nj) in blocked[L] and (ni, nj, L) not in target_states:
                    continue
                if di and dj and ((i + di, j) in blocked[L] or (i, j + dj) in blocked[L]):
                    continue
                step = math.sqrt(2) if di and dj else 1.0
                if d is not None and d != (di, dj):
                    step += 0.6       # discourage zig-zags
                if L == 0:
                    step *= 1.0
                else:
                    step *= 1.15      # mild preference for the top layer
                ns = (ni, nj, L)
                ng = gc + step
                if ng < g.get(ns, 1e18):
                    g[ns] = ng; parent[ns] = s
                    heapq.heappush(openh, (ng + h(ni, nj), ng, ns, (di, dj)))
            if (i, j) not in via_block:
                ns = (i, j, 1 - L)
                ng = gc + 12.0
                if ng < g.get(ns, 1e18):
                    g[ns] = ng; parent[ns] = s
                    heapq.heappush(openh, (ng + h(i, j), ng, ns, d))
        return None

    def commit(self, net, paths):
        for path in paths:
            # split into straight runs per layer, add vias at layer changes
            run = [path[0]]
            def flush(run):
                pts = [(a * GRID, b * GRID) for (a, b, _) in run]
                L = run[0][2]
                # merge collinear points
                simp = [pts[0]]
                for k in range(1, len(pts) - 1):
                    ax, ay = simp[-1]; bx, by = pts[k]; cx, cy = pts[k + 1]
                    if abs((bx - ax) * (cy - by) - (by - ay) * (cx - bx)) > 1e-9:
                        simp.append(pts[k])
                if len(pts) > 1:
                    simp.append(pts[-1])
                for a, b in zip(simp, simp[1:]):
                    self.segs.append((net, L, a[0], a[1], b[0], b[1]))
            for s in path[1:]:
                if s[2] != run[-1][2]:
                    flush(run)
                    self.vias.append((net, s[0] * GRID, s[1] * GRID))
                    run = [s]
                else:
                    run.append(s)
            flush(run)


def main():
    board, fps, nets = build()
    router = Router(board, fps)
    order = list(ROUTE_ORDER)
    for name in order:
        side, members = NETS[name]
        pts = []
        for ref, pad in members:
            p = fps[ref].FindPadByNumber(pad).GetPosition()
            pts.append((pcbnew.ToMM(p.x) - OX, pcbnew.ToMM(p.y) - OY))
        paths = router.route_net(name, side, pts)
        if paths is None:
            sys.exit(f"routing failed: {name}")
        router.commit(name, paths)
        print(f"routed {name}: {sum(len(p) for p in paths)} cells")

    for (net, L, x0, y0, x1, y1) in router.segs:
        if (x0, y0) == (x1, y1):
            continue
        t = pcbnew.PCB_TRACK(board)
        t.SetStart(pt(x0, y0)); t.SetEnd(pt(x1, y1))
        t.SetWidth(mm(TRACK)); t.SetLayer(pcbnew.F_Cu if L == 0 else pcbnew.B_Cu)
        t.SetNet(nets[net]); board.Add(t)
    for (net, x, y) in router.vias:
        v = pcbnew.PCB_VIA(board)
        v.SetPosition(pt(x, y)); v.SetWidth(mm(VIA_D)); v.SetDrill(mm(VIA_DRILL))
        v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu); v.SetNet(nets[net]); board.Add(v)

    # ground pours on the bottom layer, one per side, with a gap between them
    def zone(net, x0, x1):
        z = pcbnew.ZONE(board)
        z.SetLayer(pcbnew.B_Cu)
        z.SetNet(nets[net])
        ol = z.Outline(); ol.NewOutline()
        for (x, y) in [(x0, 0.3), (x1, 0.3), (x1, H - 0.3), (x0, H - 0.3)]:
            ol.Append(mm(OX + x), mm(OY + y))
        z.SetLocalClearance(mm(CLEAR))
        z.SetMinThickness(mm(0.25))
        z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
        board.Add(z)
    zone("BUS_GND", 0.3, ZONE_BUS_X1)
    zone("GND", ZONE_ESP_X0, W - 0.3)

    for text, x, y, size, rot in SILK:
        t = pcbnew.PCB_TEXT(board)
        t.SetText(text); t.SetPosition(pt(x, y)); t.SetLayer(pcbnew.F_SilkS)
        t.SetTextSize(pcbnew.VECTOR2I(mm(size), mm(size))); t.SetTextThickness(mm(size * 0.15))
        t.SetTextAngleDegrees(rot); board.Add(t)
    # isolation marker
    for y in range(1, int(H) - 1, 3):
        if 3 <= y <= 16 or 23 <= y <= 33:
            continue  # leave the optocouplers' outlines clear
        s = pcbnew.PCB_SHAPE(board); s.SetShape(pcbnew.SHAPE_T_SEGMENT)
        s.SetStart(pt(31.8 + 9.0, y)); s.SetEnd(pt(31.8 + 9.0, y + 1.5)); s.SetLayer(pcbnew.F_SilkS); s.SetWidth(mm(0.15))
        board.Add(s)

    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    board.Save(OUT)
    print("saved", OUT)


if __name__ == "__main__":
    main()
