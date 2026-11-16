"""Medicion de CPU/RSS en serie (maquina quieta) con repeticiones: la mediana de 3 imita al evaluador."""
import sys, statistics as st, json
from pathlib import Path
import sim_harness as H

def probe(configs, data, reps=3, source=H.POLICY_SRC):
    work = Path(H.HERE.parent / "scratch" / "w").resolve()
    out = {}
    for name, params in configs.items():
        cpus, rss, wall, extra = [], [], [], None
        for r in range(reps):
            m = H.evaluate(params, data, work, f"cpu_{name}_{r}", source)
            cpus.append(m["cpu_s"]); rss.append(m["rss_mb"]); wall.append(m["wall_s"]); extra = m
        out[name] = {"cpu_med": st.median(cpus), "cpu_all": [round(c, 2) for c in cpus], "rss_med": st.median(rss),
                     "wall_med": st.median(wall), "cost": extra["cost_total"], "lead": extra["lead_mean"], "rcp": extra["rcp"]}
    return out

if __name__ == "__main__":
    data = H.REPO / "data"
    cfg = {"default": {}, "tick_only": {"dispatch_on_arrival": 0}, "hungarian": {"assign": 1}, "hold_off": {"hold_on": 0}}
    res = probe(cfg, data)
    for k, v in res.items(): print(k, v)
