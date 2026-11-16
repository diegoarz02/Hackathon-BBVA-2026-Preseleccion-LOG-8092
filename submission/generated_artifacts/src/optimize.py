"""Comparativa de optimizadores del policy (OFFLINE) en el MISMO flujo.

Todos buscan sobre el mismo espacio (8 parametros continuos del policy), con el mismo presupuesto de
evaluaciones, el mismo conjunto de escenarios y la misma funcion objetivo (``sim_harness.objective``):
  Grid (rejilla gruesa), Random, Sobol (QMC), Optuna/TPE (multivariado) y CMA-ES.
Se registra por ensayo: valor, tiempo de pared acumulado y mejor-hasta-ahora => "wall-clock-to-best".

Reanudable: tras CADA ensayo se escribe un checkpoint atomico (tmp + fsync + os.replace); al relanzar,
los ensayos hechos se reponen (Optuna: create_trial/add_trial) y se continua desde el siguiente.
Los optimizadores se ejecutan EN SERIE (cada uno usa el pool completo) para medir tiempos comparables.
"""
from __future__ import annotations

import json
import math
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import optuna
import pandas as pd
from optuna.distributions import FloatDistribution

import sim_harness as H
import tuning as T

optuna.logging.set_verbosity(optuna.logging.WARNING)

OUT = H.REPO / "solucion" / "outputs"
CKPT = OUT / "cache"
TUNE_SET = ["tune_base_0", "tune_base_1", "tune_peak_0", "tune_peak_1",
            "tune_rural_holiday_0", "tune_rural_holiday_1", "tune_catalog_0", "tune_catalog_1"]
W_NO_CPU = {"cost": 1.0, "lead": 1.0, "p95": 1.0, "rcp": 1.0, "cpu": 0.0}

# nombre: (min, max, escala_log)
SPACE = {
    "w_time": (0.5, 20.0, True),
    "w_vip": (1.0, 10.0, False),
    "w_fail": (0.0, 3.0, False),
    "vip_fail_extra": (0.0, 3000.0, False),
    "terminal_extra": (0.0, 8000.0, False),
    "w_unit": (0.0, 4.0, False),
    "unit_util_gamma": (0.0, 3.0, False),
    "hold_cap_min": (20.0, 45.0, False),
}
DISTS = {k: FloatDistribution(lo, hi, log=lg) for k, (lo, hi, lg) in SPACE.items()}


def kinds_of(names):
    return {n: n.split("_", 1)[1].rsplit("_", 1)[0] for n in names}


def load_refs():
    refs = {}
    for f in ("reference_metrics_mc.csv", "edge_first_pass.csv"):
        df = pd.read_csv(OUT / "csvs" / f)
        df = df[df.policy == "ref_price"]
        for _, r in df.iterrows():
            refs[r["scenario"]] = r.to_dict()
    return refs


class Evaluator:
    def __init__(self, cache_path: Path, pool, scenarios=TUNE_SET):
        self.cache_path, self.pool, self.scen = cache_path, pool, scenarios
        self.refs = load_refs()
        self.kinds = kinds_of(scenarios)

    def __call__(self, params: dict) -> tuple[float, dict]:
        for attempt in range(6):   # un corte (suspension/EOF) no debe tumbar la corrida: se repite el ensayo
            res = T.evaluate_many([params], self.scen, cache_path=self.cache_path, pool=self.pool)[0]
            if all("cost_total" in m for m in res.values()):
                break
            print(f"  ensayo con fallo transitorio, reintento {attempt + 1}", flush=True)
            time.sleep(20)
        else:
            raise RuntimeError("evaluacion fallida tras 6 intentos")
        val = H.weighted_objective(res, self.refs, self.kinds, W_NO_CPU)
        df = pd.DataFrame(res).T
        agg = {
            "cost_ratio": float(np.mean([res[s]["cost_total"] / self.refs[s]["cost_total"] for s in res])),
            "lead_ratio": float(np.mean([res[s]["lead_mean"] / self.refs[s]["lead_mean"] for s in res])),
            "p95_ratio": float(np.mean([res[s]["lead_p95"] / self.refs[s]["lead_p95"] for s in res])),
            "rcp": float(df.rcp.mean()),
            "gate_bad": int(((df.unresolved > 0) | (df.hold_breaches > 0) | (df.sla_breach_rate > 0.06)).sum()),
        }
        return val, agg


