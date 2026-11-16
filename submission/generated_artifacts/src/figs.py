"""Figuras del solucionario (estilo dataviz). Cada funcion crea, guarda en outputs/figs/ y devuelve la figura.
Textos pequenos, color por entidad, sin etiquetas solapadas."""
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

import plotstyle as PS

FIG = Path(__file__).resolve().parents[1] / "outputs" / "figs"
PS.apply()


def _save(fig, name):
    FIG.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIG / name)
    return fig


def short(s: str) -> str:
    return s.split("_", 1)[1] if "_" in s else s


# ------------------------------------------------------------------------------------------------ EDA
def eda_arrivals(d: pd.DataFrame, name="eda_llegadas_mezcla.png"):
    fig, ax = plt.subplots(1, 2, figsize=(9.2, 3.2), gridspec_kw={"width_ratios": [1.25, 1]})
    tab = d.groupby([d.t.dt.dayofweek, d.t.dt.hour]).size().unstack(fill_value=0) / ((d.t.max() - d.t.min()).days / 7)
    im = ax[0].imshow(tab.values, aspect="auto", cmap=PS.SEQ)
    ax[0].set_yticks(range(7)); ax[0].set_yticklabels(["lun", "mar", "mié", "jue", "vie", "sáb", "dom"])
    ax[0].set_xticks(range(0, 24, 3)); ax[0].set_xticklabels([f"{h}h" for h in range(0, 24, 3)])
    ax[0].grid(False); ax[0].set_title("Llegadas por hora y día de la semana (150 k)")
    cb = fig.colorbar(im, ax=ax[0], fraction=0.045, pad=0.02); cb.ax.tick_params(labelsize=6.5); cb.set_label("tarjetas/hora", fontsize=7)
    mix = pd.crosstab(d.zone, d["product"], normalize="index").loc[["URBANA", "SUBURBANA", "RURAL", "REMOTA"]][["STANDARD", "SME", "BUSINESS", "VIP_BLACK"]]
    left = np.zeros(len(mix))
    for p in mix.columns:
        ax[1].barh(mix.index, mix[p].values, left=left, color=PS.PRODUCT_COL[p], label=p, height=0.62, edgecolor=PS.SURFACE, linewidth=1.5)
        for i, v in enumerate(mix[p].values):
            if v > 0.06:
                ax[1].text(left[i] + v / 2, i, f"{100 * v:.0f}%", ha="center", va="center", fontsize=6.5, color="white" if p != "VIP_BLACK" else PS.INK)
        left += mix[p].values
    ax[1].invert_yaxis(); ax[1].set_xlim(0, 1); ax[1].set_xticks([0, .25, .5, .75, 1]); ax[1].set_xticklabels(["0", "25", "50", "75", "100%"])
    ax[1].grid(False); ax[1].set_title("Mezcla de producto por zona")
    ax[1].legend(ncol=4, loc="upper center", bbox_to_anchor=(0.5, -0.1), fontsize=6.5)
    return _save(fig, name)


def eda_clusters(d: pd.DataFrame, name="eda_clusters.png"):
    csz = d.groupby("delivery_cluster_id").size()
    multi = d[d.delivery_cluster_id.map(csz) > 1].sort_values(["delivery_cluster_id", "t"])
    span = multi.groupby("delivery_cluster_id").t.agg(lambda s: (s.max() - s.min()).total_seconds() / 60)
    cl = pd.DataFrame({"n": csz})
    cl["shape"] = cl.index.str.replace(r"\d+", "#", regex=True)
    fig, ax = plt.subplots(1, 3, figsize=(9.6, 2.9))
    vc = csz.value_counts().sort_index()
    b = ax[0].bar(vc.index.astype(str), vc.values, color=PS.BLUE, width=0.62)
    for r, v in zip(b, vc.values):
        ax[0].text(r.get_x() + r.get_width() / 2, v, f"{v:,}", ha="center", va="bottom", fontsize=6.5, color=PS.INK2)
    ax[0].set_title("Tarjetas por cluster"); ax[0].set_xlabel("tarjetas"); ax[0].set_ylim(0, vc.max() * 1.15); ax[0].grid(False)
    ax[1].hist(span, bins=28, color=PS.AQUA, edgecolor=PS.SURFACE)
    ax[1].axvline(45, color=PS.ORANGE, lw=1.4)
    ax[1].text(2, ax[1].get_ylim()[1] * 0.93, "línea naranja = ventana de 45 min", ha="left", fontsize=6.5, color=PS.ORANGE)
    ax[1].set_title("Amplitud de llegada del cluster"); ax[1].set_xlabel("minutos entre 1.ª y última tarjeta")
    ct = pd.crosstab(cl["shape"], cl["n"])
    ct.columns = [f"{c} tarj." for c in ct.columns]
    ct.plot(kind="barh", stacked=True, ax=ax[2], color=[PS.BLUE, PS.AQUA, PS.YELLOW, PS.MAGENTA][:ct.shape[1]], edgecolor=PS.SURFACE, width=0.6, legend=True)
    ax[2].legend(fontsize=6, ncol=2, loc="lower right"); ax[2].set_title("Forma del id vs tamaño"); ax[2].set_ylabel(""); ax[2].grid(False)
    return _save(fig, name)


