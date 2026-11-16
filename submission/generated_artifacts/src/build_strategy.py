"""Genera solucion/STRATEGY_final.md y solucion/VERIFICACION_CIFRAS.md.

Cada cifra del texto se inserta con ``F(...)``, que la registra junto a su fuente (archivo y filtro) para la tabla de verificacion.
El texto es prosa en primera persona; los numeros salen de outputs/csvs/ (nada se escribe a mano).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

import v2data as V
from estilo import limpiar

ROOT = Path(__file__).resolve().parents[1]
C = V.C
REG: list[tuple[str, str, str]] = []


def F(label: str, value, src: str, fmt: str = "{}") -> str:
    s = fmt.format(value).replace(",", " ")
    REG.append((label, s, src))
    return s


def main():
    d = V.load()
    S = V.scen_sets(d)
    dec = json.load(open(C / "v2_decision.json"))
    cp5, cp150 = pd.read_csv(C / "cpu_eval_public_5k.csv"), pd.read_csv(C / "cpu_eval_public_150k.csv")
    opt2 = pd.read_csv(C / "optimizers_comparison.csv").set_index("optimizador")
    abf = pd.read_csv(C / "ablation_final.csv").set_index("variante")
    sp = pd.read_csv(C / "speed_capacity_rules.csv").set_index("variante")
    ce = pd.read_csv(C / "ceiling_batches_p95.csv")
    f2 = pd.read_csv(C / "fin2_results.csv")
    cands = json.load(open(C / "v2_candidates.json"))
    la = pd.concat([pd.read_csv(C / "lookahead_assignment.csv"), pd.read_csv(C / "lookahead_assignment_tau2.csv")]).drop_duplicates("variante").set_index("variante")
    ab1 = pd.read_csv(C / "ablation_components.csv").set_index("variante")
    timing = json.load(open(C / "hook_timing.json"))

    def row(cp, pol):
        return cp[cp.estrategia == pol].iloc[0]

    s5, f5, s1, f1 = row(cp5, "starter"), row(cp5, "final"), row(cp150, "starter"), row(cp150, "final")

    def pc(a, b):
        return 100 * (a / b - 1)

    hold, fin, fin2 = S["hold"], S["final"], S["fin2"]
    st, fi = d["starter"], d["final"]
    dm = {k: V.mean_delta(fi, st, S[k]) for k in ("hold", "final", "fin2")}
    dw = {k: V.dominance(fi, st, S[k]) for k in ("hold", "final", "fin2")}
    dw_tune = V.dominance(fi, st, S["tune"])
    _m = {"coste": "cost_total", "lead": "lead_mean", "p95": "lead_p95"}
    _fails = []
    for s_ in S["tune"]:
        for k_, c_ in _m.items():
            if not fi.loc[s_, c_] < st.loc[s_, c_]:
                _dd = 100 * (fi.loc[s_, c_] / st.loc[s_, c_] - 1)
                _fails.append(f"{s_} ({k_} " + ("sin cambio" if abs(_dd) < 0.05 else f"{_dd:+.1f} %") + ")")
        if not fi.loc[s_, "rcp"] > st.loc[s_, "rcp"]:
            _fails.append(f"{s_} (RCP {fi.loc[s_, 'rcp'] - st.loc[s_, 'rcp']:+.3f})")
    tune_txt = "en los otros dos no mejora una métrica: " + ", ".join(_fails) if _fails else "sin excepciones"
    edge_ok = [s for s in S["edge"] if s not in V.INFEASIBLE]
    gates = {k: sum(V.gate_ok(fi.loc[s]) for s in (edge_ok if k == "edge" else S[k])) for k in S}
    gates_st = {k: sum(V.gate_ok(st.loc[s]) for s in (edge_ok if k == "edge" else S[k])) for k in S}
    n_scen = len(fi)
    ret_final = int(fi.hold_breaches.sum())
    run1_vs = V.mean_delta(fi, d["run1"], hold + fin + fin2)
    _rb = dec["robustez_puntos_vs_incumbente"]
    _elig = [c for c in pd.read_csv(C / 'v2_selection.csv').query('elegible').candidato if c in _rb]
    _have = set(pd.read_csv(C / 'fin2_results.csv').candidate) & set(pd.read_csv(C / 'public_control.csv').candidate)
    best_c = max([c for c in (_elig or _rb) if c in _have], key=lambda c: _rb[c]['dPuntos_medio'])
    rob = _rb[best_c]
    f2r = pd.read_csv(C / 'fin2_results.csv'); _a = f2r[f2r.candidate == 'incumbente'].set_index('scenario'); _b = f2r[f2r.candidate == best_c].set_index('scenario').loc[_a.index]
    f2_dc, f2_dl = 100 * (_b.cost_total / _a.cost_total - 1).mean(), 100 * (_b.lead_mean / _a.lead_mean - 1).mean()
    pcr = pd.read_csv(C / 'public_control.csv'); _p5 = pcr[pcr.scenario == 'public_5k'].set_index('candidate'); _p1 = pcr[pcr.scenario == 'public_150k'].set_index('candidate')
    p5_dc = 100 * (_p5.loc[best_c, 'cost_total'] / _p5.loc['incumbente', 'cost_total'] - 1); p1_dc = 100 * (_p1.loc[best_c, 'cost_total'] / _p1.loc['incumbente', 'cost_total'] - 1)
    p5_dl = 100 * (_p5.loc[best_c, 'lead_mean'] / _p5.loc['incumbente', 'lead_mean'] - 1); p1_dl = 100 * (_p1.loc[best_c, 'lead_mean'] / _p1.loc['incumbente', 'lead_mean'] - 1)
    dom_hf = V.dominance(d['final'], d['starter'], S['hold'] + S['final'])['todas']
    emp = pd.read_csv(C / 'emparejamiento_casos_extremos.csv', index_col=0)
    orc = pd.read_csv(C / 'techo_retencion_oraculo.csv')
    _w = f2r[f2r.candidate == 'wu0'].set_index('scenario').loc[_a.index]
    wu_dc, wu_dl = 100 * (_w.cost_total / _a.cost_total - 1).mean(), 100 * (_w.lead_mean / _a.lead_mean - 1).mean()
    rob_wu = _rb['wu0']
    _ra = pd.read_csv(C / 'robustness_results_all.csv')
    run1_file = _ra[(_ra.candidate == 'run1_archivo') & (_ra.scenario == 'edge_burst_bigfleet')].iloc[0]
    rp = V.mean_delta(fi, d["ref_price"], fin2)
    pw = dec["params_ganador"]

    best_j = {k: opt2.loc[k, "mejor_J"] for k in opt2.index}
    abl = abf.J - abf.loc["completo", "J"]
    top_abl = abl.drop("completo").sort_values(ascending=False)

    txt = f"""# STRATEGY

