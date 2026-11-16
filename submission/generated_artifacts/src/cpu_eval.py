"""CPU/RAM al estilo del evaluador: 1 ejecucion de calentamiento + mediana de 3, EN SERIE e intercaladas (noop/starter/final),
sobre un escenario de carga comun. Reporta crudo y neto del piso del motor. Uso: python cpu_eval.py public_5k|public_150k [ruta_estrategia]"""
import json, statistics as st, sys
from pathlib import Path
import pandas as pd
import sim_harness as H

CASES = {"public_5k": H.REPO / "data", "public_150k": H.REPO / "scenarios" / "public_150k"}
if __name__ == "__main__":
    scen = sys.argv[1]
    final = Path(sys.argv[2]) if len(sys.argv) > 2 else H.REPO / "candidate_strategy.py"
    pols = {"noop": H.REPO / "solucion/scratch/noop_strategy.py", "starter": H.HERE / "starter_baseline.py", "final": final}
    w = H.REPO / "solucion/scratch/w"; w.mkdir(parents=True, exist_ok=True)
    runs = {k: [] for k in pols}
    for rnd in range(4):                      # ronda 0 = calentamiento (se descarta)
        for k, path in pols.items():
            m = H.run_engine(path, CASES[scen], w / f"cpuev_{scen}_{k}.json")
            print(rnd, k, round(m["cpu_s"], 2), round(m["rss_mb"], 1), round(m["wall_s"]), flush=True)
            if rnd > 0: runs[k].append(m)
    rows = []
    floor = st.median(x["cpu_s"] for x in runs["noop"])
    floor_rss = st.median(x["rss_mb"] for x in runs["noop"])
    for k, rr in runs.items():
        cpu, rss = st.median(x["cpu_s"] for x in rr), st.median(x["rss_mb"] for x in rr)
        last = rr[-1]
        rows.append({"escenario": scen, "estrategia": k, "status": last["status"], "admitted": last["admitted"], "delivered": last["delivered"], "returned": last["returned"],
                     "unresolved": last["unresolved"], "hold_breaches": last["hold_breaches"], "sla_breach_rate": last["sla_breach_rate"], "rcp": last["rcp"],
                     "cost_total": last["cost_total"], "lead_mean": last["lead_mean"], "lead_p95": last["lead_p95"], "avg_batch": last["avg_batch"],
                     "pristine": last["pristine"], "cpu_s_mediana3": cpu, "cpu_s_runs": [round(x["cpu_s"], 2) for x in rr],
                     "cpu_neta_s": cpu - floor, "rss_mib_mediana3": rss, "rss_neta_mib": rss - floor_rss,
                     "wall_s_mediana3": st.median(x["wall_s"] for x in rr)})
    out = pd.DataFrame(rows); out.to_csv(H.REPO / f"solucion/outputs/csvs/cpu_eval_{scen}.csv", index=False)
    print(out.to_string())
