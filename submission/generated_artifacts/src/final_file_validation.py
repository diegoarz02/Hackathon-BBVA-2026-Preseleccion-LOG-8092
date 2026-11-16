"""Validacion del ARCHIVO FINAL (candidate_strategy.py de la raiz) en TUNE+HOLD+EDGE+FINAL+FIN2, como lo ejecutaria el evaluador."""
import json, pandas as pd
from concurrent.futures import ProcessPoolExecutor
import optimize2 as O2, robustness as R, sim_harness as H

CACHE = H.REPO / "solucion" / "outputs" / "cache" / "evals_final_file.jsonl"
if __name__ == "__main__":
    O2.keep_awake()
    idx = json.loads((H.REPO / "solucion/scenarios_mc/index.json").read_text())
    tune, hold, edge = R.scenario_lists()
    scen = tune + hold + edge + sorted(k for k in idx if k.startswith(("final_", "fin2_")))
    with ProcessPoolExecutor(max_workers=8) as pool:
        df = R.run({"final_file": None}, scen, H.REPO / "candidate_strategy.py", CACHE, pool)
    df.to_csv(H.REPO / "solucion/outputs/csvs/final_file_validation.csv", index=False)
    print("DONE_FINALFILE", len(df))
