"""Techos medidos: lotes frente a la cota superior (clusters + intentos fallidos) y p95 frente a la regla 'siempre el carrier mas rapido'.
Usa el ARCHIVO final en HOLD, FINAL y FIN2. Escribe outputs/csvs/ceiling_batches_p95.csv."""
import numpy as np, pandas as pd
import sim_harness as H

C = H.REPO / "solucion" / "outputs" / "csvs"
ff = pd.read_csv(C / "final_file_validation.csv"); ff = ff[ff.candidate == "final_file"].set_index("scenario")
ref = pd.read_csv(C / "robustness_results_all.csv"); ref = ref[ref.candidate == "ref_eta"].set_index("scenario")
rows = []
for s in sorted(x for x in ff.index if x.startswith(("hold_", "final_", "fin2_"))):
    cl = pd.read_csv(H.REPO / "solucion/scenarios_mc" / s / "shipments.csv", usecols=["delivery_cluster_id"]).delivery_cluster_id.nunique()
    f, e = ff.loc[s], ref.loc[s]
    sup = cl + int(f.failed_attempts)
    rows.append({"scenario": s, "clusters": cl, "batches": int(f.batches), "failed": int(f.failed_attempts), "cota_inf": cl + int(np.ceil(f.failed_attempts / 4)), "cota_sup": sup,
                 "lote_vs_cota_sup_pct": round(100 * (f.batches / sup - 1), 2), "p95_final": f.lead_p95, "p95_ref_eta": e.lead_p95, "p95_vs_eta_pct": round(100 * (f.lead_p95 / e.lead_p95 - 1), 2)})
t = pd.DataFrame(rows); t.to_csv(C / "ceiling_batches_p95.csv", index=False)
print(t[["lote_vs_cota_sup_pct", "p95_vs_eta_pct"]].describe().loc[["mean", "min", "max"]].round(2))
