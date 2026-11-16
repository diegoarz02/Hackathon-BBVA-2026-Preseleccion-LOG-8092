"""Seleccion final (2.a corrida): gates + dominancia estricta sobre el starter (HOLD y FINAL) + proxy de cohorte;
si el mejor no supera de forma ROBUSTA al incumbente (bootstrap pareado), se conserva el incumbente (no cambiar por cambiar)."""
import json
import numpy as np, pandas as pd
import optimize2 as O2, robustness as R, sim_harness as H, proxy as PX

C = H.REPO / "solucion" / "outputs" / "csvs"

def load():
    cand = pd.read_csv(C / "v2_robustness_candidates.csv")
    allr = pd.read_csv(C / "robustness_results_all.csv")
    fv = pd.read_csv(C / "final_validation_results.csv")
    fixed = pd.concat([allr[allr.candidate.isin(["starter", "ref_price", "ref_eta", "ref_mix"])], fv[fv.candidate.isin(["starter", "ref_price", "ref_eta", "ref_mix"])]], ignore_index=True)
    fixed = fixed.drop_duplicates(["candidate", "scenario"])
    return pd.concat([cand, fixed], ignore_index=True), json.load(open(C / "v2_candidates.json"))

def main():
    df, params = load()
    scen_hold = sorted(s for s in df.scenario.unique() if s.startswith("hold_"))
    scen_final = sorted(s for s in df.scenario.unique() if s.startswith("final_"))
    scen_edge = [s for s in df.scenario.unique() if s.startswith("edge_") and s not in R.INFEASIBLE]
    st = df[df.candidate == "starter"].set_index("scenario")
    refs = R.reference_rows(df)
    cands = [c for c in params]
    rows = []
    for c in cands:
        g = df[df.candidate == c].set_index("scenario")
        def dom(sc):
            h, s = g.loc[sc], st.loc[sc]
            return bool(((h.cost_total < s.cost_total) & (h.lead_mean < s.lead_mean) & (h.lead_p95 < s.lead_p95) & (h.rcp > s.rcp)).all())
        kinds = lambda sc: {s: O2.kinds_of([s])[s] for s in sc}
        rows.append({"candidato": c,
                     "gates_HOLD": int(sum(R.gate_ok(g.loc[s]) for s in scen_hold)), "gates_FINAL": int(sum(R.gate_ok(g.loc[s]) for s in scen_final)),
                     "gates_EDGE": int(sum(R.gate_ok(g.loc[s]) for s in scen_edge)), "hold_breaches": int(g.hold_breaches.sum()),
                     "domina_HOLD": dom(scen_hold), "domina_FINAL": dom(scen_final),
                     "J_HOLD": H.weighted_objective({s: g.loc[s].to_dict() for s in scen_hold}, refs, kinds(scen_hold), O2.W_NO_CPU),
                     "J_FINAL": H.weighted_objective({s: g.loc[s].to_dict() for s in scen_final}, refs, kinds(scen_final), O2.W_NO_CPU)})
    t = pd.DataFrame(rows)
    cohort = cands + ["starter", "ref_price", "ref_eta", "ref_mix"]
    P = PX.cohort_points(df, scen_hold + scen_final, cohort)
    t = t.merge(P[["total_negocio"]].rename(columns={"total_negocio": "puntos_proxy"}), left_on="candidato", right_index=True)
    t["elegible"] = (t.gates_HOLD == len(scen_hold)) & (t.gates_FINAL == len(scen_final)) & (t.gates_EDGE == len(scen_edge)) & (t.hold_breaches == 0) & t.domina_HOLD & t.domina_FINAL
    t["J_medio"] = (t.J_HOLD + t.J_FINAL) / 2
    t = t.sort_values("puntos_proxy", ascending=False).reset_index(drop=True)
    t.to_csv(C / "v2_selection.csv", index=False)
    el = t[t.elegible]
    best = el.iloc[0]["candidato"] if len(el) else "incumbente"
    # bootstrap pareado de PUNTOS POR ESCENARIO (el mecanismo real de evaluacion) vs incumbente, sobre HOLD+FINAL
    from scipy.stats import rankdata
    sc = scen_hold + scen_final
    cnt = {}
    for s in sc:
        cnt[PX.kind_of(s)] = cnt.get(PX.kind_of(s), 0) + 1
    wk = np.array([PX.W[PX.kind_of(s)] / cnt[PX.kind_of(s)] for s in sc])
    pts = {c: [] for c in cohort}
    for s in sc:
        g = df[df.scenario == s].drop_duplicates("candidate").set_index("candidate").reindex(cohort)
        tot = np.zeros(len(cohort))
        for m, higher in PX.METRICS:
            v = g[m].values.astype(float); v = -v if higher else v
            r = rankdata(v, method="average"); n = len(v); tot += 20 * (100 * (n - r) / (n - 1)) / 100
        for c, x in zip(cohort, tot):
            pts[c].append(x)
    P_ = {c: np.array(v) for c, v in pts.items()}
    rng = np.random.default_rng(5)
    rob = {}
    for c in cands:
        if c == "incumbente":
            continue
        d = P_[c] - P_["incumbente"]
        idx = np.arange(len(d))
        bs = [np.average(d[b], weights=wk[b]) for b in (rng.choice(idx, len(idx)) for _ in range(4000))]
        lo, hi = np.percentile(bs, [2.5, 97.5])
        rob[c] = {"dPuntos_medio": float(np.average(d, weights=wk)), "IC95": [float(lo), float(hi)], "gana_en": int((d > 0).sum()), "n": int(len(d))}
    elig = [c for c in t[t.elegible].candidato if c != "incumbente"]
    robust = [c for c in elig if rob[c]["IC95"][0] > 0]
    robust.sort(key=lambda c: -rob[c]["dPuntos_medio"])
    shortlist = robust[:3]
    best = shortlist[0] if shortlist else "incumbente"
    decision = {"regla": "elegible (gates + dominancia HOLD y FINAL) y mejora ROBUSTA en puntos por escenario vs incumbente (IC95 inferior > 0)",
                "robustez_puntos_vs_incumbente": rob, "shortlist_a_confirmar_en_FIN2": shortlist,
                "ganador_provisional": best, "conservar_incumbente": not shortlist,
                "params_ganador": params[best], "params_shortlist": {c: params[c] for c in shortlist}}
    json.dump(decision, open(C / "v2_decision.json", "w"), indent=1)
    pd.set_option("display.width", 250)
    print(t.round(3).to_string()); print(json.dumps({k: v for k, v in decision.items() if not k.startswith("params")}, indent=1))

if __name__ == "__main__":
    main()
