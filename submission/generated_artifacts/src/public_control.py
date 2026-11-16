"""Control con los datos PUBLICOS REALES (no se usan para afinar): starter, incumbente (1.a corrida) y finalistas del re-ajuste.
Escribe outputs/csvs/public_control.csv. Uso: python public_control.py [5k|150k|all]"""
import json, sys
import pandas as pd
from concurrent.futures import ProcessPoolExecutor
import optimize2 as O2, robustness as R, sim_harness as H

C = H.REPO / "solucion" / "outputs" / "csvs"
CACHE = H.REPO / "solucion" / "outputs" / "cache" / "evals_public_control.jsonl"
SCEN = {"5k": ("data", "public_5k"), "150k": ("scenarios/public_150k", "public_150k")}

if __name__ == "__main__":
    O2.keep_awake()
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    keys = list(SCEN) if which == "all" else [which]
    dec = json.load(open(C / "v2_decision.json"))
    allc = json.load(open(C / "v2_candidates.json"))
    names = sys.argv[2:] or list(dec["params_shortlist"])
    cands = {"incumbente": {}, **{n: allc[n] for n in names}}
    frames = []
    with ProcessPoolExecutor(max_workers=6) as pool:
        for k in keys:
            d, label = SCEN[k]
            fr = [R.run(cands, [d], H.HERE / "policy_v2.py", CACHE, pool), R.run({"starter": None}, [d], H.HERE / "starter_baseline.py", CACHE, pool)]
            df = pd.concat(fr, ignore_index=True); df["scenario"] = label; frames.append(df)
    out = pd.concat(frames, ignore_index=True)
    cols = ["scenario", "candidate", "status", "unresolved", "hold_breaches", "sla_breach_rate", "cost_total", "lead_mean", "lead_p95", "rcp", "avg_batch"]
    out[cols].to_csv(C / f"public_control{'' if which == 'all' else '_' + which}.csv", index=False)
    print(out[cols].to_string())
