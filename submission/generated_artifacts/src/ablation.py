"""Ablaciones del policy ganador (OFFLINE): cuanto aporta cada componente.

Variantes sobre TUNE_SET (8 escenarios) con los parametros ganadores + CPU neta en el 5k publico (serie).
Salida: outputs/csvs/ablation_components.csv
"""
from __future__ import annotations
import json, sys
import numpy as np, pandas as pd
import optimize as O, sim_harness as H, tuning as T, cpu_probe as P

VARIANTS = {
    "full": {},
    "sin_retencion (hold_on=0)": {"hold_on": 0},
    "sin_despacho_al_llegar (solo ticks)": {"dispatch_on_arrival": 0},
    "hungarian_por_tick (assign=1)": {"assign": 1},
    "sin_riesgo_de_fallo (w_fail=0)": {"w_fail": 0.0},
    "sin_valor_del_tiempo (w_time=0)": {"w_time": 0.0},
    "sin_prioridad_VIP (w_vip=1, vip_fail_extra=0)": {"w_vip": 1.0, "vip_fail_extra": 0.0},
    "sin_coste_sombra_flota (w_unit=0)": {"w_unit": 0.0},
    "sin_liberar_cluster_completo": {"hold_full_release": 0},
    "sin_retener_segundo_miembro": {"hold_second": 0},
}


def main(best: dict):
    refs = O.load_refs()
    kinds = O.kinds_of(O.TUNE_SET)
    cands = [{**best, **v} for v in VARIANTS.values()]
    res = T.evaluate_many(cands, O.TUNE_SET)
    rows = []
    for (name, _), r in zip(VARIANTS.items(), res):
        df = pd.DataFrame(r).T
        rows.append({"variante": name,
                     "J": H.weighted_objective(r, refs, kinds, O.W_NO_CPU),
                     "coste_vs_ref": float(np.mean([r[s]["cost_total"] / refs[s]["cost_total"] for s in r])),
                     "lead_vs_ref": float(np.mean([r[s]["lead_mean"] / refs[s]["lead_mean"] for s in r])),
                     "p95_vs_ref": float(np.mean([r[s]["lead_p95"] / refs[s]["lead_p95"] for s in r])),
                     "rcp": float(df.rcp.mean()), "lote_medio": float(df.avg_batch.mean()),
                     "gates_malos": int(((df.unresolved > 0) | (df.hold_breaches > 0) | (df.sla_breach_rate > 0.06)).sum())})
    out = pd.DataFrame(rows)
    # CPU neta en el 5k publico, en serie, mediana de 3 (piso no-op en la misma sesion)
    noop = H.REPO / "solucion" / "scratch" / "noop_strategy.py"
    floor = P.probe({"noop": {}}, H.REPO / "data", reps=3, source=noop)["noop"]["cpu_med"]
    cpu = P.probe({k: {**best, **v} for k, v in VARIANTS.items()}, H.REPO / "data", reps=3)
    out["cpu_neta_5k_s"] = [cpu[k]["cpu_med"] - floor for k in VARIANTS]
    out["rss_5k_mb"] = [cpu[k]["rss_med"] for k in VARIANTS]
    out.to_csv(H.REPO / "solucion" / "outputs" / "csvs" / "ablation_components.csv", index=False)
    print(out.round(3).to_string())
    return out

if __name__ == "__main__":
    best = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {}
    main(best)
