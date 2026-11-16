"""Tras corregir el generador de escenarios (offsets de cluster ~ U(0, 45 min)): re-evalua starter, referencias y la
configuracion de la 1.a corrida (con el bucle de despacho corregido) en TODOS los escenarios sinteticos.
Escribe robustness_results_all.csv (insumo de optimize2, select_v2, v2data)."""
import json
import pandas as pd
from concurrent.futures import ProcessPoolExecutor
import optimize2 as O2, robustness as R, sim_harness as H

CACHE = H.REPO / "solucion" / "outputs" / "cache" / "evals_fixed.jsonl"
OUT = H.REPO / "solucion" / "outputs" / "csvs"

if __name__ == "__main__":
    O2.keep_awake()
    idx = json.loads((H.REPO / "solucion/scenarios_mc/index.json").read_text())
    idx_e = json.loads((H.REPO / "solucion/scenarios_mc/index_edge.json").read_text())
    scen = sorted(idx) + sorted(idx_e)
    frames = []
    with ProcessPoolExecutor(max_workers=8) as pool:
        frames.append(R.run({"starter": None}, scen, H.HERE / "starter_baseline.py", CACHE, pool))
        frames.append(R.run({"ref_price": {"mode": "price"}, "ref_eta": {"mode": "eta"}, "ref_mix": {"mode": "mix"}}, scen, H.HERE / "ref_simple.py", CACHE, pool))
        frames.append(R.run({"wt6_la240_up": {}}, scen, H.HERE / "policy_v2.py", CACHE, pool))      # 1.a corrida (constantes originales, bucle corregido)
        frames.append(R.run({"run1_archivo": None}, scen, H.HERE / "candidate_run1.py", CACHE, pool))  # archivo de la 1.a corrida tal cual (con el defecto del bucle)
    df = pd.concat(frames, ignore_index=True)
    df["split"] = df.scenario.str.split("_").str[0]
    df.to_csv(OUT / "robustness_results_all.csv", index=False)
    print("DONE_FIXED", len(df), df.candidate.nunique(), "candidatos;", df.scenario.nunique(), "escenarios")
