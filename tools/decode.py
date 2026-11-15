import numpy as np, sys
T=500e-6
def bursts(t,v,th=7.4,gap=5e-3):
    hi=v>th; e=np.flatnonzero(np.diff(hi.astype(np.int8)))
    ev=[(t[i+1],bool(hi[i+1])) for i in e]
    out=[];cur=[]
    for x in ev:
        if cur and x[0]-cur[-1][0]>gap: out.append(cur);cur=[]
        cur.append(x)
    if cur: out.append(cur)
    return out
def halfbits(ev):
    s=""
    for (a,up),(b,_) in zip(ev,ev[1:]):
        n=round((b-a)/T); s+=("1" if up else "0")*n
    return s+"1"*0  # ends on falling edge (last high run included)
def manch(s, phase, hl_is_one=True):
    s=s[phase:]; bits=""
    for i in range(0,len(s)-1,2):
        p=s[i:i+2]
        if p=="10": bits+="1" if hl_is_one else "0"
        elif p=="01": bits+="0" if hl_is_one else "1"
        else: bits+="?"
    return bits
if __name__=="__main__":
    t,v=np.load(sys.argv[1])
    for k,ev in enumerate(bursts(t,v)):
        hb=halfbits(ev)
        print(f"burst {k} @ {ev[0][0]*1e3:.1f} ms, {len(hb)} half-bits")
        print("  levels:", hb)
        for ph in (0,1):
            print(f"  phase{ph} (H->L=1):", manch(hb+"0",ph))
