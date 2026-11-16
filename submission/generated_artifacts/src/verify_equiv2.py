import json, pandas as pd
from concurrent.futures import ThreadPoolExecutor
import sim_harness as H, sweep_worker as W
FINAL = H.REPO / "candidate_strategy.py"
C = H.REPO / "solucion/outputs/csvs/"
a = pd.read_csv(C / "v2_robustness_candidates.csv"); a = a[a.candidate == "incumbente"].set_index("scenario")
b = pd.read_csv(C / "fin2_results.csv"); b = b[b.candidate == "incumbente"].set_index("scenario")
ref = pd.concat([a, b])
SC = ["tune_base_0", "tune_peak_2", "tune_rural_holiday_1", "edge_stress_up", "edge_cap1", "edge_stress_xl", "hold_catalog_0", "hold_peak_1",
      "edge_opaque_ids", "edge_all_closed_sun_hol", "final_catalog_1", "final_rural_holiday_2", "fin2_peak_2", "fin2_rural_holiday_3", "fin2_catalog_3", "fin2_base_1"]
def run(s):
    return s, H.run_engine(FINAL, W.scenario_dir(s), H.REPO / "solucion/scratch/w" / f"eq2_{s}.json")
if __name__ == "__main__":
    with ThreadPoolExecutor(6) as ex: res = dict(ex.map(run, SC))
    ok = True; rows = []
    for s in SC:
        m, r = res[s], ref.loc[s]
        same = (m["cost_total"] == r.cost_total and abs(m["lead_mean"] - r.lead_mean) < 1e-9 and m["lead_p95"] == r.lead_p95 and m["unresolved"] == r.unresolved and m["hold_breaches"] == r.hold_breaches and abs(m["rcp"] - r.rcp) < 1e-9)
        ok &= bool(same); rows.append({"scenario": s, "igual": bool(same), "cost_final": m["cost_total"], "cost_inv": int(r.cost_total), "lead_final": m["lead_mean"], "lead_inv": r.lead_mean})
    out = pd.DataFrame(rows); out.to_csv(C / "equivalence_final_vs_research.csv", index=False)
    print(out.to_string()); print("EQUIVALENCIA TOTAL" if ok else "HAY DIFERENCIAS")
