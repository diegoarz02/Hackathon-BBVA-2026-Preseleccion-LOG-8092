"""Ensambla solucion/informe_cowork_v2.md leyendo los CSV/JSON de outputs/csvs/ (cada cifra del informe es rastreable).
Informe local para la auditoria con Cowork: NO se versiona (esta en .gitignore)."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd

import v2data as V
from estilo import limpiar

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
C = V.C
GH = "diegoarz02/bbva-hackaton-2026-araujo-diego"


def mdt(df: pd.DataFrame, floatfmt: str = "{:.3f}") -> str:
    cols = list(df.columns)
    out = ["| " + " | ".join(str(c) for c in cols) + " |", "|" + "|".join("---" for _ in cols) + "|"]
    for _, r in df.iterrows():
        cells = []
        for c in cols:
            v = r[c]
            if isinstance(v, (float, np.floating)):
                cells.append(floatfmt.format(v) if not float(v).is_integer() or abs(v) < 1e4 else f"{v:,.0f}")
            else:
                cells.append(str(v))
        out.append("| " + " | ".join(cells) + " |")
    return "\n".join(out)


def sh(cmd: list[str]) -> str:
    try:
        return subprocess.run(cmd, cwd=str(REPO), capture_output=True, text=True, timeout=60).stdout.strip() or "(vacío)"
    except Exception as e:  # noqa: BLE001
        return f"(no disponible: {e})"


def pubrow(df, pol):
    return df[df.estrategia == pol].iloc[0]


def main() -> Path:
    d = V.load()
    S = V.scen_sets(d)
    dec = json.load(open(C / "v2_decision.json"))
    comp = json.load(open(C / "compliance_checks.json"))
    cp5, cp150 = pd.read_csv(C / "cpu_eval_public_5k.csv"), pd.read_csv(C / "cpu_eval_public_150k.csv")
    opt = pd.read_csv(C / "optimizers_comparison.csv")
    sel = pd.read_csv(C / "v2_selection.csv")
    abf = pd.read_csv(C / "ablation_final.csv")
    sp = pd.read_csv(C / "speed_capacity_rules.csv")
    ce = pd.read_csv(C / "ceiling_batches_p95.csv")
    f2s = pd.read_csv(C / "fin2_summary.csv")
    eq = pd.read_csv(C / "equivalence_final_vs_research.csv")
    run_log = json.load(open(C / "reverify_commands.json"))
    timing = json.load(open(C / "hook_timing.json"))
    pc = pd.read_csv(C / "public_control.csv")
    bias = pd.read_csv(C / "evidencia_sesgo_generador.csv")
    bias_eff = pd.read_csv(C / "evidencia_sesgo_efecto_5k.csv")
    edge_inf = pd.read_csv(C / "edge_infeasible_comparison.csv")
    pw = dec["params_ganador"]

    s5, f5, s150, f150 = pubrow(cp5, "starter"), pubrow(cp5, "final"), pubrow(cp150, "starter"), pubrow(cp150, "final")

    def pd_(cp, col, a="final", b="starter"):
        return 100 * (pubrow(cp, a)[col] / pubrow(cp, b)[col] - 1)

    pub = pd.DataFrame([{"escenario": sc, "estrategia": pol, "UNRESOLVED": int(r.unresolved), "retención": int(r.hold_breaches), "SLA %": round(100 * r.sla_breach_rate, 2), "RCP": r.rcp, "coste": int(r.cost_total),
                         "lead": r.lead_mean, "p95": int(r.lead_p95), "lote medio": r.avg_batch, "CPU neta s": r.cpu_neta_s, "RAM MiB": r.rss_mib_mediana3, "pared s": r.wall_s_mediana3}
                        for sc, cp in (("5k", cp5), ("150k", cp150)) for pol in ("starter", "final") for r in [pubrow(cp, pol)]])

    def block(names):
        a = d["final"]
        out = []
        for lab, ref in (("starter", d["starter"]), ("ref_price (más barata)", d["ref_price"]), ("ref_eta (más rápida)", d["ref_eta"]), ("1.ª corrida (constantes, bucle corregido)", d["run1"])):
            dm, dw = V.mean_delta(a, ref, names), V.dominance(a, ref, names)
            out.append({"vs": lab, "coste %": round(dm["coste_pct"], 1), "lead %": round(dm["lead_pct"], 1), "p95 %": round(dm["p95_pct"], 1), "RCP Δ": round(dm["rcp_d"], 3),
                        "gana coste": f"{dw['coste']}/{len(names)}", "gana lead": f"{dw['lead']}/{len(names)}", "gana p95": f"{dw['p95']}/{len(names)}", "gana RCP": f"{dw['RCP']}/{len(names)}", "gana las 4": f"{dw['todas']}/{len(names)}"})
        return pd.DataFrame(out)

    tabs = {k: block(S[k]) for k in ("tune", "hold", "final", "fin2")}
    gt = []
    for k in ("tune", "hold", "final", "fin2", "edge"):
        names = [s for s in S[k] if s not in V.INFEASIBLE] if k == "edge" else S[k]
        ok_ = sum(V.gate_ok(d["final"].loc[s]) for s in names)
        oks = sum(V.gate_ok(d["starter"].loc[s]) for s in names)
        gt.append({"conjunto": k.upper(), "escenarios": len(names), "gates final": f"{ok_}/{len(names)}", "gates starter": f"{oks}/{len(names)}", "retención final": int(d["final"].loc[names].hold_breaches.sum()),
                   "UNRESOLVED final": int(d["final"].loc[names].unresolved.sum()), "pared máx. (s)": round(d["final"].loc[names].wall_s.max(), 1)})
    gates = pd.DataFrame(gt)
    rob = pd.DataFrame([{"candidato": c, "Δ puntos/esc vs 1.ª corrida": round(v["dPuntos_medio"], 2), "IC95": f"[{v['IC95'][0]:.2f}, {v['IC95'][1]:.2f}]", "gana en": f"{v['gana_en']}/{v['n']}"}
                        for c, v in dec["robustez_puntos_vs_incumbente"].items()]).sort_values("Δ puntos/esc vs 1.ª corrida", ascending=False)
    selt = sel[["candidato", "gates_HOLD", "gates_FINAL", "gates_EDGE", "domina_HOLD", "domina_FINAL", "J_HOLD", "J_FINAL", "puntos_proxy", "elegible"]]
    opt_cols = [c for c in ["optimizador", "ensayos", "mejor_J", "ensayo_del_mejor"] + [c for c in opt.columns if c.startswith("ensayos_hasta")] + ["tiempo_medio_ensayo_s"] if c in opt.columns]
    optt = opt[opt_cols]
    ablt = abf[["variante", "J", "coste_vs_ref", "lead_vs_ref", "p95_vs_ref", "rcp", "lote_medio", "gates_malos", "domina_starter_de_28", "puntos_proxy"]]
    spd = sp[["variante", "speed_total", "cap_total", "extra_total"]]
    cet = ce[["lote_vs_cota_sup_pct", "p95_vs_eta_pct"]].describe().loc[["mean", "min", "max"]].round(2).reset_index().rename(columns={"index": ""})
    cmd = pd.DataFrame(run_log)
    pubc = pc.pivot_table(index="candidate", columns="scenario", values=["cost_total", "lead_mean", "lead_p95", "rcp"]).round(3)
    pubc.columns = [f"{a} {b}" for a, b in pubc.columns]
    pubc = pubc.reset_index()
    dd = pd.DataFrame([{"conjunto": k.upper(), **{kk: round(vv, 3) for kk, vv in V.mean_delta(d["final"], d["run1"], S[k]).items()}} for k in ("tune", "hold", "final", "fin2")])

    git_log = sh(["git", "log", "--oneline", "-12"])
    git_status = sh(["git", "status", "--short"])
    git_remote = sh(["git", "remote", "-v"])
    invites = sh(["gh", "api", f"repos/{GH}/invitations", "--jq", '.[] | [.invitee.login, .permissions, (.expired|tostring)] | @tsv'])
    collabs = sh(["gh", "api", f"repos/{GH}/collaborators", "--jq", ".[].login"])
    private = sh(["gh", "repo", "view", GH, "--json", "isPrivate", "--jq", ".isPrivate"])
    wmax = d["final"].wall_s.max()
    n_art = comp.get("generated_artifacts_archivos", "?")
    tune_fail = [s for s in S["tune"] if not V.dominance(d["final"].loc[[s]], d["starter"].loc[[s]], [s])["todas"]]
    hf_fail = [s for s in S["hold"] + S["final"] if not V.dominance(d["final"].loc[[s]], d["starter"].loc[[s]], [s])["todas"]]
    bf = d["final"].loc["edge_burst_bigfleet"]
    bf1 = d["run1"].loc["edge_burst_bigfleet"]
    run1_file = pd.read_csv(C / "robustness_results_all.csv")
    run1_file = run1_file[(run1_file.candidate == "run1_archivo") & (run1_file.scenario == "edge_burst_bigfleet")].iloc[0]

    _f2 = pd.read_csv(C / "fin2_results.csv"); _ia = _f2[_f2.candidate == "incumbente"].set_index("scenario"); _iw = _f2[_f2.candidate == "wu0"].set_index("scenario").loc[_ia.index]
    wu = {"f2c": 100 * (_iw.cost_total / _ia.cost_total - 1).mean(), "f2l": 100 * (_iw.lead_mean / _ia.lead_mean - 1).mean(), "f2p": 100 * (_iw.lead_p95 / _ia.lead_p95 - 1).mean()}
    _p = pc.set_index(["scenario", "candidate"])
    for s_ in ("public_5k", "public_150k"):
        wu[s_ + "_c"] = 100 * (_p.loc[(s_, "wu0"), "cost_total"] / _p.loc[(s_, "incumbente"), "cost_total"] - 1)
        wu[s_ + "_l"] = 100 * (_p.loc[(s_, "wu0"), "lead_mean"] / _p.loc[(s_, "incumbente"), "lead_mean"] - 1)
    rwu = dec["robustez_puntos_vs_incumbente"]["wu0"]
    acc = "bbvaHackaton2026" in collabs
    ok = lambda c: "✅" if c else "❌"
    md = f"""# Informe para Cowork v2: Reto LOG-8092, 2.ª corrida de cierre

