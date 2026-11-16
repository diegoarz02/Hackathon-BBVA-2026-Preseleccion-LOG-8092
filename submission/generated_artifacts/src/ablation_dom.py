"""Ablacion por DOMINANCIA y puntos proxy (lo que realmente se uso para elegir), reutilizando la cache de evaluaciones."""
import json, numpy as np, pandas as pd
import ablation_v2 as A, optimize2 as O2, robustness as R, sim_harness as H, tuning as T, proxy as PX, v2data as V
C = H.REPO / "solucion/outputs/csvs/"
best = json.load(open(C / "v2_decision.json"))["params_ganador"]
tune, hold, _ = R.scenario_lists(); scen = tune + hold
cands = {k: {**best, **v} for k, v in A.VARIANTS.items()}
res = T.evaluate_many(list(cands.values()), scen, source=H.HERE / "policy_v2.py", cache_path=H.REPO / "solucion/outputs/cache/evals_ablation_v2.jsonl", pool=None)
allr = pd.read_csv(C / "robustness_results_all.csv")
rows = []
for name, r in zip(cands, res):
    for s in scen:
        m = dict(r[s]); m["candidate"] = name; m["scenario"] = s; rows.append(m)
df = pd.DataFrame(rows)
fixed = allr[allr.candidate.isin(["starter", "ref_price", "ref_eta", "ref_mix"]) & allr.scenario.isin(scen)]
full = pd.concat([df, fixed], ignore_index=True)
st = fixed[fixed.candidate == "starter"].set_index("scenario").loc[scen]
cohort = list(cands) + ["starter", "ref_price", "ref_eta", "ref_mix"]
P = PX.cohort_points(full, scen, cohort)
out = pd.read_csv(C / "ablation_final.csv")
dom, d_cost, d_lead = [], [], []
for v in out.variante:
    g = df[df.candidate == v].set_index("scenario").loc[scen]
    dom.append(int(((g.cost_total < st.cost_total) & (g.lead_mean < st.lead_mean) & (g.lead_p95 < st.lead_p95) & (g.rcp > st.rcp)).sum()))
out["domina_starter_de_28"] = dom
out["puntos_proxy"] = [P.loc[v, "total_negocio"] for v in out.variante]
out.to_csv(C / "ablation_final.csv", index=False)
print(out[["variante", "J", "gates_malos", "domina_starter_de_28", "puntos_proxy"]].round(2).to_string())
