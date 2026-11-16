"""Carga unificada de resultados de la 1.a y 2.a corrida (cada cifra de los informes sale de aqui -> de un CSV)."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

C = Path(__file__).resolve().parents[1] / "outputs" / "csvs"
METRICS = ["cost_total", "lead_mean", "lead_p95", "rcp"]


def _r(name):
    return pd.read_csv(C / name)


def load():
    """Devuelve dict con DataFrames indexados por escenario para: final (2.a corrida), run1 (1.a corrida), starter, ref_price, ref_eta, ref_mix."""
    allr = _r("robustness_results_all.csv")
    fv = _r("final_validation_results.csv")
    f2 = _r("fin2_results.csv")
    ff = _r("final_file_validation.csv")
    out = {"final": ff[ff.candidate == "final_file"].set_index("scenario")}
    run1 = pd.concat([allr[allr.candidate == "wt6_la240_up"], fv[fv.candidate == "final"], f2[f2.candidate == "incumbente"]], ignore_index=True)
    out["run1"] = run1.drop_duplicates("scenario").set_index("scenario")
    for k in ("starter", "ref_price", "ref_eta", "ref_mix"):
        x = pd.concat([allr[allr.candidate == k], fv[fv.candidate == k], f2[f2.candidate == k]], ignore_index=True)
        out[k] = x.drop_duplicates("scenario").set_index("scenario")
    return out


def scen_sets(d):
    s = sorted(d["final"].index)
    return {"tune": [x for x in s if x.startswith("tune_")], "hold": [x for x in s if x.startswith("hold_")],
            "edge": [x for x in s if x.startswith("edge_")], "final": [x for x in s if x.startswith("final_")],
            "fin2": [x for x in s if x.startswith("fin2_")]}


INFEASIBLE = {"edge_zone_uncovered", "edge_no_hard_access", "edge_burst_1500", "edge_empty", "edge_one"}


def gate_ok(r) -> bool:
    return bool(r.status == "COMPLETED" and r.unresolved == 0 and r.hold_breaches == 0 and r.sla_breach_rate <= 0.06)


def dominance(a: pd.DataFrame, b: pd.DataFrame, names: list[str]) -> dict:
    """a domina a b (a mejor en las 4 metricas) en cuantos escenarios."""
    x, y = a.loc[names], b.loc[names]
    w = {"coste": int((x.cost_total < y.cost_total).sum()), "lead": int((x.lead_mean < y.lead_mean).sum()),
         "p95": int((x.lead_p95 < y.lead_p95).sum()), "RCP": int((x.rcp > y.rcp).sum())}
    w["todas"] = int(((x.cost_total < y.cost_total) & (x.lead_mean < y.lead_mean) & (x.lead_p95 < y.lead_p95) & (x.rcp > y.rcp)).sum())
    return w


def mean_delta(a: pd.DataFrame, b: pd.DataFrame, names: list[str]) -> dict:
    x, y = a.loc[names], b.loc[names]
    return {"coste_pct": float(100 * (x.cost_total / y.cost_total - 1).mean()), "lead_pct": float(100 * (x.lead_mean / y.lead_mean - 1).mean()),
            "p95_pct": float(100 * (x.lead_p95 / y.lead_p95 - 1).mean()), "rcp_d": float((x.rcp - y.rcp).mean())}