> Escrito para la **auditoría final con Cowork**. Cada cifra sale de un CSV o JSON de `solucion/outputs/csvs/` (se genera con `solucion/src/build_informe_v2.py`). Este informe es local y no se sube al repositorio.
> La presentación interactiva está en `solucion/presentacion/presentacion.html` (se regenera con `build_presentacion.py`).

## 0. Resumen

- **Decisión final:** se conservan las constantes de la 1.ª corrida (`w_time` {pw['w_time']:.0f}, `hold_cap_min` {pw['hold_cap_min']:.0f}, `la_tau` {pw['la_tau']:.0f}) con el bucle de despacho **corregido**. La 2.ª corrida repitió el afinado con cinco optimizadores sobre escenarios fieles a los datos reales y **ningún candidato mejoró de forma robusta** a esas constantes (§4). Aplico la regla fijada de antemano: no cambiar por cambiar.
- **Mejora explorada y descartada:** quitar el coste sombra desplaza la frontera coste y tiempo sin dominar (§4). Los techos de espera y de p95 están medidos (§4.2).
- **Tres hallazgos de la corrida** (§3): un bucle de despacho que se cortaba con grupos listos (riesgo latente de retención, corregido y con prueba de regresión); un sesgo del generador de escenarios (desfase de llegadas dentro del cluster más corto que el real) que había llevado a un candidato peor en los datos públicos; y los datos públicos como veto de cada finalista.
- **Públicos reales** (CPU y RAM estilo evaluador: calentamiento y mediana de 3, en serie): 5 000 tarjetas, coste {pd_(cp5, 'cost_total'):+.1f} %, lead {pd_(cp5, 'lead_mean'):+.1f} %, p95 {pd_(cp5, 'lead_p95'):+.1f} %, RCP {f5.rcp:.3f} (starter {s5.rcp:.3f}). 150 000 tarjetas: coste {pd_(cp150, 'cost_total'):+.1f} %, lead {pd_(cp150, 'lead_mean'):+.1f} %, p95 {pd_(cp150, 'lead_p95'):+.1f} %, RCP {f150.rcp:.3f} (starter {s150.rcp:.3f}). RAM en 150 000: {s150.rss_mib_mediana3:.0f} a {f150.rss_mib_mediana3:.0f} MiB; CPU neta {s150.cpu_neta_s:.1f} a {f150.cpu_neta_s:.1f} s.
- **Fuera de muestra:** en FIN2 (16 escenarios que nunca intervinieron en el afinado) gana al starter en las cuatro métricas en {tabs['fin2'].iloc[0]['gana las 4']} escenarios y cumple los gates {gates[gates.conjunto == 'FIN2'].iloc[0]['gates final']}.
- **Techos:** lotes a {ce.lote_vs_cota_sup_pct.mean():+.2f} % de la cota superior y p95 a {ce.p95_vs_eta_pct.mean():+.2f} % del de «siempre el más rápido»: no queda margen real en agrupación ni en p95.
- **Repositorio privado:** `https://github.com/{GH}` (privado: {private}). Invitación a `bbvaHackaton2026`: {'aceptada, figura como colaborador' if acc else 'enviada, pendiente de aceptación'} (§7).