def eda_catalog(cat: pd.DataFrame, name="eda_catalogo_coste_eta.png"):
    carriers = list(dict.fromkeys(cat.carrier))
    mk = {"URBANA": "o", "SUBURBANA": "s", "RURAL": "^", "REMOTA": "D"}
    fig, ax = plt.subplots(figsize=(5.8, 3.3))
    for j, c in enumerate(carriers):
        g = cat[cat.carrier == c]
        ax.plot(g.ETA_min, g.precio_1_tarjeta, color=PS.CAT[j], lw=0.8, alpha=0.5)
        for _, r in g.iterrows():
            ax.scatter(r.ETA_min, r.precio_1_tarjeta, marker=mk[r.zona], s=34, color=PS.CAT[j], edgecolor=PS.SURFACE, linewidth=0.8, zorder=3)
    h1 = [Line2D([], [], marker="o", ls="", color=PS.CAT[j], label=c.replace("_", " ").title(), markersize=5) for j, c in enumerate(carriers)]
    h2 = [Line2D([], [], marker=m, ls="", color=PS.MUTED, label=z.title(), markersize=5) for z, m in mk.items()]
    l1 = ax.legend(handles=h1, title="carrier", loc="upper left", fontsize=6.3, title_fontsize=6.8)
    ax.add_artist(l1); ax.legend(handles=h2, title="zona", loc="upper right", fontsize=6.3, title_fontsize=6.8)
    ax.set_xlabel("ETA (min) = pickup + trayecto de ida"); ax.set_ylabel("precio de 1 tarjeta (céntimos)")
    ax.set_title("Frontera coste–tiempo por carrier y zona (catálogo 5 k)")
    return _save(fig, name)


def baseline_diag(bm_reports: pd.DataFrame, name="baseline_diagnostico.png"):
    """bm_reports: filas por escenario con UNRESOLVED, retencion, lote medio (starter)."""
    fig, ax = plt.subplots(1, 3, figsize=(8.6, 2.6))
    for a, col, ttl in zip(ax, ["UNRESOLVED", "infracciones_retencion", "lote_medio"],
                           ["UNRESOLVED (gate = 0)", "Infracciones de retención (gate = 0)", "Tarjetas por lote"]):
        b = a.bar(bm_reports.escenario, bm_reports[col], color=PS.ORANGE, width=0.5)
        for r, v in zip(b, bm_reports[col]):
            a.text(r.get_x() + r.get_width() / 2, v, f"{v:g}", ha="center", va="bottom", fontsize=7, color=PS.INK2)
        a.set_title(ttl); a.set_ylim(0, max(bm_reports[col]) * 1.2 + 0.01); a.grid(False); a.tick_params(axis="x", labelsize=7)
    return _save(fig, name)


