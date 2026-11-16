"""Validacion FINAL en 16 escenarios NUEVOS (split 'final', nunca usados) del candidate_strategy.py de la raiz."""
import json, pandas as pd
from concurrent.futures import ProcessPoolExecutor
import optimize as O, robustness as R, sim_harness as H

CACHE = H.REPO / "solucion" / "outputs" / "cache" / "evals_final_validation.jsonl"
if __name__ == "__main__":
    O.keep_awake()
    idx = json.loads((H.REPO / "solucion/scenarios_mc/index.json").read_text())
    scen = sorted(k for k in idx if k.startswith("final_"))
    frames = []
    with ProcessPoolExecutor(max_workers=8) as pool:
        frames.append(R.run({"final": None}, scen, H.REPO / "candidate_strategy.py", CACHE, pool))
        frames.append(R.run({"starter": None}, scen, H.HERE / "starter_baseline.py", CACHE, pool))
        frames.append(R.run({"ref_price": {"mode": "price"}, "ref_eta": {"mode": "eta"}, "ref_mix": {"mode": "mix"}}, scen, H.HERE / "ref_simple.py", CACHE, pool))
    df = pd.concat(frames, ignore_index=True)
    df.to_csv(H.REPO / "solucion/outputs/csvs/final_validation_results.csv", index=False)
    print("DONE_FINALVAL", len(df))
