import json, sys, statistics as st
d = json.load(open(sys.argv[1], encoding="utf-8"))
lb = d["instancia"]["linea_base"]
print("linea_base:", str(lb)[:150])
num = lambda x: isinstance(x, (int, float)) and not isinstance(x, bool)
opt = None
if isinstance(lb, dict):
    opt = next((v for k, v in lb.items() if "dist" in k.lower() and num(v)), None)
elif num(lb):
    opt = lb
print("optimo usado:", opt)
g = {}
for c in d["corridas"]:
    g.setdefault(c["formulacion"], []).append(c)
for f, cs in g.items():
    fact = [c for c in cs if c["ruta"]["factible"]]
    dist = [c["metricas"]["distancia_total"] for c in fact]
    p = cs[0]["parametros"]
    print(f"\n{f}: {len(fact)}/{len(cs)} factibles | shots={set(c['parametros'].get('shots') for c in cs)}"
          f" | backend={set(c['parametros'].get('backend') for c in cs)}")
    if dist:
        m = st.mean(dist); s = st.stdev(dist) if len(dist) > 1 else 0.0
        print(f"  distancia (factibles): {m:.3f} ± {s:.3f} km")
        if opt:
            print(f"  gap medio: {(m-opt)/opt*100:.2f} %"
                  f" | en el óptimo: {sum(abs(x-opt)<1e-3 for x in dist)}/{len(dist)}")
    print("  parametros[0]:", {k: str(v)[:40] for k, v in p.items()})