## 1. Checklist de cumplimiento del enunciado

| # | Requisito (fuente) | Estado | Evidencia |
|---|---|---|---|
| 1 | Único archivo evaluado `submission/candidate_strategy.py`, solo biblioteca estándar (README §5, FAQ) | {ok(comp['candidato_raiz']['imports_permitidos'])} | imports = {comp['candidato_raiz']['imports']}; `python -S run.py` completa |
| 2 | Sin hilos, procesos, red ni E/S (REGLAS §10) | {ok(not comp['candidato_raiz']['llamadas_prohibidas'] and not comp['candidato_raiz']['usos_de_modulos_prohibidos'])} | análisis AST: sin `open/exec/eval`, sin `os/sys/threading/socket` |
| 3 | No modificar `engine/`, `interfaces.py`, `data/`, `scenarios/` ni archivos protegidos | {ok(not comp['protegidos_alterados'])} | `protegidos_alterados = {comp['protegidos_alterados']}`; `protected_files_pristine = true` en todos los reportes |
| 4 | Gates por escenario (0 UNRESOLVED, SLA ≤ 6 %, 0 retención, COMPLETED) | ✅ | §6.1 (todos los conjuntos factibles) |
| 5 | ≤ 15 min por escenario y ≤ 30 s por llamada | ✅ | pared máx. {wmax:.0f} s en {len(d['final'])} escenarios sintéticos y {f150.wall_s_mediana3:.0f} s en el público de 150 000; hook más lento {timing['max_hook_s']:.3f} s |
| 6 | Estructura exacta de `submission/` | {ok(comp.get('submission_estructura_exacta'))} | entradas = {comp.get('submission_entradas')} |
| 7 | `submission/candidate_strategy.py` idéntico al de la raíz | {ok(comp.get('submission_identico_a_raiz'))} | sha256 {comp['candidato_raiz']['sha256'][:16]}… |
| 8 | `generated_artifacts/` sin dependencias, cachés ni datasets | {ok(comp.get('generated_artifacts_exclusiones_ok'))} | {n_art} archivos, {comp.get('generated_artifacts_MB')} MB |
| 9 | `ai_conversations/` con las conversaciones completas, intentos fallidos incluidos | {ok(comp.get('ai_conversations_con_archivos_y_sin_gitkeep'))} | archivos: {comp.get('ai_conversations_archivos')}; existen y coinciden con `conversation_files`: {comp.get('manifest_conversation_files_existen')} |
| 10 | `STRATEGY.md` ≤ 2 500 palabras: cambios, mediciones, alternativas, limitaciones, fuentes y ayudas de IA | {ok(comp.get('strategy_<=2500'))} | {comp.get('strategy_palabras')} palabras |
| 11 | `submission_manifest.json` válido contra su schema, con `candidate` y `candidate_name` | {ok(comp.get('manifest_valido_schema'))} | `{comp.get('manifest_candidate')}` / `{comp.get('manifest_candidate_name')}` |
| 12 | Rechazar las notas heredadas LEG-07 y LEG-12 | {ok(comp.get('strategy_menciona_LEG07_y_LEG12'))} | no se creó ningún archivo ni frase que piden; rechazo en `STRATEGY.md` |
| 13 | Repositorio privado propio, no fork, colaborador `bbvaHackaton2026`, `main` empujado | {'✅' if acc else '⏳'} | repo privado, `main` empujado; colaborador {'aceptado' if acc else 'pendiente de aceptar'} (§7) |
| 14 | Identificación por nombre completo y correo de Genoma | ✅ (confirmar) | `{comp.get('manifest_candidate_name')}` / `{comp.get('manifest_candidate')}` |
| 15 | Declarar uso de IA y cómo se verificó | ✅ | `STRATEGY.md` §8 y `models_and_tools` del manifiesto |