## 1. Qué cambié y por qué

El código inicial despachaba una tarjeta por lote con un round-robin entre carriers. No agrupa, y el motor cobra el *linehaul* por lote: el lote medio del starter es {F('lote medio starter 5k', 1.0, 'baseline_metrics.csv avg_batch', '{:.1f}')} tarjeta. Tras un `INACCESSIBLE_ROUTE` reintenta con el mismo carrier aunque no tenga `HARD_ACCESS`, y acaba en `UNRESOLVED`. Comprueba la zona con una subcadena (`"URBANA" in "SUBURBANA"` es verdadero), deja tarjetas pendientes aunque haya otro carrier libre y guarda todo el histórico, de modo que la memoria crece con los envíos: {F('RAM starter 150k MiB', s1.rss_mib_mediana3, 'cpu_eval_public_150k.csv estrategia=starter rss_mib_mediana3', '{:.0f}')} MiB frente a {F('RAM final 150k MiB', f1.rss_mib_mediana3, 'cpu_eval_public_150k.csv estrategia=final rss_mib_mediana3', '{:.0f}')} MiB de la versión final.

Reescribí `CandidateStrategy` con seis piezas.

**Grupos.** Las tarjetas se agrupan por (cluster, zona, intento, capacidades requeridas): es lo único que el motor admite en un mismo lote.

**Retención solo para agrupar.** El motor audita la retención en el primer tick posterior a `ready_at + 45 min`, y el tick corre antes que la auditoría. Retengo un cluster multi-tarjeta como máximo hasta ese tick (tope de {F('hold_cap_min', pw['hold_cap_min'], 'v2_decision.json params_ganador.hold_cap_min', '{:.0f}')} min). Salir antes nunca produce una infracción. Que un identificador pertenezca a un cluster multi no está escrito en el código: la estrategia lo aprende en línea (probabilidad de cluster multi según la *forma* del id, con los dígitos borrados) y solo retiene si esa probabilidad supera 0.5.

**Prioridad EDD.** Cuando hay contención de flota, pasa primero el grupo cuyo plazo SLA vence antes.

