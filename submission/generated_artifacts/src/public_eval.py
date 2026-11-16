"""Evalua estrategias sobre los dos escenarios PUBLICOS, en serie (maquina quieta), con CPU neta.

 python public_eval.py baseline   -> noop + starter      -> outputs/csvs/baseline_metrics.csv
 python public_eval.py final      -> noop + starter + candidate_strategy.py (raiz) -> final_vs_baseline.csv

CPU neta = cpu_seconds - cpu_seconds(estrategia nula) medida en la misma sesion/escenario.
El evaluador usa la mediana de 3 ejecuciones; aqui: 3 en el 5k y 1 en el 150k (cada una tarda minutos).
"""
from __future__ import annotations

import json
import statistics as st
import sys
from pathlib import Path

import pandas as pd

import sim_harness as H

REPO = H.REPO
OUT = REPO / "solucion" / "outputs" / "csvs"
SCRATCH = REPO / "solucion" / "scratch" / "w"
CASES = {"public_5k": (REPO / "data", 3), "public_150k": (REPO / "scenarios" / "public_150k", 2)}
NOOP = REPO / "solucion" / "scratch" / "noop_strategy.py"
STARTER = H.HERE / "starter_baseline.py"
FINAL = REPO / "candidate_strategy.py"


def run_policy(label: str, path: Path, scen: str, reps: int) -> dict:
    data, _ = CASES[scen]
    SCRATCH.mkdir(parents=True, exist_ok=True)
    runs = []
    for r in range(reps):
        rep = SCRATCH / f"{label}_{scen}_{r}.json"
        m = H.run_engine(path, data, rep)
        keep_dir = REPO / "solucion" / "outputs" / "reports"
        keep_dir.mkdir(parents=True, exist_ok=True)
        if rep.exists():
            (keep_dir / f"{label}_{scen}.json").write_bytes(rep.read_bytes())
        runs.append(m)
        print(f"  {label} {scen} rep{r}: cpu={m.get('cpu_s')} rss={m.get('rss_mb', 0):.1f} wall={m['wall_s']:.0f}s", flush=True)
    base = dict(runs[-1])
    base["cpu_s"] = st.median(x["cpu_s"] for x in runs)
    base["rss_mb"] = st.median(x["rss_mb"] for x in runs)
    base["wall_s"] = st.median(x["wall_s"] for x in runs)
    base.update({"policy": label, "scenario": scen, "reps": reps})
    return base


def main(mode: str) -> pd.DataFrame:
    pols = {"noop": NOOP, "starter": STARTER}
    if mode == "final":
        pols["final"] = FINAL
    rows = []
    for scen, (_, reps) in CASES.items():
        for label, path in pols.items():
            rows.append(run_policy(label, path, scen, reps))
    df = pd.DataFrame(rows)
    floor = df[df.policy == "noop"].set_index("scenario")["cpu_s"]
    df["cpu_net_s"] = df.apply(lambda r: r["cpu_s"] - floor[r["scenario"]], axis=1)
    keep = ["policy", "scenario", "reps", "status", "admitted", "delivered", "returned", "unresolved", "hold_breaches",
            "sla_breach_rate", "rcp", "cost_total", "lead_mean", "lead_p95", "cpu_s", "cpu_net_s", "rss_mb",
            "wall_s", "avg_batch", "failed_attempts", "rejected_dispatches", "upg_extra"]
    out = df[keep]
    name = "baseline_metrics.csv" if mode == "baseline" else "final_vs_baseline.csv"
    out.to_csv(OUT / name, index=False)
    print(out.round(3).to_string())
    return out


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "baseline")