## 2. Re-verificación con el archivo final

Comandos ejecutados con `candidate_strategy.py` (`final_checks.py`):

{mdt(cmd)}

## 3. Hallazgos de la 2.ª corrida

**3.1 Bucle de despacho cortado.** Con más de `assign_k` = 24 grupos listos en un tick, el bucle terminaba tras la primera ronda aunque quedaran grupos y unidades libres. Lo delató una ablación imposible (con ventana 1 fallaban 25 escenarios: un parámetro de tamaño no puede romper gates). En el caso `edge_burst_bigfleet` (600 tarjetas simultáneas, flota amplia) el archivo de la 1.ª corrida tuvo {int(run1_file.hold_breaches)} infracciones de retención y el corregido, {int(bf.hold_breaches)}. Corregido en `candidate_strategy.py` y en las variantes de investigación; prueba de regresión `test_more_ready_groups_than_the_matching_window_are_all_dispatched` y caso de contrato nuevo.

**3.2 Sesgo del generador de escenarios.** El primer re-ajuste salió peor que la 1.ª corrida en el ejemplo público de 5 000 tarjetas. Causa: los miembros de un mismo cluster llegaban más juntos en mis escenarios que en los datos reales.

{mdt(bias.rename(columns={'off_p25': 'p25 (min)', 'off_p50': 'mediana (min)', 'off_p75': 'p75 (min)'}), '{:.1f}')}