# ------------------------------------------------------------------------------------------------ policy
def carrier_choice(tabc: pd.DataFrame, name="policy_carrier_elegido_vs_wtime.png"):
    names = sorted(set(tabc.values.ravel()))
    idx = {n: i for i, n in enumerate(names)}
    cmap = PS.mpl.colors.ListedColormap(PS.CAT[:len(names)])
    fig, ax = plt.subplots(figsize=(7.4, 2.4))
    ax.imshow(np.vectorize(idx.get)(tabc.values), aspect="auto", cmap=cmap, vmin=-0.5, vmax=len(names) - 0.5)
    for i in range(tabc.shape[0]):
        for j in range(tabc.shape[1]):
            ax.text(j, i, tabc.iloc[i, j].split("_")[0][:4], ha="center", va="center", fontsize=6, color="white", fontweight="bold")
    ax.set_xticks(range(tabc.shape[1])); ax.set_xticklabels([c.replace("w=", "") for c in tabc.columns]); ax.set_yticks(range(tabc.shape[0]))
    ax.set_yticklabels(tabc.index); ax.set_xlabel("valor del tiempo w_time (céntimos por minuto y tarjeta)"); ax.grid(False)
    ax.set_title("Carrier elegido por J según el valor del tiempo")
    ax.legend(handles=[Patch(color=PS.CAT[i], label=n.replace("_", " ").title()) for n, i in idx.items()], ncol=len(names), loc="upper center",
              bbox_to_anchor=(0.5, -0.32), fontsize=6.3)
    return _save(fig, name)


def cluster_learning(tt: pd.DataFrame, name="policy_aprendizaje_clusters.png"):
    fig, ax = plt.subplots(figsize=(5.6, 2.7))
    ax.axhspan(0.5, 1.02, color="#eef4fc", zorder=0)
    ax.plot(tt.h, tt.P_E, color=PS.BLUE, label="forma CLU-E… (multi)")
    ax.plot(tt.h, tt.P_S, color=PS.ORANGE, label="forma CLU-S-… (singleton)")
    first = tt[tt.P_E >= 0.5].h.iloc[0]
    ax.annotate(f"cruza 0,5 a las {first:.1f} h", (first, 0.5), xytext=(first + 6, 0.32), fontsize=6.5, color=PS.INK2,
                arrowprops=dict(arrowstyle="-", color=PS.MUTED, lw=0.7))
    ax.axhline(0.5, color=PS.MUTED, lw=0.7, ls="--"); ax.set_xlim(0, 48); ax.set_ylim(0, 1.02)
    ax.set_xlabel("horas simuladas desde el inicio"); ax.set_ylabel("P(cluster multi | forma del id)")
    ax.set_title("La política aprende qué ids son clusters multi-tarjeta"); ax.legend(loc="center right")
    return _save(fig, name)


ABL_SHORT = {
    "full": "completo", "sin_retencion (hold_on=0)": "sin retención", "sin_despacho_al_llegar (solo ticks)": "solo en ticks",
    "hungarian_por_tick (assign=1)": "Hungarian puro", "sin_riesgo_de_fallo (w_fail=0)": "sin riesgo de fallo",
    "sin_valor_del_tiempo (w_time=0)": "sin valor del tiempo", "sin_prioridad_VIP (w_vip=1, vip_fail_extra=0)": "sin prioridad VIP",
    "sin_coste_sombra_flota (w_unit=0)": "sin coste sombra flota", "sin_liberar_cluster_completo": "sin liberar cluster completo",
    "sin_retener_segundo_miembro": "sin retener 2.º miembro",
}


def ablation(ab: pd.DataFrame, name="ablacion_componentes.png"):
    a = ab.copy()
    a["v"] = a.variante.map(lambda s: ABL_SHORT.get(s, s))
    base = a.loc[a.v == "completo", "J"].iloc[0]
    a["dJ"] = a.J - base
    a = a[a.v != "completo"].sort_values("dJ")
    fig, ax = plt.subplots(1, 2, figsize=(9.0, 3.0), gridspec_kw={"width_ratios": [1.2, 1]})
    cols = [PS.ORANGE if x > 0.02 else PS.AQUA for x in a.dJ]
    b = ax[0].barh(a.v, a.dJ, color=cols, height=0.62)
    for r, v in zip(b, a.dJ):
        ax[0].text(v + (0.004 if v >= 0 else -0.004), r.get_y() + r.get_height() / 2, f"{v:+.3f}", va="center", ha="left" if v >= 0 else "right", fontsize=6.5, color=PS.INK2)
    ax[0].axvline(0, color=PS.INK2, lw=0.7); ax[0].set_title("Δ J al quitar el componente (↑ = peor)"); ax[0].grid(axis="y", visible=False)
    ax[0].set_xlim(a.dJ.min() - 0.05, a.dJ.max() + 0.07)
    c = ab.assign(v=ab.variante.map(lambda s: ABL_SHORT.get(s, s))).set_index("v").loc[a.v]
    b2 = ax[1].barh(c.index, c.cpu_neta_5k_s, color=PS.VIOLET, height=0.62)
    for r, v in zip(b2, c.cpu_neta_5k_s):
        ax[1].text(v + 0.02, r.get_y() + r.get_height() / 2, f"{v:.2f}", va="center", fontsize=6.5, color=PS.INK2)
    ax[1].set_yticklabels([]); ax[1].set_title("CPU neta en 5 k (s, mediana de 3)"); ax[1].grid(axis="y", visible=False); ax[1].set_xlim(0, c.cpu_neta_5k_s.max() * 1.18)
    return _save(fig, name)