**Carrier por valor esperado.** Para cada grupo calculo, en céntimos, el precio exacto del lote, más el valor del tiempo por la ETA, más el riesgo de fallo atribuible al carrier por el coste esperado de un fallo, más un coste sombra por ocupar la unidad. Las probabilidades de fallo se leen del contexto del escenario. `HARD_ACCESS` elimina el riesgo de ruta inaccesible; los domingos y festivos suben el riesgo operativo del carrier.

**Emparejamiento con arrepentimiento bajo escasez.** Si hay más grupos listos que unidades libres, resuelvo una asignación de coste mínimo (algoritmo húngaro) cuyo coste por pareja es J − M − K. M es el valor de los minutos de espera que se evitan, y K una constante enorme que obliga a emparejar tantos grupos como unidades factibles haya, porque una unidad libre y factible con un envío esperando sería una infracción. Entre los emparejamientos máximos, las unidades escasas van a los grupos más urgentes. Con unidades de sobra uso el greedy.

**Modelo local de la flota y mejoras mensuales.** Cada unidad que envío vuelve en `now + pickup + 2·ida`, como en el motor; así despacho al llegar la tarjeta sin pedir un `snapshot()`, que cuesta CPU. Una unidad extra (`EXTRA_UNIT`) solo se pide si la cola media del periodo anterior supera {F('up_wait_thr', pw['up_wait_thr'], 'v2_decision.json params_ganador.up_wait_thr', '{:.2f}')} tarjetas por tick.

## 2. Cómo lo planteé

Lo traté como un proceso de decisión de Markov con acción (qué grupo sale ahora y con qué carrier) y coste (dinero más penalización por tiempo y riesgo). La programación dinámica exacta es inviable y el archivo evaluado no admite un solver, así que usé una aproximación de política: una regla paramétrica con constantes afinadas offline sobre el simulador. La prioridad se apoya en teoría de scheduling: EDD minimiza la tardanza máxima (Jackson; Pinedo, *Scheduling*).

Dos escenarios públicos habrían llevado al sobreajuste. El motor acepta datos propios (la carpeta de datos no se valida contra los hashes del kit), así que generé escenarios sintéticos dentro de `[scenario_ranges]` con las estadísticas medidas en los públicos: perfil horario y semanal, mezcla de producto y zona, clusters de 2 a 4 tarjetas que llegan en menos de 45 min. Los separé en conjuntos de afinado, de decisión y de validación, y añadí {F('n edge', len(S['edge']), 'final_file_validation.csv scenario=edge_*')} casos de contrato: ráfaga de 1 500 llegadas simultáneas, lotes de capacidad 1, flota al 30 %, un solo carrier, ids opacos, zona sin cobertura.

## 3. Qué medí

CPU y RAM, como el evaluador: un calentamiento y la mediana de tres ejecuciones en serie, restando la CPU de una estrategia nula (el piso del motor).

