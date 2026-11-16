"""Puntos esperados en una COHORTE SIMULADA (proxy, no el calculo del evaluador): regla de percentiles de EVALUACION.md
(percentil = 100*(n-r)/(n-1), puntos = 20*percentil/100, empates con rango medio) por escenario y metrica de negocio,
ponderando los tipos de escenario 40/25/20/15."""
from __future__ import annotations
import numpy as np
import pandas as pd
from scipy.stats import rankdata

W = {"base": 0.40, "peak": 0.25, "rural_holiday": 0.20, "catalog": 0.15}
METRICS = [("cost_total", False), ("lead_mean", False), ("lead_p95", False), ("rcp", True)]   # (metrica, mayor_es_mejor)


def kind_of(s: str) -> str:
    return s.split("_", 1)[1].rsplit("_", 1)[0]


def cohort_points(df: pd.DataFrame, scenarios: list[str], cohort: list[str]) -> pd.DataFrame:
    """df con columnas candidate, scenario y las metricas. Devuelve puntos por metrica y total (max 80)."""
    acc = {c: {m: {} for m, _ in METRICS} for c in cohort}
    for s in scenarios:
        g = df[df.scenario == s].drop_duplicates("candidate").set_index("candidate").reindex(cohort)
        if g[[m for m, _ in METRICS]].isna().any().any():
            continue
        for m, higher in METRICS:
            v = g[m].values.astype(float)
            v = -v if higher else v
            r = rankdata(v, method="average")
            n = len(v)
            p = 20 * (100 * (n - r) / (n - 1)) / 100
            for c, x in zip(cohort, p):
                acc[c][m].setdefault(kind_of(s), []).append(x)
    out = {}
    for c in cohort:
        row = {}
        for m, _ in METRICS:
            byk = acc[c][m]
            row[m] = sum(W[k] * np.mean(v) for k, v in byk.items()) / sum(W[k] for k in byk)
        out[c] = row
    P = pd.DataFrame(out).T
    P["total_negocio"] = P.sum(axis=1)
    return P.sort_values("total_negocio", ascending=False)