# ------------------------------------------------------------------------------------------------ optimizadores
def opt_convergence(tr: pd.DataFrame, order, name="opt_convergencia.png"):
    fig, ax = plt.subplots(1, 2, figsize=(9.2, 3.0), sharey=True)
    xs_end, ys_end, lab = [], [], []
    for o in order:
        d = tr[tr.optimizer == o].sort_values("n")
        ax[0].step(d.n + 1, d.best, where="post", color=PS.color(o), lw=1.5)
        i = d.value.idxmin()
        ax[0].scatter([d.loc[i, "n"] + 1], [d.loc[i, "value"]], color=PS.color(o), s=18, zorder=3, edgecolor=PS.SURFACE)
        cap = d.trial_s.median() * 3           # un ensayo atravesado por una suspension de la laptop se recorta a 3x la mediana
        ax[1].step(d.trial_s.clip(upper=cap).cumsum() / 60, d.best, where="post", color=PS.color(o), lw=1.5, label=o)
        xs_end.append(d.n.max() + 1); ys_end.append(d.best.iloc[-1]); lab.append(o)
    PS.repel(ax[0], xs_end, ys_end, lab, fontsize=6.5, offset=(5, 0))
    ax[0].set_xlabel("evaluaciones"); ax[0].set_ylabel("mejor J hasta ahora (↓ mejor)"); ax[0].set_title("Por evaluaciones (comparable)"); ax[0].set_xlim(0, 70)
    ax[1].set_xlabel("minutos de cómputo (suma de tiempos por ensayo; suspensiones recortadas)"); ax[1].set_title("Por tiempo de cómputo")
    ax[1].legend(ncol=5, loc="upper center", bbox_to_anchor=(0.5, -0.2), fontsize=6.3)
    return _save(fig, name)


def opt_frontier(tr: pd.DataFrame, order, name="opt_frontera_y_distribucion.png"):
    fig, ax = plt.subplots(1, 2, figsize=(9.4, 3.3), gridspec_kw={"width_ratios": [1.15, 1]})
    wcol = "p_w_time" if "p_w_time" in tr else None
    if wcol:
        sc = ax[0].scatter(tr.cost_ratio, tr.lead_ratio, c=np.log10(tr[wcol].clip(lower=1e-3)), cmap=PS.SEQ, s=13, edgecolor="#ffffff55", linewidth=0.3)
        cb = fig.colorbar(sc, ax=ax[0], fraction=0.04, pad=0.02); cb.set_label("log10(w_time)", fontsize=6.5); cb.ax.tick_params(labelsize=6)
    else:
        ax[0].scatter(tr.cost_ratio, tr.lead_ratio, s=13, color=PS.BLUE)
    for o in order:
        d = tr[tr.optimizer == o]; b = d.loc[d.value.idxmin()]
        ax[0].scatter([b.cost_ratio], [b.lead_ratio], marker="*", s=95, color=PS.color(o), edgecolor=PS.INK, linewidth=0.5, zorder=4, label=f"mejor {o}")
    ax[0].scatter([1], [1], marker="s", s=44, color=PS.INK, zorder=4, label="ref. más barata")
    ax[0].set_xlabel("coste / coste de la referencia barata"); ax[0].set_ylabel("lead medio / lead de la referencia")
    ax[0].set_title("Frontera coste–tiempo (todos los ensayos)"); ax[0].legend(ncol=2, fontsize=6, loc="upper right")
    rng = np.random.default_rng(3)
    for i, o in enumerate(order):
        v = tr[tr.optimizer == o].value.values
        ax[1].scatter(i + rng.uniform(-0.17, 0.17, len(v)), v, s=8, color=PS.color(o), alpha=0.65, edgecolor="none")
        ax[1].hlines(np.median(v), i - 0.3, i + 0.3, color=PS.INK, lw=1.4)
        ax[1].text(i + 0.33, np.median(v), f"{np.median(v):.2f}", ha="left", va="center", fontsize=6.3, color=PS.INK2)
    ax[1].set_xticks(range(len(order))); ax[1].set_xticklabels(order); ax[1].set_ylabel("J por ensayo (mediana en negro)")
    ax[1].set_title("Calidad media de lo que propone cada método"); ax[1].set_ylim(top=min(tr.value.max(), 4.4))
    return _save(fig, name)


