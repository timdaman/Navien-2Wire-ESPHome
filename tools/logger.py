import sys, time, json; sys.path.insert(0,".")
import numpy as np
from scope import Scope; from grab import grab; from decode import bursts, halfbits, manch
N=int(sys.argv[1]); out=sys.argv[2]
sc=Scope(); sc.w(":TRIG:EDGE:LEV 10"); sc.w(":TRIG:SWE NORM")
f=open(out,"a")
for i in range(N):
    sc.w(":SING"); time.sleep(0.4); t0=time.time()
    while sc.q(":TRIG:STAT?")!="STOP":
        time.sleep(0.05)
        if time.time()-t0>3: break
    t,v=grab(sc, mode="RAW", fmt="BYTE")
    for ev in bursts(t,v):
        seg=(t>=ev[0][0])&(t<=ev[-1][0]); pk=float(v[seg].max())
        hb=halfbits(ev); bits=manch(hb+"0",0)
        rec=dict(ts=time.time(), cap=i, off_ms=round(ev[0][0]*1e3,2), peak=round(pk,2), bits=bits)
        f.write(json.dumps(rec)+"\n"); f.flush()
        print(i, f"{rec['off_ms']:7.2f}", f"{pk:5.2f}", bits)
