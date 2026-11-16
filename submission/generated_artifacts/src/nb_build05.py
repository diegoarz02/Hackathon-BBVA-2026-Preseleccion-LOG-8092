"""Notebook 05: aporte de cada pieza, techos y recursos (se importa desde nb_build.py)."""
from nb_build import SETUP, build, code, md


def nb05():
    c = [md("""
# 05 · Aporte de cada pieza, techos medidos y recursos

**Pregunta:** ¿cada componente de la política aporta algo, queda margen real de mejora y cuánto cuesta en CPU y memoria?
Se mide la ablación sobre la propuesta final, las reglas de mejoras que se probaron y no se adoptaron, los techos de agrupación, de p95 y de la espera para agrupar,
y la CPU y la RAM al estilo del evaluador. Cada tabla sale de un CSV de `outputs/csvs/`.
"""), code(SETUP), md("""
## 1 · Ablación sobre la propuesta final (afinado y decisión, 28 escenarios)
ΔJ a secas sugiere que el riesgo de fallo, el coste sombra y el emparejamiento no aportan; los puntos de cohorte y la dominancia sobre el starter dicen otra cosa,
porque J suma magnitudes relativas y no mira si se gana al starter escenario a escenario.
"""), code(r"""
abf = pd.read_csv(CSV/"ablation_final.csv")
import matplotlib.pyplot as plt
a = abf[abf.variante != "completo"].copy(); full = abf[abf.variante=="completo"].iloc[0]; a["dJ"] = a.J - full.J; a = a.sort_values("puntos_proxy")
fig, ax = plt.subplots(1, 2, figsize=(9.4, 3.4), sharey=True)
b = ax[0].barh(a.variante, a.dJ, color=[PS.ORANGE if v > 0.02 else PS.AQUA for v in a.dJ], height=0.62)
for r, v in zip(b, a.dJ): ax[0].text(v + (0.006 if v >= 0 else -0.006), r.get_y()+r.get_height()/2, f"{v:+.3f}", va="center", ha="left" if v >= 0 else "right", fontsize=6.5, color=PS.INK2)
ax[0].axvline(0, color=PS.INK2, lw=0.7); ax[0].grid(axis="y", visible=False); ax[0].set_xlim(a.dJ.min() - 0.09, a.dJ.max() + 0.07)
ax[0].set_title("Δ J al quitar el componente (↑ = peor)", fontsize=8)
b2 = ax[1].barh(a.variante, a.puntos_proxy, color=PS.BLUE, height=0.62)
for r, v, d in zip(b2, a.puntos_proxy, a.domina_starter_de_28): ax[1].text(v + 0.6, r.get_y()+r.get_height()/2, f"{v:.1f}  ({int(d)}/28)", va="center", fontsize=6.5, color=PS.INK2)
ax[1].axvline(full.puntos_proxy, color=PS.ORANGE, lw=1.3); ax[1].grid(axis="y", visible=False); ax[1].set_xlim(0, a.puntos_proxy.max() * 1.28)
ax[1].set_title(f"Puntos de cohorte (↑ = mejor); línea = completo, {full.puntos_proxy:.1f}\n(entre paréntesis, escenarios donde domina al starter)", fontsize=8)
fig.suptitle("Ablación sobre la propuesta final (28 escenarios)", fontsize=9.5, fontweight="bold", x=0.02, ha="left"); fig.tight_layout(); fig.savefig(FIG/"ablacion_final.png"); show(fig)
abf.round(3)
"""), md("""
## 2 · Reglas SPEED_SHIFT y EXPANDED_CAPACITY (probadas, no adoptadas)
`SPEED_SHIFT` se compra si el valor del tiempo ahorrado el periodo anterior (20 % del trayecto de ida × `w_time`) cubre κ veces su coste; `EXPANDED_CAPACITY` si hubo muchos grupos partidos por capacidad.
"""), code(r"""
sp = pd.read_csv(CSV/"speed_capacity_rules.csv")
scen_sp = [c[5:] for c in sp.columns if c.startswith("cost_")]
show(figs.speed_rules(sp, scen_sp))
sp[["variante","speed_total","cap_total","extra_total"]]
"""), md("""
## 3 · Techos medidos
- **Lotes:** cada cluster necesita al menos un lote en el primer intento y cada reintento fallido, como mucho, uno más; la cota superior es clusters más fallos.
- **p95:** parte es irreducible, porque la mayoría de los fallos son ausencias del cliente (no dependen del transportista) y el reintento espera 1 440 min. La referencia «siempre el transportista más rápido» marca la cota práctica.
- **Espera para agrupar:** un oráculo que conoce el tamaño real de cada cluster acota cuánto podría mejorar cualquier regla de espera más inteligente.
"""), code(r"""
ce = pd.read_csv(CSV/"ceiling_batches_p95.csv"); show(figs.ceilings(ce)); ce[["lote_vs_cota_sup_pct","p95_vs_eta_pct"]].describe().loc[["mean","min","max"]].round(2)
"""), code(r"""
orc = pd.read_csv(CSV/"techo_retencion_oraculo.csv"); print("Oráculo frente al archivo final (negativo = mejora del oráculo):"); display(orc)
post = pd.read_csv(CSV/"espera_posterior_barrido.csv"); print("Regla de espera por posterior frente a la regla final (afinado y decisión):"); post
"""), md("""
## 4 · CPU y RAM al estilo del evaluador
Un calentamiento y la **mediana de 3** ejecuciones, en serie e intercaladas (estrategia nula, starter y final), sobre dos escenarios de carga (5 000 y 150 000 tarjetas).
CPU neta = CPU menos la CPU de la estrategia nula, que es el piso del motor.
"""), code(r"""
cp = {s: pd.read_csv(CSV/f"cpu_eval_{s}.csv") for s in ["public_5k","public_150k"]}
show(figs.cpu_bars(cp))
pd.concat(cp.values()).round(2)
""")]
    return build("05_aporte_y_recursos.ipynb", c)