def opt_sensitivity(sens: pd.Series, name="opt_sensibilidad.png"):
    fig, ax = plt.subplots(figsize=(5.2, 2.7))
    cols = [PS.AQUA if v < 0 else PS.ORANGE for v in sens.values]
    b = ax.barh(sens.index, sens.values, color=cols, height=0.62)
    for r, v in zip(b, sens.values):
        ax.text(v + (0.012 if v >= 0 else -0.012), r.get_y() + r.get_height() / 2, f"{v:+.2f}", va="center", ha="left" if v >= 0 else "right", fontsize=6.5, color=PS.INK2)
    ax.axvline(0, color=PS.INK2, lw=0.7); ax.grid(axis="y", visible=False)
    ax.set_xlim(min(sens.min() - 0.12, -0.1), max(sens.max() + 0.12, 0.1))
    ax.set_title("Spearman(parámetro, J): negativo = subirlo baja J")
    return _save(fig, name)


# ------------------------------------------------------------------------------------------------ robustez
def gates(M: pd.DataFrame, infeasible: set, name="robustez_gates.png"):
    scen = list(M.index)
    fig, ax = plt.subplots(figsize=(5.6, 0.19 * len(scen) + 1.5))
    ax.imshow(M.values.astype(float), aspect="auto", cmap=PS.GOOD_BAD, vmin=0, vmax=1)
    for i, s in enumerate(scen):
        for j, c in enumerate(M.columns):
            ok = bool(M.loc[s, c]); inf = s in infeasible
            ax.text(j, i, "✓" if ok else ("∅" if inf else "✗"), ha="center", va="center", fontsize=6.2, color=PS.INK2 if ok else PS.INK)
    splits = [s.split("_")[0] for s in scen]
    for i in range(1, len(scen)):
        if splits[i] != splits[i - 1]:
            ax.axhline(i - 0.5, color=PS.INK2, lw=0.9)
    ax.set_xticks(range(M.shape[1])); ax.set_xticklabels(M.columns, rotation=25, ha="right", fontsize=6.5)
    ax.set_yticks(range(len(scen))); ax.set_yticklabels(scen, fontsize=5.8); ax.grid(False)
    ax.set_title("Gates por escenario (✓ cumple · ✗ viola · ∅ infactible por construcción)", fontsize=8)
    return _save(fig, name)