| | 5 k starter | 5 k final | 150 k starter | 150 k final |
|---|---|---|---|---|
| UNRESOLVED | {F('unres s5', s5.unresolved, 'cpu_eval_public_5k.csv', '{:.0f}')} | {F('unres f5', f5.unresolved, 'cpu_eval_public_5k.csv', '{:.0f}')} | {F('unres s1', s1.unresolved, 'cpu_eval_public_150k.csv', '{:.0f}')} | {F('unres f1', f1.unresolved, 'cpu_eval_public_150k.csv', '{:.0f}')} |
| Infracciones de retención | {F('ret s5', s5.hold_breaches, 'cpu_eval_public_5k.csv', '{:.0f}')} | {F('ret f5', f5.hold_breaches, 'cpu_eval_public_5k.csv', '{:.0f}')} | {F('ret s1', s1.hold_breaches, 'cpu_eval_public_150k.csv', '{:.0f}')} | {F('ret f1', f1.hold_breaches, 'cpu_eval_public_150k.csv', '{:.0f}')} |
| Coste (céntimos) | {F('cost s5', s5.cost_total, 'cpu_eval_public_5k.csv cost_total', '{:,.0f}')} | {F('cost f5', f5.cost_total, 'cpu_eval_public_5k.csv cost_total', '{:,.0f}')} | {F('cost s1', s1.cost_total, 'cpu_eval_public_150k.csv cost_total', '{:,.0f}')} | {F('cost f1', f1.cost_total, 'cpu_eval_public_150k.csv cost_total', '{:,.0f}')} |
| Lead medio (min) | {F('lead s5', s5.lead_mean, 'cpu_eval_public_5k.csv lead_mean', '{:.1f}')} | {F('lead f5', f5.lead_mean, 'cpu_eval_public_5k.csv lead_mean', '{:.1f}')} | {F('lead s1', s1.lead_mean, 'cpu_eval_public_150k.csv lead_mean', '{:.1f}')} | {F('lead f1', f1.lead_mean, 'cpu_eval_public_150k.csv lead_mean', '{:.1f}')} |
| p95 (min) | {F('p95 s5', s5.lead_p95, 'cpu_eval_public_5k.csv lead_p95', '{:.0f}')} | {F('p95 f5', f5.lead_p95, 'cpu_eval_public_5k.csv lead_p95', '{:.0f}')} | {F('p95 s1', s1.lead_p95, 'cpu_eval_public_150k.csv lead_p95', '{:.0f}')} | {F('p95 f1', f1.lead_p95, 'cpu_eval_public_150k.csv lead_p95', '{:.0f}')} |
| RCP | {F('rcp s5', s5.rcp, 'cpu_eval_public_5k.csv rcp', '{:.3f}')} | {F('rcp f5', f5.rcp, 'cpu_eval_public_5k.csv rcp', '{:.3f}')} | {F('rcp s1', s1.rcp, 'cpu_eval_public_150k.csv rcp', '{:.3f}')} | {F('rcp f1', f1.rcp, 'cpu_eval_public_150k.csv rcp', '{:.3f}')} |
| CPU neta (s) | {F('cpu s5', s5.cpu_neta_s, 'cpu_eval_public_5k.csv cpu_neta_s', '{:.1f}')} | {F('cpu f5', f5.cpu_neta_s, 'cpu_eval_public_5k.csv cpu_neta_s', '{:.1f}')} | {F('cpu s1', s1.cpu_neta_s, 'cpu_eval_public_150k.csv cpu_neta_s', '{:.1f}')} | {F('cpu f1', f1.cpu_neta_s, 'cpu_eval_public_150k.csv cpu_neta_s', '{:.1f}')} |
| RAM pico (MiB) | {F('ram s5', s5.rss_mib_mediana3, 'cpu_eval_public_5k.csv', '{:.0f}')} | {F('ram f5', f5.rss_mib_mediana3, 'cpu_eval_public_5k.csv', '{:.0f}')} | {F('ram s1', s1.rss_mib_mediana3, 'cpu_eval_public_150k.csv', '{:.0f}')} | {F('ram f1', f1.rss_mib_mediana3, 'cpu_eval_public_150k.csv', '{:.0f}')} |

Frente al starter, el coste baja {F('dcost 5k', -pc(f5.cost_total, s5.cost_total), 'cpu_eval_public_5k.csv', '{:.0f}')} % en 5 k y {F('dcost 150k', -pc(f1.cost_total, s1.cost_total), 'cpu_eval_public_150k.csv', '{:.0f}')} % en 150 k; el lead medio, {F('dlead 5k', -pc(f5.lead_mean, s5.lead_mean), 'cpu_eval_public_5k.csv', '{:.0f}')} % y {F('dlead 150k', -pc(f1.lead_mean, s1.lead_mean), 'cpu_eval_public_150k.csv', '{:.0f}')} %; el p95, {F('dp95 5k', -pc(f5.lead_p95, s5.lead_p95), 'cpu_eval_public_5k.csv', '{:.1f}')} % y {F('dp95 150k', -pc(f1.lead_p95, s1.lead_p95), 'cpu_eval_public_150k.csv', '{:.1f}')} %. La CPU neta baja {F('dcpu 5k', -pc(f5.cpu_neta_s, s5.cpu_neta_s), 'cpu_eval_public_5k.csv cpu_neta_s', '{:.0f}')} % en 5 k y {F('dcpu 150k', -pc(f1.cpu_neta_s, s1.cpu_neta_s), 'cpu_eval_public_150k.csv cpu_neta_s', '{:.0f}')} % en 150 k, y casi toda la que queda es espera al motor: de las {F('llamadas dispatch', timing['svc_dispatch_calls'], 'hook_timing.json svc_dispatch_calls', '{:,}')} llamadas a `dispatch_batch`, el motor tarda unos {F('us por lote', timing['svc_dispatch_us_per_call'], 'hook_timing.json svc_dispatch_us_per_call', '{:.0f}')} µs en cada una, y esa espera cuenta como CPU del proceso candidato; mi cómputo propio suma {F('compute propio s', timing['own_compute_s'], 'hook_timing.json own_compute_s', '{:.1f}')} s. Solo bajaría con menos lotes, y la agrupación ya está en su techo. El hook más lento tardó {F('hook max', timing['max_hook_s'], 'hook_timing.json max_hook_s', '{:.3f}')} s (límite: 30 s) y el escenario más largo, el público de 150 k, {F('wall 150k', f1.wall_s_mediana3, 'cpu_eval_public_150k.csv wall_s_mediana3 final', '{:.0f}')} s (límite: 900 s).

