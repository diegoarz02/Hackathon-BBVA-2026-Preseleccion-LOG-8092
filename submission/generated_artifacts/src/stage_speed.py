"""SPEED_SHIFT / EXPANDED_CAPACITY: reglas por escenario (incluido pico y estres) sobre policy_v2.py."""
import json, pandas as pd
from concurrent.futures import ProcessPoolExecutor
import optimize as O, sim_harness as H, tuning as T, robustness as R

SCEN = ["tune_base_0", "tune_base_1", "tune_peak_0", "tune_peak_1", "tune_peak_2", "tune_rural_holiday_0", "tune_rural_holiday_1",
        "tune_catalog_0", "tune_catalog_1", "edge_stress_up", "edge_stress_xl", "edge_cap1"]
BASE = {}
if __name__ == "__main__":
    O.keep_awake()
    cands = {"base": {}, **{f"speed_k{k}": {"speed_kappa": k} for k in (0.2, 0.5, 1.0, 2.0)}, "cap_s5": {"cap_splits_thr": 5}, "cap_s50": {"cap_splits_thr": 50}}
    cache = H.REPO / "solucion/outputs/cache/evals_speed.jsonl"
    with ProcessPoolExecutor(max_workers=8) as pool:
        res = T.evaluate_many(list(cands.values()), SCEN, source=H.HERE / "policy_v2.py", cache_path=cache, pool=pool)
    rows = []
    for (name, p), r in zip(cands.items(), res):
        row = {"variante": name, "speed_total": sum(r[s]["upg_speed"] for s in SCEN), "cap_total": sum(r[s]["upg_cap"] for s in SCEN),
               "extra_total": sum(r[s]["upg_extra"] for s in SCEN)}
        for s in SCEN: row[f"cost_{s}"] = r[s]["cost_total"]; row[f"lead_{s}"] = r[s]["lead_mean"]; row[f"p95_{s}"] = r[s]["lead_p95"]
        rows.append(row)
    out = pd.DataFrame(rows); out.to_csv(H.REPO / "solucion/outputs/csvs/speed_capacity_rules.csv", index=False)
    b = out.set_index("variante")
    show = pd.DataFrame({v: {"speed": b.loc[v, "speed_total"], "cap": b.loc[v, "cap_total"],
        "dcost%": 100 * sum(b.loc[v, f"cost_{s}"] / b.loc["base", f"cost_{s}"] - 1 for s in SCEN) / len(SCEN),
        "dlead%": 100 * sum(b.loc[v, f"lead_{s}"] / b.loc["base", f"lead_{s}"] - 1 for s in SCEN) / len(SCEN),
        "dp95%": 100 * sum(b.loc[v, f"p95_{s}"] / b.loc["base", f"p95_{s}"] - 1 for s in SCEN) / len(SCEN)} for v in b.index}).T
    print(show.round(3).to_string())