def dumbbells(df: pd.DataFrame, names, cand: str, title: str, name: str, refs=("ref_price",)):
    """Por escenario: el candidato respecto al starter (=100 %). Una fila por escenario, un panel por metrica."""
    s = df[df.candidate == "starter"].set_index("scenario").loc[names]
    c = df[df.candidate == cand].set_index("scenario").loc[names]
    r = {x: df[df.candidate == x].set_index("scenario").loc[names] for x in refs}
    fig, ax = plt.subplots(1, 4, figsize=(10.2, 0.2 * len(names) + 1.9), sharey=True)
    y = np.arange(len(names))
    panels = [("cost_total", "Coste (starter = 100 %)", 100.0, False), ("lead_mean", "Lead medio (starter = 100 %)", 100.0, False),
              ("lead_p95", "p95 (starter = 100 %)", 100.0, False), ("rcp", "RCP (Δ puntos vs starter)", None, True)]
    for a, (m, ttl, base, higher) in zip(ax, panels):
        if base:
            vc, vs = 100 * c[m] / s[m], np.full(len(names), 100.0)
            vr = {k: 100 * v[m] / s[m] for k, v in r.items()}
        else:
            vc, vs = c[m] - s[m], np.zeros(len(names))
            vr = {k: v[m] - s[m] for k, v in r.items()}
        a.hlines(y, vs, vc, color="#c9d8ee", lw=2.2, zorder=1)
        a.scatter(vc, y, color=PS.BLUE, s=20, zorder=3, label="final")
        for k, v in vr.items():
            a.scatter(v, y, facecolor="none", edgecolor=PS.color(k), s=18, linewidth=1.1, zorder=2, label=k)
        a.axvline(vs[0], color=PS.ORANGE, lw=1.3, zorder=0)
        mean_txt = f"{vc.mean():.1f} %" if base else f"{vc.mean():+.3f}"
        a.set_title(f"{ttl}\nmedia del candidato: {mean_txt}", fontsize=7.6, linespacing=1.5); a.grid(axis="y", visible=False)
    ax[0].set_yticks(y); ax[0].set_yticklabels([short(n) for n in names], fontsize=6.3); ax[0].invert_yaxis()
    h = [Line2D([], [], marker="o", ls="", color=PS.BLUE, label="candidato final", markersize=5), Line2D([], [], color=PS.ORANGE, label="starter", lw=1.3)]
    h += [Line2D([], [], marker="o", ls="", markerfacecolor="none", markeredgecolor=PS.color(k), label=k, markersize=5) for k in refs]
    fig.legend(handles=h, loc="upper right", ncol=4, fontsize=6.5, bbox_to_anchor=(1.0, 1.06))
    fig.suptitle(title, x=0.01, ha="left", fontsize=9.5)
    return _save(fig, name)


def improvement_heatmap(df: pd.DataFrame, names, cand: str, name: str, title: str):
    s = df[df.candidate == "starter"].set_index("scenario").loc[names]
    c = df[df.candidate == cand].set_index("scenario").loc[names]
    M = pd.DataFrame({"coste": 100 * (1 - c.cost_total / s.cost_total), "lead medio": 100 * (1 - c.lead_mean / s.lead_mean),
                      "p95": 100 * (1 - c.lead_p95 / s.lead_p95), "RCP (×100 Δ)": 100 * (c.rcp - s.rcp)})
    fig, ax = plt.subplots(figsize=(4.6, 0.22 * len(names) + 1.4))
    lim = max(10, np.nanmax(np.abs(M.values)))
    ax.imshow(M.values, aspect="auto", cmap=PS.DIV, vmin=-lim, vmax=lim)
    for i in range(M.shape[0]):
        for j in range(M.shape[1]):
            ax.text(j, i, f"{M.values[i, j]:.0f}", ha="center", va="center", fontsize=6, color=PS.INK)
    ax.set_xticks(range(4)); ax.set_xticklabels(M.columns, fontsize=6.8); ax.set_yticks(range(len(names))); ax.set_yticklabels([short(n) for n in names], fontsize=6.3)
    ax.xaxis.tick_top(); ax.grid(False)
    ax.set_title(title + "\n% de mejora vs starter (azul = mejor)", fontsize=8, pad=22)
    return _save(fig, name)


def cohort(P: pd.DataFrame, metrics, name="robustez_puntos_cohorte.png", top=8):
    t = P.head(top)
    fig, ax = plt.subplots(figsize=(7.2, 3.0))
    left = np.zeros(len(t))
    labels = {"cost_total": "coste", "lead_mean": "lead medio", "lead_p95": "p95", "rcp": "RCP"}
    for (m, _), col in zip(metrics, [PS.BLUE, PS.ORANGE, PS.AQUA, PS.YELLOW]):
        ax.barh(t.index, t[m], left=left, color=col, label=labels.get(m, m), height=0.62, edgecolor=PS.SURFACE, linewidth=1.5)
        for i, v in enumerate(t[m].values):
            if v > 2.2:
                ax.text(left[i] + v / 2, i, f"{v:.1f}", ha="center", va="center", fontsize=6.2, color="white" if col != PS.YELLOW else PS.INK)
        left += t[m].values
    for i, v in enumerate(left):
        ax.text(v + 0.5, i, f"{v:.1f}", va="center", fontsize=6.8, color=PS.INK, fontweight="bold")
    ax.invert_yaxis(); ax.set_xlim(0, 88); ax.set_xlabel("puntos de las 4 métricas de negocio (máx 80)"); ax.grid(axis="y", visible=False)
    ax.set_title("Cohorte simulada de estrategias propias (PROXY, no el cálculo del evaluador)")
    ax.legend(ncol=4, loc="upper center", bbox_to_anchor=(0.5, -0.17), fontsize=6.5)
    return _save(fig, name)


