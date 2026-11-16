"""Trabajador de barridos (OFFLINE). Vive en un modulo aparte para que ``spawn`` (Windows) lo pueda
reimportar; no ejecuta nada al importarse. BLAS a 1 hilo por proceso (receta de paralelismo en Windows).

Cada tarea = (parametros, escenario, fuente de la politica). Devuelve las metricas planas del motor.
"""
import os
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ.setdefault(_v, "1")

import hashlib
import json
import tempfile
from pathlib import Path

import sim_harness as H

SCEN_ROOT = H.REPO / "solucion" / "scenarios_mc"
_TMP = Path(tempfile.gettempdir()) / "bbva_sweep"


def scenario_dir(name: str) -> Path:
    p = SCEN_ROOT / name
    return p if p.exists() else (H.REPO / name)   # 'data', 'scenarios/public_150k'


def task_key(params: dict | None, scenario: str, source: str) -> str:
    src_hash = hashlib.sha1(Path(source).read_bytes()).hexdigest()[:10]
    blob = json.dumps({"p": params or {}, "s": scenario, "h": src_hash}, sort_keys=True)
    return hashlib.sha1(blob.encode()).hexdigest()[:20]


def run_one(task: dict) -> dict:
    """task = {params, scenario, source, key}. Importable y picklable (funcion de modulo)."""
    _TMP.mkdir(parents=True, exist_ok=True)
    tag = f"{os.getpid()}_{task['key']}"
    for attempt in range(3):   # fallos transitorios del motor/OS (p. ej. EOFError al cerrar el worker)
        m = H.evaluate(task.get("params"), scenario_dir(task["scenario"]), _TMP, f"{tag}_{attempt}", Path(task["source"]))
        if m.get("status") not in ("NO_REPORT", "WALL_TIMEOUT"):
            break
    m["scenario"] = task["scenario"]
    m["key"] = task["key"]
    return m
