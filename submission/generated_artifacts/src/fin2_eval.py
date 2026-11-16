"""Holdout FRESCO (fin2_*): candidato final + incumbente + starter + referencias, solo para validar."""
import json, sys
import pandas as pd
from concurrent.futures import ProcessPoolExecutor
import optimize2 as O2, robustness as R, sim_harness as H

C = H.REPO / "solucion" / "outputs" / "csvs"
CACHE = H.REPO / "solucion" / "outputs" / "cache" / "evals_fin2.jsonl"
if __name__ == "__main__":
    O2.keep_awake()
    idx = json.loads((H.REPO / "solucion/scenarios_mc/index.json").read_text())
    scen = sorted(k for k in idx if k.startswith("fin2_"))
    dec = json.load(open(C / "v2_decision.json"))
    allc = json.load(open(C / "v2_candidates.json"))
    names = sys.argv[1:] or list(dec["params_shortlist"])
    cands = {"incumbente": {}, **{n: allc[n] for n in names}}
    frames = []
    with ProcessPoolExecutor(max_workers=8) as pool:
        frames.append(R.run(cands, scen, H.HERE / "policy_v2.py", CACHE, pool))
        frames.append(R.run({"starter": None}, scen, H.HERE / "starter_baseline.py", CACHE, pool))
        frames.append(R.run({"ref_price": {"mode": "price"}, "ref_eta": {"mode": "eta"}, "ref_mix": {"mode": "mix"}}, scen, H.HERE / "ref_simple.py", CACHE, pool))
    df = pd.concat(frames, ignore_index=True)
    df.to_csv(C / "fin2_results.csv", index=False)
    print("DONE_FIN2", len(df))
