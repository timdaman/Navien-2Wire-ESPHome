# Continuous-ish logger: roll mode, long window, stop -> download -> run.
import sys, time, json; sys.path.insert(0,".")
import numpy as np
from scope import Scope; from grab import grab; from decode import bursts, halfbits, manch
N=int(sys.argv[1]); out=sys.argv[2]; div=float(sys.argv[3]) if len(sys.argv)>3 else 1.0
sc=Scope()
sc.w(":ACQ:MDEP 10M"); sc.w(f":TIM:SCAL {div}"); sc.w(":TIM:OFFS 0"); sc.w(":TRIG:SWE AUTO"); sc.w(":RUN")
time.sleep(10*div+0.5)
f=open(out,"a"); last_end=None
for i in range(N):
    try:
        sc.w(":STOP"); tstop=time.time(); time.sleep(0.3)
        t,v=grab(sc, mode="RAW", fmt="BYTE")
    except Exception as e:
        print(i, "error:", repr(e), "- reconnecting", flush=True)
        time.sleep(2)
        try: sc.s.close()
        except Exception: pass
        sc=Scope(); sc.w(":RUN"); time.sleep(10*div+0.5)
        continue
    sc.w(":RUN"); t_run=time.time()
    np.save(f"{out}.w{i}.npy", np.vstack([t,v]).astype(np.float32)); open(f"{out}.w{i}.tstop","w").write(str(tstop))
    span=t[-1]-t[0]
    for ev in bursts(t,v):
        if ev[-1][0] > t[-1]-0.05 or ev[0][0] < t[0]+0.05: continue   # skip cut-off bursts
        seg=(t>=ev[0][0])&(t<=ev[-1][0]); pk=float(v[seg].max())
        bits=manch(halfbits(ev)+"0",0)
        ts=tstop-(t[-1]-ev[0][0])
        f.write(json.dumps(dict(ts=ts, win=i, peak=round(pk,2), bits=bits))+"\n")
    f.flush()
    print(i, "span %.2fs pts %d dt %.2gs, dl %.1fs"%(span,len(v),t[1]-t[0],t_run-tstop), flush=True)
    time.sleep(max(0, span - (time.time()-t_run)))   # refill the window before next stop
