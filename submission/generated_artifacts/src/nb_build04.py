"""Notebook 04: seleccion del candidato y validacion (se importa desde nb_build.py)."""
from nb_build import SETUP, build, code, md


def nb04():
    c = [md("""
# 04 · Selección del candidato y validación

**Pregunta:** ¿qué política se entrega y cómo sabemos que la mejora es real y no un artefacto de los escenarios sintéticos?
Esta libreta recorre (1) la comprobación de fidelidad del generador contra los datos reales, (2) la regla de selección fijada de antemano y su resultado,
(3) el control con los datos públicos reales y (4) la validación por conjuntos: afinado, decisión (HOLD), validación (FINAL) y datos frescos (FIN2).
Cada tabla sale de un CSV de `outputs/csvs/`.
"""), code(SETUP), md("""
## 1 · Fidelidad del generador de escenarios frente a los datos reales
Los escenarios sintéticos se generan dentro de los rangos publicados. Antes de afinar se compara cada estadístico que la política podría explotar con los datos públicos.
El desfase de llegada entre las tarjetas de un mismo destino es uno de ellos: en los datos reales es uniforme entre 0 y 45 minutos desde la primera.
"""), code(r"""
import matplotlib.pyplot as plt
bias = pd.read_csv(CSV/"evidencia_sesgo_generador.csv")
fig, ax = plt.subplots(figsize=(7.2, 2.9))
x = range(len(bias)); w = 0.26
for i, (col, lab, colr) in enumerate((("off_p25", "cuartil 1", PS.AQUA), ("off_p50", "mediana", PS.BLUE), ("off_p75", "cuartil 3", PS.VIOLET))):
    b = ax.bar([k + (i - 1) * w for k in x], bias[col], width=w, color=colr, label=lab)
    for r, v in zip(b, bias[col]): ax.text(r.get_x() + r.get_width()/2, v + 0.6, f"{v:.0f}", ha="center", fontsize=7, color=PS.INK2)
ax.set_ylim(0, 42); ax.set_xticks(list(x)); ax.set_xticklabels(bias.fuente, fontsize=7.5); ax.set_ylabel("minutos desde la primera tarjeta"); ax.legend(fontsize=7, frameon=False, ncol=3, loc="upper left")
ax.set_title("Desfase de llegada dentro del cluster: datos reales, escenarios antiguos y corregidos", fontsize=8.5, loc="left"); ax.grid(axis="x", visible=False)
fig.tight_layout(); fig.savefig(FIG/"fidelidad_generador.png"); show(fig)
pd.read_csv(CSV/"evidencia_sesgo_efecto_5k.csv")
"""), md("""
El primer re-ajuste, hecho con los escenarios antiguos, eligió un tope de retención de 27,7 min que en el ejemplo público de 5 000 tarjetas empeoraba a la versión anterior
(tabla). Se corrigió el generador y se repitió el afinado; `fidelity_audit.py --gate` verifica los cuartiles antes de cada afinado.

## 2 · Regla de selección y resultado
Elegible: gates en HOLD, FINAL y los casos de contrato factibles, cero infracciones de retención y dominancia sobre el starter en las cuatro métricas en HOLD y FINAL.
Entre los elegibles se pide una **mejora robusta frente a la versión anterior** en puntos por percentil (intervalo bootstrap pareado con límite inferior mayor que cero);
si ninguno la logra, se conserva la versión anterior.
"""), code(r"""
sel = pd.read_csv(CSV/"v2_selection.csv"); dec = json.load(open(CSV/"v2_decision.json"))
show(figs.selection_proxy(sel))
rob = pd.DataFrame([{"candidato": k, "Δ puntos por escenario": round(v["dPuntos_medio"], 2), "IC95 inferior": round(v["IC95"][0], 2), "IC95 superior": round(v["IC95"][1], 2), "gana en": f"{v['gana_en']}/{v['n']}"}
                    for k, v in dec["robustez_puntos_vs_incumbente"].items()]).sort_values("Δ puntos por escenario", ascending=False)
print(dec["motivo"])
rob
"""), md("""
## 3 · Control con los datos públicos reales
Los datos públicos no se usan para afinar; sirven de veto. El mejor candidato alternativo y la versión conservada se comparan con el starter en ambos ejemplos.
"""), code(r"""
pc = pd.read_csv(CSV/"public_control.csv")
pc.round(3)
"""), md("""
## 4 · Validación por conjuntos (archivo final frente a starter y referencias simples)
`gana las 4` cuenta los escenarios donde la propuesta supera al starter en coste, tiempo medio, percentil 95 y satisfacción a la vez.
"""), code(r"""
import v2data as V, robustness as R
d = V.load(); S = V.scen_sets(d)
allf = pd.concat([d[k].reset_index().assign(candidate=n) for k, n in (("final", "final_v2"), ("starter", "starter"), ("ref_price", "ref_price"), ("ref_eta", "ref_eta"), ("run1", "incumbente"))], ignore_index=True)
rows = []
for k, lab in (("tune", "Afinado"), ("hold", "HOLD"), ("final", "FINAL"), ("fin2", "FIN2")):
    names = S[k]; dm, dw = V.mean_delta(d["final"], d["starter"], names), V.dominance(d["final"], d["starter"], names)
    rows.append({"conjunto": lab, "escenarios": len(names), "gates": f"{sum(V.gate_ok(d['final'].loc[s]) for s in names)}/{len(names)}", "gates starter": f"{sum(V.gate_ok(d['starter'].loc[s]) for s in names)}/{len(names)}",
                 "retención": int(d["final"].loc[names].hold_breaches.sum()), "coste vs starter %": round(dm["coste_pct"], 1), "lead %": round(dm["lead_pct"], 1), "p95 %": round(dm["p95_pct"], 1),
                 "RCP Δ": round(dm["rcp_d"], 3), "gana las 4": f"{dw['todas']}/{len(names)}"})
tab = pd.DataFrame(rows); tab
"""), md("""
### Datos frescos (FIN2): 16 escenarios que nunca intervinieron en el afinado
"""), code(r"""
names = S["fin2"]
show(figs.dumbbells(allf, names, "final_v2", "FIN2 (16 escenarios nuevos): propuesta frente al starter", "fin2_dumbbells.png", refs=("ref_price", "ref_eta")))
show(figs.improvement_heatmap(allf, names, "final_v2", "fin2_mejora_heatmap.png", "FIN2"))
st = allf[allf.candidate == "starter"].set_index("scenario").loc[names]
rows = []
for cand in ["final_v2", "incumbente", "ref_price", "ref_eta"]:
    g = allf[allf.candidate == cand].set_index("scenario").loc[names]
    rows.append({"candidato": cand, "gates": f"{sum(R.gate_ok(g.loc[s]) for s in names)}/{len(names)}", "retención": int(g.hold_breaches.sum()), "UNRESOLVED": int(g.unresolved.sum()),
                 "coste vs starter %": round(100*(g.cost_total/st.cost_total-1).mean(), 1), "lead vs starter %": round(100*(g.lead_mean/st.lead_mean-1).mean(), 1),
                 "p95 vs starter %": round(100*(g.lead_p95/st.lead_p95-1).mean(), 1), "RCP Δ": round((g.rcp-st.rcp).mean(), 3),
                 "gana coste/lead/p95/RCP": "/".join(str(int(x)) for x in [(g.cost_total<st.cost_total).sum(), (g.lead_mean<st.lead_mean).sum(), (g.lead_p95<st.lead_p95).sum(), (g.rcp>st.rcp).sum()])})
fin2_tab = pd.DataFrame(rows); fin2_tab.to_csv(CSV/"fin2_summary.csv", index=False); fin2_tab
"""), md("""
### Decisión (HOLD) y validación (FINAL)
"""), code(r"""
for k, lab in (("hold", "HOLD"), ("final", "FINAL")):
    show(figs.dumbbells(allf, S[k], "final_v2", f"{lab} ({len(S[k])} escenarios): propuesta frente al starter", f"validacion_{k}_dumbbells.png", refs=("ref_price", "ref_eta")))
    show(figs.improvement_heatmap(allf, S[k], "final_v2", f"validacion_{k}_heatmap.png", lab))
"""), md("""
### Casos de contrato (extremos y estrés)
Se evalúan casos como ráfagas de 1 500 llegadas simultáneas, lotes de capacidad 1, flota al 30 %, un solo transportista, ids opacos y zonas sin cobertura.
Los que ninguna estrategia puede resolver (zona sin ningún transportista, envíos que exigen acceso difícil sin transportista que lo tenga, ráfaga mayor que la flota) se marcan aparte.
"""), code(r"""
edge = d["final"].loc[S["edge"]][["status", "admitted", "unresolved", "sla_breach_rate", "hold_breaches", "cost_total", "lead_mean"]].copy()
edge["factible"] = [s not in V.INFEASIBLE for s in edge.index]
edge["gates"] = [V.gate_ok(d["final"].loc[s]) for s in edge.index]
edge.round(4)
""")]
    return build("04_seleccion_y_validacion.ipynb", c)
