import json, pandas as pd
from concurrent.futures import ProcessPoolExecutor
import optimize as O, sim_harness as H, tuning as T, robustness as R
BASE = {"w_time": 6.0, "w_vip": 8.0, "w_unit": 1.0}
SCEN = ["tune_peak_0", "tune_peak_1", "tune_peak_2", "edge_stress_up", "edge_stress_xl", "edge_stress_noup", "edge_burst_1500", "tune_base_0", "tune_catalog_0", "tune_rural_holiday_0"]
if __name__ == "__main__":
    O.keep_awake()
    rb = pd.read_csv(H.REPO / "solucion/outputs/csvs/robustness_results.csv"); refs = R.reference_rows(rb)
    cands = {"greedy": dict(BASE)}
    for tau in (15.0, 60.0, 240.0):
        cands[f"lookahead_tau{int(tau)}"] = {**BASE, "assign": 2, "la_tau": tau}
    src = H.HERE / "policy_lookahead.py"
    with ProcessPoolExecutor(max_workers=4) as pool:
        res = T.evaluate_many(list(cands.values()), SCEN, source=src, cache_path=H.REPO/"solucion/outputs/cache/evals_lookahead.jsonl", pool=pool)
    rows = []
    for (name, p), r in zip(cands.items(), res):
        kinds = {s: "peak" for s in SCEN}
        row = {"variante": name, "J": H.weighted_objective(r, refs, kinds, O.W_NO_CPU)}
        for s in SCEN: row[f"lead_{s}"] = round(r[s]["lead_mean"]); row[f"cost_{s}"] = r[s]["cost_total"]
        row["gates_malos"] = sum(not R.gate_ok(pd.Series(r[s])) for s in SCEN if s not in R.INFEASIBLE)
        row["cpu_mean"] = sum(r[s]["cpu_s"] for s in SCEN) / len(SCEN)
        rows.append(row)
    out = pd.DataFrame(rows); out.to_csv(H.REPO / "solucion/outputs/csvs/lookahead_assignment.csv", index=False)
    pd.set_option("display.width", 250); pd.set_option("display.max_columns", 50)
    print(out[["variante", "J", "gates_malos", "cpu_mean"] + [f"lead_{s}" for s in SCEN[:7]]].round(3).to_string())