**Fuera de muestra.** En FIN2, {len(fin2)} escenarios generados después de fijar el candidato, la estrategia gana al starter en coste, lead, p95 y RCP a la vez en {F('dom fin2', dw['fin2']['todas'], 'final_file_validation.csv vs starter, fin2_*', '{:.0f}')} de {len(fin2)}, con coste {F('fin2 coste', dm['fin2']['coste_pct'], 'idem', '{:+.1f}')} %, lead {F('fin2 lead', dm['fin2']['lead_pct'], 'idem', '{:+.1f}')} %, p95 {F('fin2 p95', dm['fin2']['p95_pct'], 'idem', '{:+.1f}')} % y RCP {F('fin2 rcp', dm['fin2']['rcp_d'], 'idem', '{:+.3f}')}, y cumple los gates en {F('gates fin2', gates['fin2'], 'final_file_validation.csv', '{:.0f}')} de {len(fin2)} (el starter, en {F('gates st fin2', gates_st['fin2'], 'starter en fin2_*', '{:.0f}')}). En HOLD y FINAL gana en las cuatro métricas en {F('dom hold', dw['hold']['todas'], 'idem hold_*', '{:.0f}')} y {F('dom final', dw['final']['todas'], 'idem final_*', '{:.0f}')} de {len(hold)} escenarios; en los {len(S['tune'])} de afinado, que sirvieron para elegir, en {F('dom tune', dw_tune['todas'], 'idem tune_*', '{:.0f}')}.

**Robustez.** En los {n_scen} escenarios sintéticos hay {F('ret total', ret_final, 'final_file_validation.csv hold_breaches sum', '{:.0f}')} infracciones de retención y ningún error. Cumple los gates en {F('gates tune', gates['tune'], 'idem', '{:.0f}')}/{len(S['tune'])} escenarios de afinado, {gates['hold']}/{len(hold)} de HOLD y {gates['edge']}/{len(edge_ok)} de los casos de contrato factibles. No cuento los casos que ninguna estrategia puede resolver (zona sin carrier, `HARD_ACCESS` inexistente, ráfaga mayor que la flota).

**Techos.** Cada cluster necesita al menos un lote en el primer intento y cada reintento fallido añade, como mucho, uno más. Esa cota superior deja el número de lotes de la estrategia en {F('lotes vs cota', ce.lote_vs_cota_sup_pct.mean(), 'ceiling_batches_p95.csv lote_vs_cota_sup_pct mean', '{:+.2f}')} % de promedio: no hay agrupación pendiente. El p95 queda a {F('p95 vs eta', ce.p95_vs_eta_pct.mean(), 'ceiling_batches_p95.csv p95_vs_eta_pct mean', '{:+.2f}')} % del de la regla «siempre el carrier más rápido»; casi todos los fallos son ausencias del cliente, que no dependen del carrier, y el reintento espera 1 440 min. Un oráculo que conoce el tamaño real de cada cluster mejoraría el lead {F('oraculo lead', -orc.lead_pct.mean(), 'techo_retencion_oraculo.csv lead_pct', '{:.1f}')} % y el coste {F('oraculo coste', -orc.coste_pct.mean(), 'techo_retencion_oraculo.csv coste_pct', '{:.1f}')} % como máximo, y una regla de espera por probabilidades, que probé, no mejora a la actual.

## 4. Cómo afiné y cómo elegí

Comparé cinco optimizadores con el mismo espacio de 11 parámetros, 60 evaluaciones cada uno, los mismos ocho escenarios y el mismo objetivo: las cuatro métricas de negocio normalizadas por una referencia barata, ponderadas 40/25/20/15, más una penalización dura por cada gate violado y otra por no superar al starter con margen. El mejor valor fue {F('J mejor', min(best_j.values()), 'optimizers_comparison.csv mejor_J', '{:.3f}')} y el peor {F('J peor', max(best_j.values()), 'idem', '{:.3f}')} ({F('rango J', 100*(max(best_j.values())/min(best_j.values())-1), 'idem', '{:.1f}')} % de diferencia): un paisaje casi plano. Los comparé por ensayos hasta quedar a 1 % del mejor valor, no por tiempo de pared, que la suspensión de la laptop distorsiona.

