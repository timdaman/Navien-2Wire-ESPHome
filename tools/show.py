import json, sys
recs=[json.loads(l) for l in open(sys.argv[1])]
t0=recs[0]["ts"]
for r in recs:
    b=r["bits"]; d=b[1:33]
    hx=" ".join(f"{int(d[i:i+8],2):02X}" for i in range(0,32,8)) if len(b)>=33 and "?" not in d else "?? "+b
    who="HTR" if r["peak"]>10 else "RMT"
    print(f"{r['ts']-t0:7.2f}s w{r.get('win',0)} {who} {hx}  len{len(b)}")
