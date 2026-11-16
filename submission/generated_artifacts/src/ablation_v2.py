"""Ablacion sobre el candidato FINAL (policy_v2.py con los parametros ganadores) en TUNE+HOLD (28 escenarios) + CPU neta 5k."""
import json, sys
import numpy as np, pandas as pd
from concurrent.futures import ProcessPoolExecutor
import optimize2 as O2, robustness as R, sim_harness as H, tuning as T, cpu_probe as P

C = H.REPO / "solucion" / "outputs" / "csvs"
VARIANTS = {
    "completo": {},
    "sin retención (nunca retener)": {"hold_p_min": 1.1, "hold_second": 0},
    "sin retener al 2.º miembro": {"hold_second": 0},
    "sin liberar el cluster completo": {"hold_full_release": 0},
    "sin valor del tiempo (w_time=0)": {"w_time": 0.0},
    "sin riesgo de fallo (w_fail=0)": {"w_fail": 0.0},
    "sin prioridad VIP": {"w_vip": 1.0, "vip_fail_extra": 0.0},
    "sin coste sombra de flota": {"w_unit": 0.0},
    "sin emparejamiento (solo greedy)": {"assign_k": 1},
    "sin mejoras mensuales": {"up_wait_thr": 1e9, "speed_kappa": 1e9, "cap_splits_thr": 1e9},
    "sin SPEED_SHIFT": {"speed_kappa": 1e9},
}
if __name__ == "__main__":
    O2.keep_awake()
    best = json.load(open(C / "v2_decision.json"))["params_ganador"]
    tune, hold, _ = R.scenario_lists()
    scen = tune + hold
    cands = {k: {**best, **v} for k, v in VARIANTS.items()}
    rb = pd.read_csv(C / "robustness_results_all.csv")
    refs = R.reference_rows(rb)
    with ProcessPoolExecutor(max_workers=8) as pool:
        res = T.evaluate_many(list(cands.values()), scen, source=H.HERE / "policy_v2.py", cache_path=H.REPO / "solucion/outputs/cache/evals_ablation_v2.jsonl", pool=pool)
    rows = []
    kinds = O2.kinds_of(scen)
    for (name, _), r in zip(cands.items(), res):
        df = pd.DataFrame(r).T
        rows.append({"variante": name, "J": H.weighted_objective(r, refs, kinds, O2.W_NO_CPU),
                     "coste_vs_ref": float(np.mean([r[s]["cost_total"] / refs[s]["cost_total"] for s in r])),
                     "lead_vs_ref": float(np.mean([r[s]["lead_mean"] / refs[s]["lead_mean"] for s in r])),
                     "p95_vs_ref": float(np.mean([r[s]["lead_p95"] / refs[s]["lead_p95"] for s in r])),
                     "rcp": float(df.rcp.mean()), "lote_medio": float(df.avg_batch.mean()),
                     "gates_malos": int(((df.unresolved > 0) | (df.hold_breaches > 0) | (df.sla_breach_rate > 0.06)).sum())})
    out = pd.DataFrame(rows)
    noop = H.REPO / "solucion" / "scratch" / "noop_strategy.py"
    floor = P.probe({"noop": {}}, H.REPO / "data", reps=3, source=noop)["noop"]["cpu_med"]
    cpu = P.probe({k: v for k, v in cands.items() if k in ("completo", "sin retención (nunca retener)", "sin emparejamiento (solo greedy)", "sin mejoras mensuales")},
                  H.REPO / "data", reps=3, source=H.HERE / "policy_v2.py")
    out["cpu_neta_5k_s"] = [cpu[k]["cpu_med"] - floor if k in cpu else np.nan for k in out.variante]
    out.to_csv(C / "ablation_final.csv", index=False)
    print(out.round(3).to_string())