def metric_bars(rows: pd.DataFrame, name="final_vs_starter_publicos.png"):
    """rows: filas de final_vs_baseline.csv. Barras agrupadas (starter vs final) normalizadas a starter = 100 %, por escenario publico."""
    fig, axs = plt.subplots(1, 2, figsize=(8.6, 2.9), sharey=True)
    metrics = [("cost_total", "coste"), ("lead_mean", "lead medio"), ("lead_p95", "p95"), ("cpu_net_s", "CPU neta"), ("rss_mb", "RAM")]
    for ax, scen in zip(axs, ["public_5k", "public_150k"]):
        s = rows[(rows.policy == "starter") & (rows.scenario == scen)].iloc[0]
        f = rows[(rows.policy == "final") & (rows.scenario == scen)].iloc[0]
        vals = [100 * f[m] / s[m] for m, _ in metrics]
        b = ax.bar([l for _, l in metrics], vals, color=[PS.BLUE if v <= 100 else PS.ORANGE for v in vals], width=0.6)
        ax.axhline(100, color=PS.ORANGE, lw=1.2)
        for r, v in zip(b, vals):
            ax.text(r.get_x() + r.get_width() / 2, v + 1.5, f"{v:.0f}%", ha="center", fontsize=6.8, color=PS.INK2)
        ax.set_title(f"{scen.replace('public_', '')}: final (starter = 100 %)"); ax.set_ylim(0, 125); ax.grid(axis="x", visible=False)
        ax.tick_params(axis="x", labelsize=6.8)
    return _save(fig, name)


# ------------------------------------------------------------------------------------------------ 2.a corrida
def speed_rules(df: pd.DataFrame, scen: list, name="speed_capacity_reglas.png"):
    b = df.set_index("variante")
    names = [v for v in b.index if v != "base"]
    d = {v: {"coste": 100 * np.mean([b.loc[v, f"cost_{s}"] / b.loc["base", f"cost_{s}"] - 1 for s in scen]),
             "lead": 100 * np.mean([b.loc[v, f"lead_{s}"] / b.loc["base", f"lead_{s}"] - 1 for s in scen]),
             "p95": 100 * np.mean([b.loc[v, f"p95_{s}"] / b.loc["base", f"p95_{s}"] - 1 for s in scen])} for v in names}
    t = pd.DataFrame(d).T
    fig, ax = plt.subplots(1, 2, figsize=(8.8, 2.9), gridspec_kw={"width_ratios": [1.6, 1]})
    x = np.arange(len(t)); w = 0.26
    for i, (c, col) in enumerate(zip(["coste", "lead", "p95"], [PS.ORANGE, PS.BLUE, PS.AQUA])):
        bars = ax[0].bar(x + (i - 1) * w, t[c], width=w, color=col, label=c)
        for r, v in zip(bars, t[c]):
            if abs(v) > 0.05:
                ax[0].text(r.get_x() + r.get_width() / 2, v + (0.1 if v >= 0 else -0.1), f"{v:+.1f}", ha="center", va="bottom" if v >= 0 else "top", fontsize=5.8, color=PS.INK2)
    ax[0].axhline(0, color=PS.INK2, lw=0.7); ax[0].set_xticks(x); ax[0].set_xticklabels([n.replace("speed_k", "κ=").replace("cap_s", "cap≥") for n in t.index], fontsize=7)
    ax[0].set_ylabel("% vs sin mejoras de velocidad/capacidad"); ax[0].set_title("SPEED_SHIFT / EXPANDED_CAPACITY: efecto medio por regla"); ax[0].legend(ncol=3, fontsize=6.3)
    ax[1].bar(range(len(names)), [b.loc[v, "speed_total"] + b.loc[v, "cap_total"] for v in names], color=PS.VIOLET, width=0.6)
    ax[1].set_xticks(range(len(names))); ax[1].set_xticklabels([n.replace("speed_k", "κ=").replace("cap_s", "cap≥") for n in names], fontsize=7)
    ax[1].set_title("Mejoras compradas en 12 escenarios"); ax[1].grid(axis="x", visible=False)
    return _save(fig, name)