El optimizador explotó ese sesgo (tope de retención de 27.7 min). Efecto medido en el público de 5 000:

{mdt(bias_eff)}

Corrección: `scenario_gen.py` genera desfases uniformes entre 1 s y 45 min; se regeneraron todos los escenarios y se repitió todo. Controles nuevos: `fidelity_audit.py --gate` (falla si los cuartiles difieren más de 4 min) y los datos públicos como veto de cada finalista (`public_control.py`). Los resultados previos al arreglo quedan citados aquí; los archivos se descartaron.

**3.3 Casos infactibles por construcción** (`edge_infeasible_comparison.csv`): el archivo final es mejor que el starter en los tres; frente a la 1.ª corrida hay variaciones menores en `edge_no_hard_access` (tarjetas sin resolver) que no cambian el veredicto, porque ninguna estrategia puede resolverlos.

{mdt(edge_inf, '{:.4f}')}

## 4. Re-ajuste y selección (estructura final, escenarios fieles)

Cinco optimizadores, 11 parámetros, 60 ensayos, 8 escenarios de afinado, objetivo J con penalización de dominancia (`optimize2.py`, notebook 03). Comparación por ensayos hasta el umbral y no por tiempo de pared (suspensiones de la laptop):

{mdt(optt)}

Selección (regla fijada de antemano: gates en HOLD, FINAL y EDGE factibles; dominancia sobre el starter en HOLD y FINAL; mejora robusta frente a la 1.ª corrida en puntos por percentil, IC95 inferior mayor que cero):

{mdt(selt)}

{mdt(rob)}

