"""Compara starter, corrida 1 y archivo final en los tres casos edge infactibles por construccion."""
import pandas as pd
from concurrent.futures import ProcessPoolExecutor
import robustness as R, sim_harness as H
SC = ["edge_no_hard_access", "edge_zone_uncovered", "edge_burst_1500"]
if __name__ == "__main__":
    out = []
    with ProcessPoolExecutor(max_workers=3) as pool:
        for lab, src in (("starter", H.REPO / "solucion/src/starter_baseline.py"), ("run1", H.REPO / "solucion/src/candidate_run1.py"), ("final", H.REPO / "candidate_strategy.py")):
            df = R.run({lab: None}, SC, src, H.REPO / "solucion/outputs/cache/evals_edge_cmp.jsonl", pool)
            df["candidato"] = lab; out.append(df)
    d = pd.concat(out)
    cols = ["scenario", "candidato", "unresolved", "sla_breach_rate", "hold_breaches", "cost_total", "lead_mean"]
    d[cols].to_csv(H.REPO / "solucion/outputs/csvs/edge_infeasible_comparison.csv", index=False)
    print(d[cols].to_string())