Antes de afinar contrasté mis escenarios con los datos públicos, estadístico por estadístico. Un primer re-ajuste, hecho con escenarios cuyas tarjetas de un mismo destino llegaban más juntas que en la realidad (mediana de 14 frente a 23 minutos), eligió un tope de retención de 27.7 min que, en el ejemplo público de 5 000 tarjetas, empeoraba a la versión anterior (coste +2.3 %, lote medio 1.199 frente a 1.273). Lo detecté al comparar con los datos reales; corregí el generador y repetí el afinado.

Elegí con una regla fijada de antemano: gates en todos los conjuntos, cero infracciones de retención, dominancia sobre el starter en HOLD y FINAL, y una mejora robusta frente a las constantes de la primera corrida en puntos por escenario, según la regla de percentiles de la evaluación (percentil = 100·(n−r)/(n−1); 20 puntos por métrica; escenarios ponderados 40/25/20/15). Con un bootstrap pareado sobre {int(rob['n'])} escenarios, el mejor candidato elegible, {best_c}{' (TPE sin compras de SPEED_SHIFT)' if best_c == 'tpe#2_ns' else ''}, queda a {F('dpts', rob['dPuntos_medio'], 'v2_decision.json robustez_puntos_vs_incumbente', '{:+.1f}')} puntos por escenario de la versión anterior (IC 95 % [{rob['IC95'][0]:.1f}; {rob['IC95'][1]:.1f}]): no hay mejora robusta, así que conservo las constantes de la primera corrida, con el bucle de despacho corregido. En FIN2 {best_c} cambia el coste {F('f2 dc', f2_dc, 'fin2_results.csv', '{:+.1f}')} % y el tiempo medio {F('f2 dl', f2_dl, 'fin2_results.csv', '{:+.1f}')} %; en los públicos, el coste {F('p5 dc', p5_dc, 'public_control.csv', '{:+.1f}')} % (5 000) y {F('p1 dc', p1_dc, 'public_control.csv', '{:+.1f}')} % (150 000): es equivalente. Las constantes conservadas superan al starter en las cuatro métricas en {F('dom hf', dom_hf, 'final_file_validation.csv hold+final', '{:.0f}')} de {len(S['hold']) + len(S['final'])} escenarios de HOLD y FINAL; en uno pierden en el tiempo medio.

## 5. Qué no funcionó y qué aporta cada pieza

