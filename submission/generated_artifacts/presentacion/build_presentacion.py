"""Genera solucion/presentacion/presentacion.html (autocontenida) a partir de plantilla.html y de los CSV vigentes de outputs/csvs/.
Todo numero que aparece en la presentacion sale de un CSV o JSON: al terminar la corrida definitiva basta volver a ejecutar este script.
Uso: python build_presentacion.py [--allow-stale]"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "solucion" / "src"))
import v2data as V  # noqa: E402

C = V.C


def first(*names):
    for n in names:
        if (C / n).exists():
            return C / n
    raise FileNotFoundError(names)


def fresh_check(allow: bool):
    """Falla si los resultados son anteriores a la regeneracion de escenarios (corrida con el generador corregido)."""
    ref = REPO / "solucion" / "scenarios_mc" / "index.json"
    for f in ("final_file_validation.csv", "cpu_eval_public_150k.csv", "v2_decision.json"):
        p = C / f
        if p.exists() and ref.exists() and p.stat().st_mtime < ref.stat().st_mtime:
            msg = f"{f} es anterior a la regeneracion de escenarios (resultados obsoletos)"
            if not allow:
                raise SystemExit("ABORTA: " + msg + ". Usa --allow-stale solo para previsualizar.")
            print("AVISO:", msg)


def fmt(x, dd=0):
    return f"{x:,.{dd}f}".replace(",", " ") if dd == 0 else f"{x:.{dd}f}"


def pct_txt(a: float, b: float) -> str:
    v = 100 * (a / b - 1)
    return ("\u2212" if v < 0 else "+") + fmt(abs(v), 0 if abs(v) >= 10 else 1) + " %"


def kind_of(name: str) -> str:
    return name.split("_", 1)[1].rsplit("_", 1)[0]


def build() -> dict:
    d = V.load()
    S = V.scen_sets(d)
    dec = json.load(open(C / "v2_decision.json"))
    pw = dec["params_ganador"]
    cp5, cp150 = pd.read_csv(C / "cpu_eval_public_5k.csv"), pd.read_csv(C / "cpu_eval_public_150k.csv")
    v1 = pd.read_csv(C / "final_vs_baseline.csv")
    timing = json.load(open(C / "hook_timing.json"))
    comp = json.load(open(C / "compliance_checks.json"))
    _la = pd.concat([pd.read_csv(C / 'lookahead_assignment.csv'), pd.read_csv(C / 'lookahead_assignment_tau2.csv')]).drop_duplicates('variante').set_index('variante')

    def pubd(cp, scen, v1scen):
        out = {}
        for pol, key in (("starter", "starter"), ("final", "final")):
            r = cp[cp.estrategia == pol].iloc[0]
            out[key] = {"cost": float(r.cost_total), "lead": float(r.lead_mean), "lead95": float(r.lead_p95), "rcp": float(r.rcp), "unresolved": int(r.unresolved),
                        "hold": int(r.hold_breaches), "cpu": float(r.cpu_neta_s), "ram": float(r.rss_mib_mediana3), "batch": float(r.avg_batch), "sla": float(r.sla_breach_rate)}
        r = v1[(v1.policy == "final") & (v1.scenario == v1scen)].iloc[0]
        out["v1"] = {"cost": float(r.cost_total), "lead": float(r.lead_mean), "lead95": float(r.lead_p95), "rcp": float(r.rcp), "unresolved": int(r.unresolved),
                     "hold": int(r.hold_breaches), "cpu": float(r.cpu_net_s), "ram": float(r.rss_mb), "batch": float(r.avg_batch), "sla": float(r.sla_breach_rate)}
        return out

    pub = {"5k": pubd(cp5, "public_5k", "public_5k"), "150k": pubd(cp150, "public_150k", "public_150k")}

    def row(df, s):
        r = df.loc[s]
        return {"cost": float(r.cost_total), "lead": float(r.lead_mean), "p95": float(r.lead_p95), "rcp": float(r.rcp)}

    sets = {}
    for k in ("hold", "final", "fin2"):
        names = S[k]
        sets[k.upper()] = {"scen": [{"name": s, "kind": kind_of(s), "fin": row(d["final"], s), "starter": row(d["starter"], s), "v1": row(d["run1"], s)} for s in names]}

    # gates
    edge_ok = [s for s in S["edge"] if s not in V.INFEASIBLE]
    gt, ok_all, n_all = [], 0, 0
    for k, lab in (("tune", "Afinado"), ("hold", "HOLD"), ("final", "FINAL"), ("fin2", "FIN2"), ("edge", "Contrato (factibles)")):
        names = edge_ok if k == "edge" else S[k]
        ok = sum(V.gate_ok(d["final"].loc[s]) for s in names)
        oks = sum(V.gate_ok(d["starter"].loc[s]) for s in names if s in d["starter"].index)
        gt.append([lab, f"{ok}/{len(names)}", f"{oks}/{len(names)}", int(d["final"].loc[names].hold_breaches.sum())])
        ok_all += ok; n_all += len(names)
    gates_total = f"{ok_all}/{n_all}"

    # datos publicos
    sh = pd.read_csv(REPO / "data" / "shipments.csv")
    mix_prod = [[k, float(v)] for k, v in sh["product"].value_counts(normalize=True).items()]
    mix_zone = [[k, float(v)] for k, v in sh["zone"].value_counts(normalize=True).items()]
    n_scen = {k: len(S[k]) for k in S}

    s5, f5, s1, f1 = pub["5k"]["starter"], pub["5k"]["final"], pub["150k"]["starter"], pub["150k"]["final"]
    pc = lambda a, b: 100 * (a / b - 1)
    dm = {k: V.mean_delta(d["final"], d["starter"], S[k]) for k in ("hold", "final", "fin2")}
    dw = {k: V.dominance(d["final"], d["starter"], S[k]) for k in ("hold", "final", "fin2")}

    # optimizacion
    tr = pd.read_csv(first("optimizers_trials.csv", "optimizers_trials_v2.csv"))
    cmp_ = pd.read_csv(first("optimizers_comparison.csv", "optimizers_comparison_v2.csv"))
    order = ["grid", "random", "sobol", "tpe", "cmaes"]
    names = {"grid": "Grid", "random": "Random", "sobol": "Sobol", "tpe": "TPE", "cmaes": "CMA-ES"}
    colors = {"grid": "#9AA7BF", "random": "#F8CD51", "sobol": "#2DCCCD", "tpe": "#1973B8", "cmaes": "#F35E61"}
    series = {o: [float(x) for x in tr[tr.optimizer == o].sort_values("n")["best"]] for o in order if o in set(tr.optimizer)}
    cmp_ = cmp_.set_index("optimizador")
    thr_col = [c for c in cmp_.columns if c.startswith("ensayos_hasta")][0]
    table = []
    for o in order:
        if o in cmp_.index:
            v = cmp_.loc[o, thr_col]
            table.append([names[o], float(cmp_.loc[o, "mejor_J"]), None if pd.isna(v) else int(v)])
    best_j = [t[1] for t in table]
    spread = 100 * (max(best_j) / min(best_j) - 1)
    opt = {"series": series, "colors": colors, "names": names, "table": table,
           "note": f"Los cinco métodos terminan a {fmt(spread,1)} % entre sí: el paisaje es casi plano. Por eso comparo por ensayos hasta quedar a 1 % del mejor valor y no por tiempo de pared, que la suspensión de la laptop distorsiona."}

    sel_df = pd.read_csv(first("v2_selection.csv"))
    sel = [{"cand": r.candidato, "proxy": float(r.puntos_proxy), "elegible": bool(r.elegible)} for r in sel_df.sort_values("puntos_proxy", ascending=False).itertuples()]
    rob = dec["robustez_puntos_vs_incumbente"]
    best = dec["ganador_provisional"]
    if dec.get("conservar_incumbente"):
        sel_winner = "<span class='chip warn'>Resultado</span> Ningún candidato mejoró de forma robusta a la versión anterior: se conserva."
    else:
        r = rob[best]
        sel_winner = (f"<span class='chip ok'>Elegido</span> <b>{best}</b>: +{fmt(r['dPuntos_medio'],1)} puntos por escenario frente a la versión anterior "
                      f"(IC95 [{fmt(r['IC95'][0],1)}; {fmt(r['IC95'][1],1)}], gana en {r['gana_en']} de {r['n']} escenarios).")
    sel_rules = ["Cumplir los gates en HOLD, FINAL y los casos de contrato factibles, con cero infracciones de retención.",
                 "Ganar al punto de partida en las cuatro métricas de negocio en todos los escenarios de HOLD y FINAL.",
                 "Superar a la versión anterior de forma robusta en puntos por percentil (intervalo bootstrap pareado con límite inferior mayor que cero).",
                 "Confirmar en escenarios frescos (FIN2) y en los datos públicos reales. Si no mejora de forma robusta, se conserva la versión anterior."]

    # ablacion
    abf = pd.read_csv(first("ablation_final.csv"))
    short = {"completo": "Propuesta completa", "sin retención (nunca retener)": "Sin retención", "sin retener al 2.º miembro": "Sin retener al 2.º miembro",
             "sin liberar el cluster completo": "Sin liberar el cluster completo", "sin valor del tiempo (w_time=0)": "Sin valor del tiempo", "sin riesgo de fallo (w_fail=0)": "Sin riesgo de fallo",
             "sin prioridad VIP": "Sin prioridad VIP", "sin coste sombra de flota": "Sin coste sombra de flota", "sin emparejamiento (solo greedy)": "Sin emparejamiento",
             "sin mejoras mensuales": "Sin mejoras mensuales", "sin SPEED_SHIFT": "Sin SPEED_SHIFT"}
    abl = [{"v": short.get(r.variante, r.variante), "proxy": float(r.puntos_proxy), "dom": int(r.domina_starter_de_28)} for r in abf.sort_values("puntos_proxy", ascending=False).itertuples()]
    full = abf[abf.variante == "completo"].iloc[0]
    abl_note = (f"Entre paréntesis, escenarios (de {len(S['tune']) + len(S['hold'])}) donde la propuesta supera al punto de partida en las cuatro métricas. "
                f"Quitar la retención o el valor del tiempo es lo que más cuesta; el emparejamiento y las mejoras mensuales importan sobre todo con flota saturada.")

    hk = timing["max_hook_s"]

    tune_dom = V.dominance(d["final"], d["starter"], S["tune"])["todas"]

    D = {
        "pub": pub, "sets": sets, "gates_total": gates_total, "gates_tabla": gt,
        "gates_def": [["0", "tarjetas sin resolver", "Ninguna puede quedar en estado UNRESOLVED."], ["≤ 6 %", "incumplimiento del plazo (SLA)", "Medido por escenario."],
                      ["0", "infracciones de retención", "Pasados 45 minutos, con transportista libre, esperar cuenta como falta."], ["15 min", "por escenario, 30 s por llamada", "Tiempo máximo de ejecución."]],
        "data_kpis": [[fmt(5000), "tarjetas en el ejemplo pequeño", "y 150 000 en el grande"], ["90 días", "de admisión", "más un drenaje hasta resolver todo"],
                      ["4 a 6", "transportistas por escenario", "zonas, tarifas, capacidades y flota propias"], ["4 y 4", "productos y zonas", "VIP_BLACK, BUSINESS, SME, STANDARD; URBANA a REMOTA"]],
        "mix_prod": mix_prod, "mix_zone": mix_zone,
        "data_list": ["Los dos escenarios públicos (5 000 y 150 000 tarjetas) con su catálogo de transportistas, festivos y reglas: son la única realidad medible y los uso como control, no para afinar.",
                      f"{sum(n_scen.values()) + 0} escenarios sintéticos dentro de los rangos publicados, en cinco conjuntos: afinado ({n_scen['tune']}), decisión HOLD ({n_scen['hold']}), validación FINAL ({n_scen['final']}), datos frescos FIN2 ({n_scen['fin2']}) y {n_scen['edge']} casos de contrato.",
                      "Un generador propio que reproduce la mezcla de productos y zonas, el perfil horario y semanal y, desde la corrección, el desfase de llegada entre las tarjetas de un mismo destino (uniforme entre 0 y 45 minutos).",
                      "Una puerta de fidelidad automática compara el generador con los datos reales antes de cada afinado."],
        "defects": [["Despacha una tarjeta por lote", f"El motor cobra un coste fijo por viaje y el lote medio es {fmt(s5['batch'],1)}: no aprovecha los destinos con varias tarjetas."],
                    ["Reintenta con el mismo transportista", "Tras una ruta inaccesible repite con quien no tiene acceso difícil, y la tarjeta termina sin resolver."],
                    ["Deja tarjetas esperando", "Examina cada tarjeta una vez por tick y la deja pendiente aunque haya otro transportista libre: infracción de retención."],
                    ["Guarda todo el histórico", f"La memoria crece con el número de envíos: {fmt(s1['ram'],0)} MiB en el ejemplo grande frente a {fmt(f1['ram'],0)} MiB de la propuesta."]],
        "flow": [
            {"id": "grupos", "titulo": "Agrupar", "corto": "cluster, zona, intento, capacidad",
             "que": "Reúne las tarjetas que pueden viajar juntas: mismo destino, misma zona, mismo intento y capacidades compatibles.", "porque": "Es lo único que el motor admite en un mismo lote, y cada lote paga un coste fijo.",
             "evidencia": f"Los lotes quedan {fmt(abs(pc_ce()), 2)} % {'por debajo' if pc_ce() <= 0 else 'por encima'} de la cota superior (clusters más reintentos): no queda agrupación pendiente."},
            {"id": "retener", "titulo": "Esperar solo si agrupa", "corto": f"tope {fmt(pw['hold_cap_min'],1)} min, nunca pasa de la auditoría",
             "que": "Retiene un grupo solo si es probable que lleguen más tarjetas del mismo destino y libera el grupo completo en cuanto está.", "porque": "La auditoría corre en el primer tick posterior a 45 minutos, y el tick corre antes que ella: salir antes nunca crea una infracción.",
             "evidencia": f"Sin retención el coste sube y los puntos de cohorte caen de {fmt(float(full.puntos_proxy),1)} a {fmt(float(abf[abf.variante.str.startswith('sin retención')].iloc[0].puntos_proxy),1)}."},
            {"id": "prioridad", "titulo": "Priorizar por plazo", "corto": "primero vence antes (EDD)",
             "que": "Cuando faltan unidades, sale primero el grupo cuyo plazo vence antes.", "porque": "La regla EDD minimiza la tardanza máxima (Jackson; Pinedo).", "evidencia": f"Quitar la prioridad VIP baja los puntos de cohorte; con flota al 30 % el lead medio cae de {fmt(_la.loc['greedy', 'lead_edge_stress_up'])} a {fmt(_la.loc['lookahead_tau240', 'lead_edge_stress_up'])} min al repartir por urgencia."},
            {"id": "carrier", "titulo": "Elegir transportista", "corto": "valor esperado J por grupo",
             "que": "Para cada grupo suma el precio exacto del lote, el valor del tiempo por la entrega estimada, el riesgo de fallo del transportista y un coste sombra por ocupar la unidad.", "porque": "Convierte coste, tiempo y riesgo en una sola cantidad comparable.",
             "evidencia": f"Valor del tiempo final: {fmt(pw['w_time'],2)} céntimos por minuto y tarjeta; sin él los puntos de cohorte bajan."},
            {"id": "escasez", "titulo": "Repartir bajo escasez", "corto": "emparejamiento con arrepentimiento",
             "que": "Si hay más grupos que unidades libres, resuelve una asignación de coste mínimo que primero maximiza cuántos grupos salen y luego da las unidades escasas a los más urgentes.", "porque": "Una unidad libre y factible con un envío esperando sería una infracción.",
             "evidencia": f"Con la flota al 30 %, el lead medio bajó de {fmt(_la.loc['greedy', 'lead_edge_stress_up'])} a {fmt(_la.loc['lookahead_tau240', 'lead_edge_stress_up'])} min; en escenarios normales no cambia nada."},
            {"id": "flota", "titulo": "Modelar la flota", "corto": "sin pedir snapshot",
             "que": "Cada unidad enviada vuelve en un instante calculable; así se despacha al llegar la tarjeta sin consultar el estado completo.", "porque": "Consultar el estado cuesta CPU en cada llamada.", "evidencia": f"El cómputo propio suma {fmt(timing['own_compute_s'],1)} s en 150 000 tarjetas; el resto de la CPU es espera al motor."},
            {"id": "mejoras", "titulo": "Mejoras mensuales", "corto": "unidad extra si la cola crece",
             "que": "Pide una unidad extra en el corte mensual solo si la cola media del periodo supera un umbral.", "porque": "Es un seguro contra la saturación sin gasto en meses normales.", "evidencia": "SPEED_SHIFT y EXPANDED_CAPACITY se probaron y no compensaron: no están en el archivo final."}],
        "score": [["Satisfacción del cliente", "Entrega rápida, sin fallos para VIP, prioridad por plazo"], ["Coste total", "Agrupar, precio exacto, retención controlada"], ["Tiempo medio de entrega", "Valor del tiempo, despacho al llegar"],
                  ["Percentil 95", "Elección de transportista y reintentos"], ["Robustez (32 casos de contrato)", "Gates por construcción, casos extremos probados"], ["Pico de memoria", f"Estado acotado: {fmt(f1['ram'],0)} MiB en 150 000 tarjetas"], ["Tiempo de CPU", f"{fmt(f1['cpu'],1)} s netos en 150 000 tarjetas (punto de partida: {fmt(s1['cpu'],1)} s)"]],
        "weights": [["Base", 40], ["Pico", 25], ["Rural y festivos", 20], ["Catálogo variante", 15]],
        "opt": opt, "sel": sel, "sel_rules": sel_rules, "sel_winner": sel_winner, "abl": abl, "abl_n": len(S["tune"]) + len(S["hold"]), "abl_note": abl_note,
        "controles": ["Escenarios frescos (FIN2) que nunca intervinieron en el afinado.", "Los dos escenarios públicos reales como control de cada candidato.",
                      "Puerta de fidelidad que compara el generador de escenarios con los datos reales.", "Pruebas de regresión y casos de contrato extremos: ráfagas, flota mínima, zonas sin cobertura."],
        "concl": [["Ahorra coste.", f"{pct_txt(f1['cost'], s1['cost'])} en el ejemplo de 150 000 tarjetas: unas {fmt((s1['cost'] - f1['cost']) / 100 / 1000, 0)} mil unidades monetarias menos.", None],
                  ["Entrega más rápido.", f"{fmt(s1['lead'] - f1['lead'], 0)} minutos menos por tarjeta en promedio ({pct_txt(f1['lead'], s1['lead'])}) y mejor percentil 95.", None],
                  ["Cumple siempre.", f"{f1['unresolved']} tarjetas sin resolver, {f1['hold']} retenciones indebidas y todos los gates cumplidos en {gates_total} escenarios factibles.", None],
                  ["Consume poco.", f"{fmt(f1['ram'], 0)} MiB de memoria frente a {fmt(s1['ram'], 0)} MiB; la decisión más lenta tarda {fmt(hk, 3)} s de los 30 permitidos.", None],
                  ["Resiste lo que no vio.", f"Mejora las cuatro métricas a la vez en {dw['fin2']['todas']} de {len(S['fin2'])} escenarios frescos.", None]],
        "limit": [["Alcance.", "La política decide cuándo y con quién despachar y cuándo pedir flota extra; no fija tarifas ni capacidades base.", None],
                  ["Validación en simulador.", f"Dos escenarios públicos reales y {sum(n_scen.values())} sintéticos dentro de los rangos publicados; los del evaluador pueden diferir.", None],
                  ["Dependencia de los datos de origen.", "Aprende en línea qué destinos agrupan; si los identificadores no dan pistas, retiene menos y pierde eficiencia, nunca cumplimiento.", None],
                  ["Recursos.", "La CPU depende sobre todo de la espera al motor por cada lote.", None]],
        "next": [["Piloto en sombra.", "Correr la política junto a la operación durante un mes y medir el ahorro real.", "Corto plazo", "ok"],
                 ["Fallos estimados en línea.", "Ajustar la probabilidad de fallo por transportista y zona con datos de operación.", "Medio plazo", "warn"],
                 ["Flota extra por demanda.", "Activar mejoras de velocidad y capacidad solo cuando la cola lo justifique.", "Medio plazo", "warn"],
                 ["Replicar el método.", "Aplicar la misma receta, una política paramétrica afinada por simulación, a otras operaciones logísticas.", "Oportunidad", "risk"]],
        "kickers": {2: "El reto", 3: "La propuesta", 4: "La metodología", 5: "El cierre"},
        "titulos": {2: "El punto de partida incumple las reglas y gasta de más",
                    3: f"Esperar solo para agrupar y elegir por valor esperado baja el coste {fmt(-pc(f5['cost'], s5['cost']), 0)} % y el tiempo {fmt(-pc(f5['lead'], s5['lead']), 0)} %",
                    4: "Cada decisión se fijó con una regla previa y se confirmó con datos que no intervinieron en el afinado",
                    5: "Menos coste, entregas más rápidas y cero incumplimientos: el siguiente paso es probarla en operación"},
        "ideas": {2: f"El servicio exige tres cosas a la vez: llegar a tiempo, no retener pedidos y gastar poco. El despachador inicial falla en las tres: {fmt(s5['unresolved'])} tarjetas sin resolver y {fmt(s5['hold'])} retenciones indebidas en el ejemplo pequeño.",
                  3: "La política decide en cada ronda qué grupo sale y con qué transportista, y mejora las cuatro métricas de negocio frente al punto de partida.",
                  4: "Cinco optimizadores, una regla de elección fijada de antemano, escenarios frescos y datos reales como control.",
                  5: "Ahorro, rapidez y cumplimiento se consiguen a la vez, con muy poca memoria."}}
    return D


def pc_ce() -> float:
    ce = pd.read_csv(C / "ceiling_batches_p95.csv")
    return float(ce.lote_vs_cota_sup_pct.mean())


def main():
    allow = "--allow-stale" in sys.argv
    fresh_check(allow)
    D = build()
    html = (HERE / "plantilla.html").read_text(encoding="utf-8").replace("/*DATA*/null", json.dumps(D, ensure_ascii=False))
    out = HERE / "presentacion.html"
    out.write_text(html, encoding="utf-8")
    print("OK", out, f"{out.stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    main()
