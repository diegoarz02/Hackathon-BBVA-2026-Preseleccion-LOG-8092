"""Efecto del emparejamiento con arrepentimiento (assign_k=1 = solo greedy) en los casos de contrato y estres, con las constantes finales."""
import pandas as pd
from concurrent.futures import ProcessPoolExecutor
import robustness as R, sim_harness as H, v2data as V

if __name__ == "__main__":
    tune, hold, edge = R.scenario_lists()
    scen = [s for s in edge if s not in ("edge_empty", "edge_one", "edge_tiny")] + ["tune_peak_1", "tune_peak_2", "hold_peak_0", "hold_peak_2"]
    cache = H.REPO / "solucion/outputs/cache/evals_edge_matching.jsonl"
    with ProcessPoolExecutor(max_workers=8) as pool:
        df = R.run({"con_emparejamiento": {}, "solo_greedy": {"assign_k": 1}}, scen, H.HERE / "policy_v2.py", cache, pool)
    a = df[df.candidate == "con_emparejamiento"].set_index("scenario"); b = df[df.candidate == "solo_greedy"].set_index("scenario").loc[a.index]
    t = pd.DataFrame({"lead_con": a.lead_mean.round(1), "lead_greedy": b.lead_mean.round(1), "coste_con": a.cost_total, "coste_greedy": b.cost_total, "p95_con": a.lead_p95, "p95_greedy": b.lead_p95,
                      "ret_con": a.hold_breaches, "ret_greedy": b.hold_breaches, "unres_con": a.unresolved, "unres_greedy": b.unresolved, "sla_con": a.sla_breach_rate.round(4), "sla_greedy": b.sla_breach_rate.round(4)})
    t["lead_%"] = (100 * (a.lead_mean / b.lead_mean - 1)).round(1); t["coste_%"] = (100 * (a.cost_total / b.cost_total - 1)).round(2)
    t.to_csv(H.REPO / "solucion/outputs/csvs/emparejamiento_casos_extremos.csv")
    print(t.to_string())
