import sys, time, numpy as np
sys.path.insert(0, ".")
from scope import Scope
def grab(sc, mode="NORM", src="CHAN1", fmt="WORD"):
    sc.w(f":WAV:SOUR {src}"); sc.w(f":WAV:MODE {mode}"); sc.w(f":WAV:FORM {fmt}")
    if mode == "RAW":
        n = int(float(sc.q(":ACQ:MDEP?")))
        pts = []
        start = 1
        step = 1_000_000 if fmt == "BYTE" else 500_000
        while start <= n:
            stop = min(start + step - 1, n)
            sc.w(f":WAV:STAR {start}"); sc.w(f":WAV:STOP {stop}")
            pts.append(sc.qbin(":WAV:DATA?")); start = stop + 1
        raw = b"".join(pts)
    else:
        raw = sc.qbin(":WAV:DATA?")
    pre = [float(x) for x in sc.q(":WAV:PRE?").split(",")]
    xinc, xor, xref, yinc, yor, yref = pre[4:10]
    d = np.frombuffer(raw, dtype=np.uint8 if fmt == "BYTE" else "<u2").astype(float)
    v = (d - yor - yref) * yinc
    t = (np.arange(len(v)) - xref) * xinc + xor
    return t, v
