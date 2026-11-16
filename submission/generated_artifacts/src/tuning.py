"""Orquestacion OFFLINE de evaluaciones: cache en JSONL atomico (reanudable) + pool de procesos."""
from __future__ import annotations
import json
import os
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import sim_harness as H
import sweep_worker as W

CACHE = H.REPO / "solucion" / "outputs" / "cache" / "evals.jsonl"
DEFAULT_WORKERS = 8   # cada evaluacion usa 2 procesos (motor + candidato): ~16 de 20 hilos


def load_cache(path: Path = CACHE) -> dict[str, dict]:
    out = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                r = json.loads(line)
                if r.get("status") in ("NO_REPORT", "WALL_TIMEOUT"):
                    continue   # un fallo transitorio nunca se reutiliza
                out[r["key"]] = r
            except (ValueError, KeyError):
                continue   # linea truncada por un corte: se ignora y se recalcula
    return out


def _append(path: Path, rec: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")
        f.flush()
        os.fsync(f.fileno())


def evaluate_many(candidates: list[dict | None], scenarios: list[str], source: Path = H.POLICY_SRC,
                  workers: int = DEFAULT_WORKERS, cache_path: Path = CACHE, pool: ProcessPoolExecutor | None = None,
                  verbose: bool = False) -> list[dict[str, dict]]:
    """Devuelve, por candidato, {escenario: metricas}. Reanuda desde la cache; escribe cada resultado al llegar."""
    cache = load_cache(cache_path)
    tasks, order = [], []
    for ci, params in enumerate(candidates):
        for s in scenarios:
            key = W.task_key(params, s, str(source))
            order.append((ci, s, key))
            if key not in cache and not any(t["key"] == key for t in tasks):
                tasks.append({"params": params, "scenario": s, "source": str(source), "key": key})
    own = pool is None
    if tasks:
        pool = pool or ProcessPoolExecutor(max_workers=workers)
        t0 = time.time()
        futs = {pool.submit(W.run_one, t): t for t in tasks}
        done = 0
        for f in as_completed(futs):
            m = f.result()
            cache[m["key"]] = m
            _append(cache_path, m)
            done += 1
            if verbose and done % 10 == 0:
                print(f"  {done}/{len(tasks)} ({time.time() - t0:.0f}s)", flush=True)
        if own:
            pool.shutdown()
    res: list[dict[str, dict]] = [dict() for _ in candidates]
    for ci, s, key in order:
        res[ci][s] = cache[key]
    return res
