"""(Version general: python add_candidate.py '{"nombre": {"parametro": valor}}'  anade candidatos explicitos sobre las constantes del incumbente.)
Anade a la comparacion la variante 'tpe#2_ns' (tpe#2 sin compras de SPEED_SHIFT: speed_kappa al maximo del espacio), para que el
archivo final no necesite codigo de SPEED_SHIFT. Evalua en TODOS los escenarios y la agrega a v2_robustness_candidates.csv / v2_candidates.json."""
import json
import pandas as pd
from concurrent.futures import ProcessPoolExecutor
import optimize2 as O2, robust_v2 as RV, robustness as R, sim_harness as H

C = H.REPO / "solucion" / "outputs" / "csvs"
if __name__ == "__main__":
    import sys
    O2.keep_awake()
    cands = json.load(open(C / "v2_candidates.json"))
    if len(sys.argv) > 1:
        add = json.loads(sys.argv[1])
    else:
        add = {"tpe#2_ns": {**cands["tpe#2"], "speed_kappa": 30.0}}
    cands.update(add)
    json.dump(cands, open(C / "v2_candidates.json", "w"), indent=1)
    tune, hold, edge = R.scenario_lists()
    scen = tune + hold + edge + RV.final_scenarios()
    with ProcessPoolExecutor(max_workers=8) as pool:
        df = R.run(add, scen, H.HERE / "policy_v2.py", RV.CACHE, pool)
    df["split"] = df.scenario.str.split("_").str[0]
    old = pd.read_csv(C / "v2_robustness_candidates.csv")
    old = old[~old.candidate.isin(list(add))]
    pd.concat([old, df], ignore_index=True).to_csv(C / "v2_robustness_candidates.csv", index=False)
    print("DONE_ADD", len(df), list(add))
