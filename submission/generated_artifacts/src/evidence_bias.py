"""Evidencia del sesgo del generador de escenarios (hallado en la 2.a corrida) y de su correccion.
Compara los desfases de llegada dentro del cluster en datos publicos, escenarios antiguos (sesgados) y corregidos, y el efecto sobre el candidato
afinado en los escenarios antiguos. Escribe outputs/csvs/evidencia_sesgo_generador.csv."""
import numpy as np, pandas as pd
from pathlib import Path
import fidelity_audit as FA

REPO = FA.REPO
C = REPO / "solucion" / "outputs" / "csvs"
OLD = REPO / "solucion" / "scratch" / "scenarios_mc_v2a"
NEW = REPO / "solucion" / "scenarios_mc"
rows = []
pub = [FA.stats(REPO / "data/shipments.csv"), FA.stats(REPO / "scenarios/public_150k/shipments.csv")]
rows.append({"fuente": "datos públicos (5k y 150k)", **{k: float(np.mean([p[k] for p in pub])) for k in ("off_p25", "off_p50", "off_p75")}})
for lab, root in (("escenarios antiguos (sesgados)", OLD), ("escenarios corregidos", NEW)):
    st = [FA.stats(root / n / "shipments.csv") for n in ("tune_base_0", "tune_peak_0", "hold_base_1", "hold_peak_1", "final_base_0", "fin2_base_0")]
    rows.append({"fuente": lab, **{k: float(np.mean([s[k] for s in st])) for k in ("off_p25", "off_p50", "off_p75")}})
off = pd.DataFrame(rows)
# efecto sobre el candidato afinado con los escenarios antiguos (cifras archivadas) frente a la 1.a corrida en el ejemplo publico de 5k
arch = REPO / "solucion/outputs/archivo_v2a_generador_sesgado/cpu_eval_public_5k.csv"
v1 = pd.read_csv(C / "final_vs_baseline.csv"); v1 = v1[(v1.policy == "final") & (v1.scenario == "public_5k")].iloc[0]
if arch.exists():
    a = pd.read_csv(arch); a = a[a.estrategia == "final"].iloc[0]
    eff = pd.DataFrame([{"version": "candidato afinado con escenarios sesgados (tope 27.7 min)", "coste": a.cost_total, "lead": a.lead_mean, "lote_medio": a.avg_batch},
                        {"version": "constantes de la 1.a corrida (tope 45 min)", "coste": v1.cost_total, "lead": v1.lead_mean, "lote_medio": v1.avg_batch}])
    eff.to_csv(C / "evidencia_sesgo_efecto_5k.csv", index=False)
off.to_csv(C / "evidencia_sesgo_generador.csv", index=False)
print(off.round(1).to_string())