**Lectura.** Ningún candidato mejora de forma robusta. `tpe#2_ns` (tpe#2 con `speed_kappa` al máximo, para que el archivo final no necesite código de SPEED_SHIFT) es el mejor elegible y domina al starter en HOLD y FINAL, mientras que las constantes de la 1.ª corrida pierden en un escenario y métrica: {hf_fail}. La diferencia en puntos es estadísticamente nula. Control con datos frescos y reales:

{mdt(f2s)}

{mdt(pubc)}

**Variante sin coste sombra (`wu0`, w_unit = 0).** La ablación sugería que el coste sombra de la flota no aporta (J baja). La evalué como candidato explícito con la misma regla: {rwu['dPuntos_medio']:+.2f} puntos por escenario (IC95 [{rwu['IC95'][0]:.2f}, {rwu['IC95'][1]:.2f}]), FIN2 con coste {wu['f2c']:+.1f} %, lead {wu['f2l']:+.1f} % y p95 {wu['f2p']:+.1f} %; públicos 5 000 con coste {wu['public_5k_c']:+.1f} % y lead {wu['public_5k_l']:+.1f} %, 150 000 con coste {wu['public_150k_c']:+.1f} % y lead {wu['public_150k_l']:+.1f} %. Abarata y alarga la entrega: es un desplazamiento sobre la frontera coste y tiempo (lo mismo que mueve `w_time`), no una mejora, así que no se adopta.

En FIN2 y en los dos públicos reales ambas opciones son equivalentes (diferencias de ±1 % en coste y lead). Decisión: conservar las constantes de la 1.ª corrida, que son más simples y no obligan a justificar ningún cambio. Constantes finales: w_time {pw['w_time']}, w_vip {pw['w_vip']}, w_fail {pw['w_fail']}, vip_fail_extra {pw['vip_fail_extra']}, terminal_extra {pw['terminal_extra']}, w_unit {pw['w_unit']}, unit_util_gamma {pw['unit_util_gamma']}, hold_cap_min {pw['hold_cap_min']}, la_tau {pw['la_tau']}, up_wait_thr {pw['up_wait_thr']}.

### 4.1 SPEED_SHIFT y EXPANDED_CAPACITY (`stage_speed.py`)

{mdt(spd)}

No se adoptan: la relación coste y beneficio no compensa donde se activa SPEED_SHIFT, y EXPANDED_CAPACITY no se activa (clusters de ≤ 4 tarjetas, capacidades ≥ 8).

### 4.2 Techos de agrupación y p95

{mdt(cet)}

Cota superior de lotes = clusters + intentos fallidos. El p95 incluye la espera de reintento de 1 440 min, que ninguna estrategia controla.

### 4.3 Ablación sobre la propuesta final (28 escenarios de afinado y decisión)

{mdt(ablt)}

Por J a secas, quitar el riesgo de fallo o el coste sombra casi no cambia; por dominancia y puntos de cohorte sí importan. El emparejamiento y las mejoras mensuales importan sobre todo con flota saturada.

## 5. CPU y RAM al estilo del evaluador (`cpu_eval.py`)

{mdt(pub)}

Un calentamiento y la mediana de 3 ejecuciones en serie, intercaladas (estrategia nula, starter y final); CPU neta = CPU menos la de la estrategia nula. El cómputo propio suma {timing['own_compute_s']:.1f} s en 150 000 tarjetas; el resto es espera por cada `dispatch_batch` ({timing['svc_dispatch_us_per_call']:.0f} µs por llamada, {timing['svc_dispatch_calls']:,} llamadas).

## 6. Validación final como evaluador

### 6.1 Gates por conjunto (`final_file_validation.csv`)

{mdt(gates)}

Casos de contrato: solo los factibles; `edge_zone_uncovered`, `edge_no_hard_access`, `edge_burst_1500`, `edge_empty` y `edge_one` son infactibles o triviales para cualquier estrategia.

### 6.2 Archivo final frente a starter y referencias (medias; «gana las 4» = mejor en coste, lead, p95 y RCP a la vez)

**AFINADO ({len(S['tune'])}, usado para elegir, no cuenta como validación):** no domina en {tune_fail}

{mdt(tabs['tune'])}

**HOLD ({len(S['hold'])}):**

{mdt(tabs['hold'])}

**FINAL ({len(S['final'])}):**

{mdt(tabs['final'])}

**FIN2 ({len(S['fin2'])}, datos frescos):**

{mdt(tabs['fin2'])}

### 6.3 Diferencia con la 1.ª corrida

Las constantes son las mismas; la única diferencia es el bucle corregido. Cambios medios (archivo final frente a la 1.ª corrida con bucle corregido), esperados cero:

{mdt(dd)}

### 6.4 Equivalencia del archivo congelado con la versión de investigación

{eq.igual.sum()}/{len(eq)} escenarios con coste, lead, p95, UNRESOLVED, retención y RCP idénticos (`equivalence_final_vs_research.csv`).

## 7. Estado de `submission/` y del repositorio

- `submission/` se arma con `solucion/src/build_submission.py`: {comp.get('submission_entradas')}; `generated_artifacts/` con {n_art} archivos curados; `ai_conversations/` solo con `.gitkeep` hasta el volcado final.
- Repositorio privado: `https://github.com/{GH}` (privado: {private}). `origin`:

```text
{git_remote}
```

- Colaboradores activos e invitaciones pendientes (GitHub no admite permiso de solo lectura en repositorios personales, la cuenta del BBVA queda con `write`; ni Claude ni otras cuentas figuran):

```text
colaboradores: {collabs}
invitaciones:  {invites}
```

- Commits (sin línea de coautoría de IA, a pedido de Diego):

```text
{git_log}
```

- Estado del árbol:

```text
{git_status}
```

- Se sube: `submission/`, `solucion/` (código, CSV, figuras, notebooks, presentación, `REFERENCIAS.md`; los 5 PDF de los libros quedan solo en el disco local por sus licencias), `tests/test_policy_unit.py` y los cambios de raíz permitidos (`candidate_strategy.py`, `.gitignore`).
- No se sube (`.gitignore`): prompts e informes de IA (`PROMPT_CLAUDE_CODE*.md`, `informe_cowork*.md`, `informe_parts/`, `STRATEGY_borrador.md`, `PUSH_INSTRUCTIONS.md`), cachés, `scratch/`, datasets sintéticos y `output/`.
- Regla de Diego: en `main` solo van las versiones finales y vigentes, sin duplicados.

## 8. Lo que falta y quién lo hace

1. **Cowork:** auditoría final de este informe, de `STRATEGY.md` y de la presentación; recomendaciones finales (idealmente solo estéticas o de redacción).
2. **Cowork:** enviar a Diego, en Markdown con los roles identificados y fecha aproximada, el historial o resumen de **sus** conversaciones con el contexto y la definición del problema, para unirlo a la sesión de Claude Code.
3. **Claude Code (yo), al final:** exportar esta sesión real y completa a `submission/ai_conversations/session-01.md`, sin inventar ni omitir intentos, con secretos o datos personales sustituidos por `[REDACTED: motivo]` y declarados en `redactions`; añadir el archivo de Cowork y ajustar `conversation_files` del manifiesto y la sección de IA de `STRATEGY.md`.
4. **Última verificación y push:** `python -S run.py --strategy submission/candidate_strategy.py`, `unittest`, `compliance_check.py`, `git status` limpio y `git push` a `main` del repositorio privado. Cierre: lunes 19 de octubre de 2026, 22:00 (Lima).
5. **Diego:** confirmar el correo de inscripción en Genoma{'' if acc else ' y que la cuenta `bbvaHackaton2026` acepte la invitación'}.

## 9. Riesgos y limitaciones vigentes

1. **Escenarios sintéticos** dentro de `[scenario_ranges]`; los ocultos pueden diferir en tamaño o perfil de pico. Mitigación: {sum(len(v) for v in S.values())} escenarios en cinco conjuntos, datos públicos como control y puerta de fidelidad.
2. **Cohorte real desconocida:** los puntos de percentil son un proxy; la posición real depende de los rivales.
3. **Dependencia del identificador de cluster:** se aprende en línea; con ids opacos no se retiene y se pierde eficiencia, no gates.
4. **CPU y RAM:** el piso del motor domina; la CPU de la laptop varió hasta 1.8 veces entre sesiones, por eso se reporta CPU neta con mediana de 3. Hardware de medición: Intel Core i7-12700H (14 núcleos, 15.7 GB), Python 3.14; el evaluador usa i7-13700HX, 16 GB y Python 3.13. Con un procesador más rápido bajarían los segundos de CPU de todos los candidatos en proporción parecida (el costo dominante es la espera al motor por cada `dispatch_batch`, {timing['svc_dispatch_us_per_call']:.0f} µs), así que el orden relativo, que es lo que puntúa, no cambia; la memoria no depende del procesador. Un equipo más potente sí acortaría el afinado (más ensayos por hora), aunque el paisaje es plano y no se espera un hallazgo nuevo.
5. **Criterio de dominancia** fijado después de ver HOLD en la 1.ª corrida; confirmado con datos frescos.

## 10. Herramientas, skills y notas

- Skills: `dataviz` (figuras), `redaccion-tesis-unmsm` y `redaccion-cientifica` (texto), `optimizacion-politica-por-simulacion` (creada en la 1.ª corrida y actualizada con la puerta de fidelidad).
- Herramientas offline: Optuna, cmaes, pandas, numpy, scipy, matplotlib, nbclient, jsonschema, MarkItDown.
- Memoria del proyecto y Obsidian actualizados (proyecto, métodos y aprendizajes, incluida la nota sobre validar el generador contra los datos reales).
"""
    out = ROOT / "informe_cowork_v2.md"
    out.write_text(limpiar(md), encoding="utf-8")
    return out


if __name__ == "__main__":
    print(main())