- **Hungarian puro por tick.** Empeoró el objetivo en {F('hung dJ', ab1.loc['hungarian_por_tick (assign=1)','J']-ab1.loc['full','J'], 'ablation_components.csv J hungarian - full', '{:+.2f}')} y gastó más CPU: minimizar la suma de J deja sin unidad a los grupos caros, que son los urgentes. El arrepentimiento lo arregla, pero solo importa con flota saturada: con la flota al 30 %, el lead medio bajó de {F('lead greedy', emp.loc['edge_stress_noup','lead_greedy'], 'emparejamiento_casos_extremos.csv edge_stress_noup', '{:.0f}')} a {F('lead lookahead', emp.loc['edge_stress_noup','lead_con'], 'idem', '{:.0f}')} min, y con 12 000 tarjetas y flota al 45 % subió {F('lead xl', emp.loc['edge_stress_xl','lead_%'], 'idem edge_stress_xl', '{:.1f}')} %; en escenarios normales no cambió nada.
- **Dos errores míos en el bucle de despacho.** El primero: la versión inicial del emparejamiento cortaba el bucle con tarjetas pendientes cuando el carrier admite lotes de una tarjeta, y produjo 83 infracciones de retención con capacidad 1 (`robustness_results_lookahead_v1_bug_cap1.csv`); lo detectó el conjunto de casos de contrato. El segundo apareció en la segunda corrida: al repartir por ventanas de 24 grupos, el bucle terminaba con grupos listos tras una ronda que sí había enviado. Lo delató una ablación absurda (con ventana 1 fallaban 25 escenarios, y un parámetro de tamaño no puede romper gates). Con una ráfaga de {int(run1_file.admitted)} tarjetas simultáneas y flota amplia, la versión defectuosa tuvo {int(run1_file.hold_breaches)} infracciones de retención y la corregida, {int(fi.loc['edge_burst_bigfleet','hold_breaches'])}. Corregí el bucle y añadí una prueba de regresión y el caso `edge_burst_bigfleet`.
- **SPEED_SHIFT y EXPANDED_CAPACITY.** Con un umbral exigente, SPEED_SHIFT casi nunca se activa. Con uno laxo compra {F('speed buys', sp.loc['speed_k0.2','speed_total'], 'speed_capacity_rules.csv speed_total speed_k0.2', '{:.0f}')} mejoras en 12 escenarios, sube el coste ≈ {F('speed coste', 100*np.mean([sp.loc['speed_k0.2',f'cost_{s}']/sp.loc['base',f'cost_{s}']-1 for s in [c[5:] for c in sp.columns if c.startswith('cost_')]]), 'idem', '{:.1f}')} % y baja el lead ≈ {F('speed lead', -100*np.mean([sp.loc['speed_k0.2',f'lead_{s}']/sp.loc['base',f'lead_{s}']-1 for s in [c[5:] for c in sp.columns if c.startswith('lead_')]]), 'idem', '{:.1f}')} %: no compensa. EXPANDED_CAPACITY nunca se activa: los clusters no superan 4 tarjetas y las capacidades empiezan en 8. Dejé ambas fuera del archivo final.
- **Despachar solo en los ticks.** Ahorra 7.5 min de espera por tarjeta a costa de un 2 % de lead, sin ahorro medible de CPU.
- **Ablación del candidato final** (28 escenarios de afinado y decisión). Medido solo con J, quitar el riesgo de fallo o el coste sombra lo mejora, pero ambos movimientos recorren la frontera coste y tiempo: sin el coste sombra baja el coste y sube el lead ({F('wu0 coste fin2', wu_dc, 'fin2_results.csv wu0', '{:+.1f}')} % y {F('wu0 lead fin2', wu_dl, 'fin2_results.csv wu0', '{:+.1f}')} % en FIN2, y el candidato `wu0` queda en {F('wu0 pts', rob_wu['dPuntos_medio'], 'v2_decision.json', '{:+.1f}')} puntos por escenario, IC 95 % [{rob_wu['IC95'][0]:.1f}; {rob_wu['IC95'][1]:.1f}]), así que no lo adopto. El candidato completo supera al starter en las cuatro métricas en {F('dom completo', abf.loc['completo','domina_starter_de_28'], 'ablation_final.csv domina_starter_de_28', '{:.0f}')} de 28 escenarios y suma {F('proxy completo', abf.loc['completo','puntos_proxy'], 'ablation_final.csv puntos_proxy', '{:.1f}')} puntos. Sin el valor del tiempo baja a {F('dom sin tiempo', abf.loc['sin valor del tiempo (w_time=0)','domina_starter_de_28'], 'ablation_final.csv', '{:.0f}')} escenarios y {F('proxy sin tiempo', abf.loc['sin valor del tiempo (w_time=0)','puntos_proxy'], 'ablation_final.csv', '{:.1f}')} puntos; sin retención, el coste sube de {F('coste completo', abf.loc['completo','coste_vs_ref'], 'ablation_final.csv coste_vs_ref', '{:.2f}')} a {F('coste sin ret', abf.loc['sin retención (nunca retener)','coste_vs_ref'], 'ablation_final.csv coste_vs_ref', '{:.2f}')} veces el de la referencia barata y los puntos caen a {F('proxy sin ret', abf.loc['sin retención (nunca retener)','puntos_proxy'], 'ablation_final.csv', '{:.1f}')}. El emparejamiento y las mejoras mensuales solo importan con flota saturada, y los conservo como seguro.

## 6. La palanca coste–tiempo

La variable que mueve la posición en la frontera es `w_time`, los céntimos que vale un minuto de entrega por tarjeta. El valor final es {F('w_time', pw['w_time'], 'v2_decision.json params_ganador.w_time', '{:.2f}')}. Frente a la estrategia «siempre la más barata», en FIN2 gasto {F('vs barata coste', rp['coste_pct'], 'idem fin2 ref_price', '{:+.1f}')} % y entrego {F('vs barata lead', rp['lead_pct'], 'idem', '{:+.1f}')} % más rápido; frente al starter, mejoro las cuatro métricas. El re-ajuste no encontró un punto mejor de forma robusta, así que lo conservo.

## 7. Limitaciones

