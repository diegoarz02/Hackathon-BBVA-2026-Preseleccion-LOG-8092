"""2.a corrida, Paso 1: robustez de los mejores del re-tuning (estructura final) + incumbente en TUNE+HOLD+EDGE+FINAL."""
import json, sys
import pandas as pd
from concurrent.futures import ProcessPoolExecutor
import optimize2 as O2, robustness as R, sim_harness as H

CACHE = H.REPO / "solucion" / "outputs" / "cache" / "evals_robust_v2.jsonl"
OUT = H.REPO / "solucion" / "outputs" / "csvs"

def final_scenarios():
    idx = json.loads((H.REPO / "solucion/scenarios_mc/index.json").read_text())
    return sorted(k for k in idx if k.startswith("final_"))

def candidates():
    c = {"incumbente": {}}
    for n in ("grid", "random", "sobol", "tpe", "cmaes"):
        ck = O2.load_ckpt(n)
        ok = [t for t in ck["trials"] if t.get("gate_bad", 1) == 0]
        top = sorted(ok, key=lambda r: r["value"])[:2]
        for i, t in enumerate(top, 1):
            c[f"{n}#{i}"] = t["params"]
    return c

if __name__ == "__main__":
    O2.keep_awake()
    tune, hold, edge = R.scenario_lists()
    scen = tune + hold + edge + final_scenarios()
    cands = candidates()
    json.dump(cands, open(OUT / "v2_candidates.json", "w"), indent=1)
    frames = []
    with ProcessPoolExecutor(max_workers=8) as pool:
        frames.append(R.run(cands, scen, H.HERE / "policy_v2.py", CACHE, pool))
    df = pd.concat(frames, ignore_index=True)
    df["split"] = df.scenario.str.split("_").str[0]
    df.to_csv(OUT / "v2_robustness_candidates.csv", index=False)
    print("DONE_ROBUST_V2", len(df), "candidatos:", len(cands))
