"""Barrido de la regla de espera por posterior (policy_v3.py) frente a la regla anterior, en TUNE+HOLD."""
import sys, json
import pandas as pd
from concurrent.futures import ProcessPoolExecutor
import robustness as R, optimize2 as O2, sim_harness as H, v2data as V

CACHE = H.REPO / "solucion/outputs/cache/evals_v3.jsonl"
if __name__ == "__main__":
    O2.keep_awake()
    tune, hold, edge = R.scenario_lists()
    scen = tune + hold
    extra = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {}
    cands = {"regla_anterior": {"hold_rule": 0, **extra}}
    for g in (150, 300, 500, 800, 1300, 2500):
        cands[f"posterior_F{g}"] = {"hold_rule": 1, "hold_gain": float(g), **extra}
    with ProcessPoolExecutor(max_workers=8) as pool:
        df = R.run(cands, scen, H.HERE / "policy_v3.py", CACHE, pool)
    base = df[df.candidate == "regla_anterior"].set_index("scenario")
    rows = []
    for c in cands:
        g = df[df.candidate == c].set_index("scenario").loc[base.index]
        rows.append({"cand": c, "coste%": round(100 * (g.cost_total / base.cost_total - 1).mean(), 2), "lead%": round(100 * (g.lead_mean / base.lead_mean - 1).mean(), 2),
                     "p95%": round(100 * (g.lead_p95 / base.lead_p95 - 1).mean(), 2), "rcp": round((g.rcp - base.rcp).mean(), 4), "lote": round(g.avg_batch.mean(), 3),
                     "gates": int(sum(V.gate_ok(g.loc[s]) for s in g.index)), "n": len(g), "gana lead": int((g.lead_mean < base.lead_mean).sum()), "gana coste": int((g.cost_total < base.cost_total).sum())})
    out = pd.DataFrame(rows); print(out.to_string())
    out.to_csv(H.REPO / "solucion/scratch/sweep_v3.csv", index=False)