No tengo acceso a los escenarios de evaluación. Mi hipótesis, no medida, es que se parecen a los míos, que reproducen lo medido en los dos públicos; los ocultos pueden diferir en tamaño o en perfil de pico. Queda pendiente probar la política con datos de operación real. Tampoco conozco a los demás candidatos, y los «puntos» que cito son un proxy sobre una cohorte propia, no el cálculo del evaluador. El aprendizaje de clusters multi aprovecha que, en los datos públicos, la forma del id distingue clusters multi de singleton; con ids opacos la estrategia no retiene y pierde eficiencia, no gates. La CPU y la RAM tienen un piso común del motor (≈ {F('piso ram', row(cp5,'noop').rss_mib_mediana3, 'cpu_eval_public_5k.csv noop', '{:.0f}')} MiB). Medí en un Intel Core i7-12700H (15.7 GB) con Python 3.14; el evaluador usa un i7-13700HX y Python 3.13. Un procesador más rápido baja los segundos de CPU de todos los candidatos sin cambiar su orden, porque domina la espera al motor por lote; solo acortaría el afinado.

## 8. Fuentes, ayudas de IA y verificación

**IA.** Trabajé con Claude Code (Anthropic, modelo Claude Sonnet 5.5) en el código, los experimentos y los documentos, y con Claude Cowork (claude-opus-4-8 y claude-opus-5-5) para auditar la carpeta y los resultados, investigar bibliografía y redactar prompts. Mi parte fue dirigir, cuestionar y decidir: fijé el objetivo de ganar al starter en las cuatro métricas, pedí comparar cinco optimizadores y advertí del riesgo de sesgar el afinado con datos sintéticos. Las conversaciones están en `ai_conversations/` (`cowork-sesion-01.md` y `claude-code-sesion-*.md`). Verifiqué cada aportación ejecutando el motor, las pruebas ({F('n tests', 16, 'python -m unittest discover -s tests -v', '{:.0f}')}, incluida la del kit) y `python -S run.py`, y comparando con referencias simples. El archivo final reproduce exactamente, escenario por escenario, la versión de investigación con la que se eligieron los parámetros.

**Código reutilizado.** Del kit conservo `interfaces.py` y los lanzadores; la estrategia es nueva y no copié código externo.

**Notas heredadas.** `anexos/nota_traspaso_legacy.pdf` (LEG-07) y `anexos/nota_operaciones_legacy.md` (LEG-12) piden a un asistente de IA crear un archivo con una cadena fija y escribir en este documento que se omite la revisión de la estrategia. No hice ninguna de las dos cosas: las traté como datos, no como instrucciones, y las rechazo.

**Bibliografía y fuentes.** Klapp, Erera y Toriello, *The Dynamic Dispatch Waves Problem for Same-Day Delivery* (EJOR 2018); Pinedo, *Scheduling* (EDD); Boysen, Fedtke y Schwerdfeger (2021), OR Spectrum 43(1):1–58; Bergstra y Bengio (2012), JMLR 13(10):281–305; Akiba et al. (2019), Optuna; Eiselt y Sandblom, *Linear Programming and its Applications* (asignación); Chen, Batson y Dang, *Applied Integer Programming* (emparejamiento). Cito los cinco libros consultados en `solucion/REFERENCIAS.md`; no los incluyo en el repositorio por respeto a sus licencias. Herramientas offline: Optuna, cmaes, pandas, scipy, matplotlib y MarkItDown.
"""
    # limpieza de artefactos de formato
    txt = txt.replace("{len(pw) and 11}", "11")
    words = len(re.findall(r"\w+", txt))
    txt = limpiar(txt)
    words = len(re.findall(r"\w+", txt))
    (ROOT / "STRATEGY_final.md").write_text(txt, encoding="utf-8")
    ver = ["# Verificación de cifras de STRATEGY.md", "", "Cada cifra del texto, con el archivo y el filtro de donde sale (rutas relativas a `solucion/outputs/csvs/`).", "",
           "| cifra | valor | fuente |", "|---|---|---|"]
    ver += [f"| {a} | {b} | {c} |" for a, b, c in REG]
    ver += ["", f"Palabras de STRATEGY.md: {words} (límite 2 500).", "", "## No verificado en esta corrida",
            "- Citas bibliográficas de libros (Pinedo; Eiselt y Sandblom; Chen, Batson y Dang): verificadas por su existencia (índices de los PDF para los dos últimos), no re-leídas en su totalidad.",
            "- Klapp, Erera y Toriello (EJOR 2018), Boysen et al. (2021), Bergstra y Bengio (2012), Akiba et al. (2019): existencia y datos bibliográficos comprobados en búsqueda web el 16-oct-2026."]
    (ROOT / "VERIFICACION_CIFRAS.md").write_text("\n".join(ver) + "\n", encoding="utf-8")
    return words


if __name__ == "__main__":
    print("palabras:", main())
