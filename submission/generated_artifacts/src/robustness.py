"""Paso 4 (OFFLINE): robustez por Monte Carlo de escenarios y seleccion del ganador.

Evalua candidatos (parametros de ``policy.py``) + referencias + starter sobre
  - TUNE (12), HOLD (16, nunca usados para afinar) y EDGE (14 casos de contrato/estres).
Metricas por escenario -> ``robustness_results.csv``. La seleccion usa SOLO HOLD(+EDGE para gates).

Criterio de seleccion (en este orden):
  1. cumple TODOS los gates en TODOS los escenarios factibles de HOLD/EDGE (los infactibles por
     construccion -zona sin cobertura, sin HARD_ACCESS, rafaga mayor que la flota- se marcan aparte);
  2. menor objetivo J agregado (40/25/20/15) en HOLD;
  3. entre candidatos empatados dentro del ruido (``tol``), el mas simple (menos parametros desviados
     del valor neutro) y el de menor CPU neta.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

import optimize as O
import sim_harness as H
import tuning as T

OUT = H.REPO / "solucion" / "outputs"
ROOT = H.REPO / "solucion" / "scenarios_mc"
INFEASIBLE = {"edge_zone_uncovered", "edge_no_hard_access", "edge_burst_1500", "edge_empty", "edge_one"}


def scenario_lists():
    tune = [k for k in json.loads((ROOT / "index.json").read_text()) if k.startswith("tune_")]
    hold = [k for k in json.loads((ROOT / "index.json").read_text()) if k.startswith("hold_")]
    edge = list(json.loads((ROOT / "index_edge.json").read_text()))
    return tune, hold, edge


def top_params(name: str, k: int = 3) -> list[dict]:
    ck = O.load_ckpt(name)
    trials = sorted(ck["trials"], key=lambda r: r["value"])[:k]
    return [t["params"] for t in trials]


def run(cands: dict[str, dict | None], scenarios: list[str], source=H.POLICY_SRC, cache=None, pool=None):
    names = list(cands)
    res = T.evaluate_many([cands[n] for n in names], scenarios, source=source,
                          cache_path=cache or T.CACHE, pool=pool)
    rows = []
    for n, r in zip(names, res):
        for s, m in r.items():
            rows.append({"candidate": n, **m})
    return pd.DataFrame(rows)


def gate_ok(row) -> bool:
    return (row["status"] == "COMPLETED" and row["unresolved"] == 0 and row["hold_breaches"] == 0
            and row["sla_breach_rate"] <= 0.06)


def contract_ok(row) -> bool:
    """Contrato (robustez): termina bien, sin errores y sin retencion indebida."""
    return row["status"] == "COMPLETED" and row["hold_breaches"] == 0


def aggregate_J(df: pd.DataFrame, refs: dict, scen: list[str]) -> pd.Series:
    kinds = O.kinds_of(scen)
    out = {}
    for cand, g in df.groupby("candidate"):
        per = {r["scenario"]: r.to_dict() for _, r in g.iterrows() if r["scenario"] in scen}
        if len(per) == len(scen):
            out[cand] = H.weighted_objective(per, refs, kinds, O.W_NO_CPU)
    return pd.Series(out)


if __name__ == "__main__":
    pass


# ----------------------------------------------------------------------------------------------
def policy_candidates(df: pd.DataFrame) -> list[str]:
    return [c for c in df.candidate.unique() if not c.startswith("ref_") and c != "starter"]


def reference_rows(df: pd.DataFrame, ref: str = "ref_price") -> dict:
    return {r["scenario"]: r.to_dict() for _, r in df[df.candidate == ref].iterrows()}


def complexity(params: dict | None, default: dict) -> int:
    """Numero de parametros desviados del valor neutro del archivo: proxy de complejidad."""
    return sum(1 for k, v in (params or {}).items() if abs(v - default.get(k, 0)) > 1e-12)


def select_winner(df: pd.DataFrame, cand_params: dict, default: dict, tol: float = 0.01):
    """Aplica el criterio de seleccion. Devuelve (tabla ordenada, nombre del ganador)."""
    refs = reference_rows(df)
    hold = sorted(s for s in df.scenario.unique() if s.startswith("hold_"))
    tune = sorted(s for s in df.scenario.unique() if s.startswith("tune_"))
    edge = sorted(s for s in df.scenario.unique() if s.startswith("edge_"))
    edge_ok = [s for s in edge if s not in INFEASIBLE]
    rows = []
    for c in policy_candidates(df):
        g = df[df.candidate == c].set_index("scenario")
        rows.append({
            "candidato": c,
            "gates_HOLD": int(sum(gate_ok(g.loc[s]) for s in hold)), "n_HOLD": len(hold),
            "gates_EDGE_factibles": int(sum(gate_ok(g.loc[s]) for s in edge_ok)), "n_EDGE": len(edge_ok),
            "contrato_todos": int(sum(contract_ok(g.loc[s]) for s in hold + tune + edge)), "n_contrato": len(hold + tune + edge),
            "J_HOLD": H.weighted_objective({s: g.loc[s].to_dict() for s in hold}, refs, O.kinds_of(hold), O.W_NO_CPU),
            "J_TUNE": H.weighted_objective({s: g.loc[s].to_dict() for s in tune}, refs, O.kinds_of(tune), O.W_NO_CPU),
            "complejidad": complexity(cand_params.get(c), default),
        })
    t = pd.DataFrame(rows)
    t["elegible"] = (t.gates_HOLD == t.n_HOLD) & (t.gates_EDGE_factibles == t.n_EDGE) & (t.contrato_todos == t.n_contrato)
    el = t[t.elegible]
    best = el.J_HOLD.min()
    ties = el[el.J_HOLD <= best * (1 + tol)].sort_values(["complejidad", "J_HOLD"])
    return t.sort_values("J_HOLD").reset_index(drop=True), (ties.iloc[0]["candidato"] if len(ties) else None), ties