def ceilings(t: pd.DataFrame, name="techos_lotes_p95.png"):
    fig, ax = plt.subplots(1, 2, figsize=(8.8, 2.9))
    y = np.arange(len(t))
    ax[0].barh(y, t.lote_vs_cota_sup_pct, color=[PS.AQUA if v <= 0.05 else PS.ORANGE for v in t.lote_vs_cota_sup_pct], height=0.62)
    ax[0].axvline(0, color=PS.INK2, lw=0.8); ax[0].set_yticks(y); ax[0].set_yticklabels([short(s) for s in t.scenario], fontsize=6)
    ax[0].invert_yaxis(); ax[0].set_xlabel("lotes del candidato vs cota superior (clusters + reintentos), %"); ax[0].set_title("Agrupación: en el techo (≤ 0 = por debajo de la cota)")
    ax[0].grid(axis="y", visible=False)
    ax[1].barh(y, t.p95_vs_eta_pct, color=[PS.AQUA if v <= 0.5 else PS.ORANGE for v in t.p95_vs_eta_pct], height=0.62)
    ax[1].axvline(0, color=PS.INK2, lw=0.8); ax[1].set_yticks(y); ax[1].set_yticklabels([]); ax[1].invert_yaxis()
    ax[1].set_xlabel("p95 del candidato vs p95 de «siempre el más rápido», %"); ax[1].set_title("p95: al nivel de la cota práctica (reintento ≈ 1 440 min)")
    ax[1].grid(axis="y", visible=False)
    return _save(fig, name)


def cpu_bars(dfs: dict, name="cpu_ram_estilo_evaluador.png"):
    """dfs: {escenario: DataFrame de cpu_eval_*.csv}. Barras CPU cruda y neta + RAM, por estrategia."""
    fig, ax = plt.subplots(1, 3, figsize=(9.6, 2.9))
    cols = {"noop": PS.MUTED, "starter": PS.ORANGE, "final": PS.BLUE}
    sc = list(dfs)
    x = np.arange(len(sc)); w = 0.26
    for a, (col, ttl) in zip(ax, [("cpu_s_mediana3", "CPU cruda (s, mediana de 3)"), ("cpu_neta_s", "CPU neta del piso (s)"), ("rss_mib_mediana3", "RAM pico (MiB)")]):
        for i, k in enumerate(["noop", "starter", "final"]):
            v = [dfs[s].set_index("estrategia").loc[k, col] for s in sc]
            bars = a.bar(x + (i - 1) * w, v, width=w, color=cols[k], label={"noop": "estrategia nula", "starter": "starter", "final": "final"}[k])
            for r, val in zip(bars, v):
                a.text(r.get_x() + r.get_width() / 2, val, f"{val:.1f}", ha="center", va="bottom", fontsize=5.8, color=PS.INK2)
        a.set_xticks(x); a.set_xticklabels([s.replace("public_", "") for s in sc]); a.set_title(ttl); a.grid(axis="x", visible=False)
    ax[0].legend(fontsize=6.3, loc="upper left")
    return _save(fig, name)


def selection_proxy(sel: pd.DataFrame, name="seleccion_proxy.png"):
    s = sel.sort_values("puntos_proxy", ascending=True)
    fig, ax = plt.subplots(figsize=(6.4, 0.26 * len(s) + 1.2))
    cols = [PS.BLUE if (e and c != "incumbente") else (PS.VIOLET if c == "incumbente" else PS.MUTED) for c, e in zip(s.candidato, s.elegible)]
    b = ax.barh(s.candidato, s.puntos_proxy, color=cols, height=0.62)
    for r, v, e in zip(b, s.puntos_proxy, s.elegible):
        ax.text(v + 0.2, r.get_y() + r.get_height() / 2, f"{v:.1f}" + ("" if e else "  (no elegible)"), va="center", fontsize=6.3, color=PS.INK2)
    ax.set_xlim(s.puntos_proxy.min() - 2, s.puntos_proxy.max() + 8); ax.grid(axis="y", visible=False)
    ax.set_xlabel("puntos proxy de cohorte, 4 métricas de negocio (máx 80)")
    ax.set_title("Selección 2.ª corrida: azul = elegible · violeta = incumbente · gris = no elegible")
    return _save(fig, name)