def atomic_write(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(obj, f)
        f.flush()
        os.fsync(f.fileno())
    for i in range(6):          # OneDrive puede bloquear el renombrado unos segundos
        try:
            os.replace(tmp, path)
            return
        except PermissionError:
            time.sleep(0.5 * (i + 1))
    os.replace(tmp, path)


def load_ckpt(name: str) -> dict:
    p = CKPT / f"opt_{name}.json"
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except ValueError:
            p.rename(p.with_suffix(".corrupto"))
    return {"trials": [], "wall_s": 0.0}


def grid_points():
    levels = {"w_time": [2.0, 6.0, 12.0], "w_fail": [0.5, 1.0, 2.0], "w_vip": [1.0, 3.0, 8.0], "w_unit": [0.0, 1.0, 3.0]}
    pts = [{}]
    for k, vs in levels.items():
        pts = [{**p, k: v} for p in pts for v in vs]
    order = np.random.default_rng(7).permutation(len(pts))   # orden barajado (como GridSampler(shuffle))
    return [pts[i] for i in order]   # 81 puntos; el resto de parametros queda en su valor por defecto


def run_optimizer(name: str, n_trials: int, seed: int, pool) -> pd.DataFrame:
    ck = load_ckpt(name)
    done = ck["trials"]
    ev = Evaluator(CKPT / f"evals_{name}.jsonl", pool)
    rng = np.random.default_rng(seed)
    study = None
    if name in ("tpe", "cmaes", "sobol"):
        if name == "tpe":
            sampler = optuna.samplers.TPESampler(seed=seed + len(done), n_startup_trials=12, multivariate=True)
        elif name == "cmaes":
            sampler = optuna.samplers.CmaEsSampler(seed=seed + len(done), n_startup_trials=0, restart_strategy=None)
        else:
            sampler = optuna.samplers.QMCSampler(qmc_type="sobol", seed=seed, scramble=True)
        study = optuna.create_study(direction="minimize", sampler=sampler)
        for rec in done:
            study.add_trial(optuna.trial.create_trial(params=rec["params"], distributions=DISTS, value=rec["value"]))
    if name == "grid":
        n_trials = min(n_trials, len(grid_points()))
    gpts = grid_points() if name == "grid" else None
    t_start = time.perf_counter() - ck["wall_s"]
    best = min([r["value"] for r in done], default=float("inf"))
    while len(done) < n_trials:
        i = len(done)
        if name == "grid":
            params, trial = gpts[i], None
        elif name == "random":
            params = {k: float(math.exp(rng.uniform(math.log(lo), math.log(hi)))) if lg else float(rng.uniform(lo, hi))
                      for k, (lo, hi, lg) in SPACE.items()}
            # reproducible al reanudar: la secuencia depende del indice
            rr = np.random.default_rng([seed, i])
            params = {k: float(math.exp(rr.uniform(math.log(lo), math.log(hi)))) if lg else float(rr.uniform(lo, hi))
                      for k, (lo, hi, lg) in SPACE.items()}
            trial = None
        else:
            trial = study.ask(DISTS)
            params = dict(trial.params)
        t0 = time.perf_counter()
        val, agg = ev(params)
        if trial is not None:
            study.tell(trial, val)
        best = min(best, val)
        wall = time.perf_counter() - t_start
        done.append({"n": i, "params": params, "value": val, "best": best, "wall_s": wall,
                     "trial_s": time.perf_counter() - t0, **agg})
        atomic_write(CKPT / f"opt_{name}.json", {"trials": done, "wall_s": wall})
        print(f"[{name}] {i + 1}/{n_trials} J={val:.4f} best={best:.4f} wall={wall:.0f}s", flush=True)
    df = pd.DataFrame(done)
    df.insert(0, "optimizer", name)
    return df


def keep_awake():
    """Windows: pide no suspender por inactividad mientras corre (ES_CONTINUOUS | ES_SYSTEM_REQUIRED)."""
    try:
        import ctypes
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000001)
    except Exception:
        pass


def main(names, n_trials=80, seed=2026, workers=8):
    keep_awake()
    with ProcessPoolExecutor(max_workers=workers) as pool:
        frames = []
        for nm in names:
            frames.append(run_optimizer(nm, n_trials, seed, pool))
    df = pd.concat(frames, ignore_index=True)
    flat = pd.json_normalize(df["params"]).add_prefix("p_")
    out = pd.concat([df.drop(columns=["params"]), flat], axis=1)
    out.to_csv(OUT / "csvs" / "optimizers_trials.csv", index=False)
    return out


if __name__ == "__main__":
    names = sys.argv[1].split(",") if len(sys.argv) > 1 else ["grid", "random", "sobol", "tpe", "cmaes"]
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 80
    main(names, n)
