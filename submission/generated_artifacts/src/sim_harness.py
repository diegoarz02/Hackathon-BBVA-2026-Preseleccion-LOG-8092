"""Harness OFFLINE: ejecuta el motor publico sobre un escenario con una estrategia/parametros
dados y devuelve metricas + el escalar objetivo del tuning.

Principios
 - Se ejecuta el MOTOR REAL (engine/) mediante ``engine_cli.py`` en un subproceso; nada se simula
   por separado, asi que lo medido es exactamente lo que mide el evaluador (salvo el hardware).
 - La estrategia candidata se materializa como un archivo: ``policy.py`` con el bloque
   ``PARAMS = {...}`` reemplazado por los parametros de la evaluacion (lo que se afina es
   literalmente el codigo que se congela despues).

Funcion objetivo (MINIMIZAR), por escenario s, con referencia R_s = politica "mas barata inmediata":

    J_s =  w_c * costo/costo_R  + w_t * lead_medio/lead_R + w_p * p95/p95_R
         + w_r * (10 - rcp)/(10 - rcp_R)  + w_cpu * cpu/cpu_R
         + PENALIZACIONES DURAS de gates (cada violacion suma 100 + magnitud)

 - Las cuatro metricas de negocio pesan igual (cada una vale 20 puntos en la evaluacion).
 - CPU entra con peso propio (otros 20 puntos); la memoria se mide aparte (casi constante).
 - Normalizar por R_s hace comparables escenarios de tamano distinto; los pesos de negocio
   por tipo de escenario (base 40/pico 25/rural-festivos 20/catalogo 15) se aplican al agregar.
 - Gates: UNRESOLVED > 0, SLA > 6 %, voluntary_hold_breaches > 0, status != COMPLETED,
   wall > 15 min. Cada uno suma una penalizacion enorme -> nunca se prefiere violar un gate.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
ENGINE_CLI = HERE / "engine_cli.py"
POLICY_SRC = HERE / "policy.py"

WEIGHTS = {"cost": 1.0, "lead": 1.0, "p95": 1.0, "rcp": 1.0, "cpu": 1.0}
GATE_PENALTY = 100.0
SCENARIO_WEIGHTS = {"base": 0.40, "peak": 0.25, "rural_holiday": 0.20, "catalog": 0.15}


# ----------------------------------------------------------------------------------------------
def materialize_candidate(params: dict | None, dest: Path, source: Path = POLICY_SRC) -> Path:
    """Escribe una copia de ``source`` con ``PARAMS`` reemplazado (merge sobre los defaults)."""
    text = source.read_text(encoding="utf-8")
    if params:
        marker = re.search(r"^PARAMS\s*=\s*\{.*?^\}\s*$", text, re.S | re.M)
        if not marker:
            raise RuntimeError("no se encontro el bloque PARAMS en la politica")
        text = text[:marker.start()] + "PARAMS = " + repr(_merged(text, params)) + text[marker.end():]
    dest.write_text(text, encoding="utf-8")
    return dest


def _merged(text: str, overrides: dict) -> dict:
    ns: dict = {}
    m = re.search(r"^PARAMS\s*=\s*(\{.*?^\})\s*$", text, re.S | re.M)
    base = eval(m.group(1), {}, ns)  # literal de diccionario del propio archivo
    unknown = set(overrides) - set(base)
    if unknown:
        raise KeyError(f"parametros desconocidos: {sorted(unknown)}")
    base.update(overrides)
    return base


def run_engine(candidate: Path, data_dir: Path, out_json: Path, python: str | None = None,
               timeout: float = 1800.0, extra_args: list[str] | None = None) -> dict:
    """Ejecuta el motor y devuelve un dict de metricas planas (incluye wall-clock)."""
    candidate, data_dir, out_json = (Path(p).resolve() for p in (candidate, data_dir, out_json))
    cmd = [python or sys.executable, str(ENGINE_CLI), "--data", str(data_dir),
           "--strategy", str(candidate), "--output", str(out_json), *(extra_args or [])]
    t0 = time.perf_counter()
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=str(REPO))
    except subprocess.TimeoutExpired:
        return {"status": "WALL_TIMEOUT", "wall_s": time.perf_counter() - t0}
    wall = time.perf_counter() - t0
    if not out_json.exists():
        return {"status": "NO_REPORT", "wall_s": wall, "stderr": proc.stderr[-500:]}
    return flatten_report(json.loads(out_json.read_text(encoding="utf-8")), wall)


def flatten_report(r: dict, wall_s: float = float("nan")) -> dict:
    c, s, rc, lt = r["counts"], r["sla"], r["rcp"], r["lead_time_minutes"]
    adm = max(1, c["admitted"])
    out = {
        "status": r["status"], "wall_s": wall_s, "scenario_id": r["scenario"]["scenario_id"],
        "admitted": c["admitted"], "delivered": c["delivered"], "returned": c["returned_to_vault"],
        "unresolved": c["unresolved"], "hold_breaches": c["voluntary_hold_breaches"],
        "rejected_dispatches": c["rejected_dispatches"], "attempts": c["accepted_attempts"],
        "batches": c["accepted_batches"], "failed_attempts": c["failed_attempts"],
        "sla_breach_rate": s["breach_rate"] if s["breach_rate"] is not None else 0.0,
        "sla_breached": s["breached"],
        "rcp": rc["weighted_score"], "rcp_unweighted": rc["unweighted_score"],
        "cost_total": r["costs"]["total_cents"], "cost_dispatch": r["costs"]["dispatch_cents"],
        "cost_upgrade": r["costs"]["upgrade_cents"], "cost_penalty": r["costs"]["penalty_cents"],
        "cost_ref": r["costs"]["reference_budget_cents"],
        "lead_mean": lt["mean"], "lead_p50": lt["p50"], "lead_p95": lt["p95"], "lead_max": lt["max"],
        "cpu_s": r["resources"]["cpu_seconds"], "rss_mb": r["resources"]["peak_rss_bytes"] / 1048576,
        "avg_batch": r["batching"]["average_batch_size"],
        "pristine": r["integrity"]["protected_files_pristine"],
        "upg_extra": r["upgrades"]["accepted_quantity_by_type"]["EXTRA_UNIT"],
        "upg_speed": r["upgrades"]["accepted_quantity_by_type"]["SPEED_SHIFT"],
        "upg_cap": r["upgrades"]["accepted_quantity_by_type"]["EXPANDED_CAPACITY"],
        "status_detail": r["diagnostics"].get("status_detail"),
    }
    for p, v in s["by_product"].items():
        out[f"sla_{p}"] = v["breach_rate"] if v["breach_rate"] is not None else 0.0
    out["fail_rate"] = r["failures"]["attempt_failure_rate"]
    return out


def gate_violations(m: dict) -> dict:
    """Magnitud de cada violacion de gate (0 = cumple)."""
    v = {}
    v["status"] = 0 if m.get("status") == "COMPLETED" else 1
    v["unresolved"] = int(m.get("unresolved", 0) or 0)
    v["sla"] = max(0.0, float(m.get("sla_breach_rate", 1.0)) - 0.06) * 100
    v["hold"] = int(m.get("hold_breaches", 0) or 0)
    v["wall"] = 1 if m.get("wall_s", 0) > 900 else 0
    return v


def objective(m: dict, ref: dict, w: dict | None = None, cpu_ref_floor: float = 0.0) -> float:
    """Escalar a MINIMIZAR para un escenario. ``ref`` = metricas de la referencia en ese escenario."""
    w = w or WEIGHTS
    if m.get("status") not in ("COMPLETED",) or m.get("lead_mean") is None or m.get("rcp") is None:
        return 1e6
    g = gate_violations(m)
    pen = sum(GATE_PENALTY * (1 + val) for val in g.values() if val > 0)
    cpu_net = max(0.05, m["cpu_s"] - cpu_ref_floor)
    cpu_ref_net = max(0.05, ref["cpu_s"] - cpu_ref_floor)
    j = (w["cost"] * m["cost_total"] / ref["cost_total"]
         + w["lead"] * m["lead_mean"] / ref["lead_mean"]
         + w["p95"] * m["lead_p95"] / ref["lead_p95"]
         + w["rcp"] * (10 - m["rcp"]) / max(1e-6, 10 - ref["rcp"])
         + w["cpu"] * cpu_net / cpu_ref_net)
    return j + pen


def weighted_objective(per_scenario: dict[str, dict], refs: dict[str, dict], kinds: dict[str, str],
                       w: dict | None = None) -> float:
    """Agregado ponderado por tipo de escenario (40/25/20/15), media dentro de cada tipo."""
    by_kind: dict[str, list[float]] = {}
    for name, m in per_scenario.items():
        by_kind.setdefault(kinds[name], []).append(objective(m, refs[name], w))
    total = 0.0
    wsum = 0.0
    for k, vals in by_kind.items():
        total += SCENARIO_WEIGHTS.get(k, 0.25) * (sum(vals) / len(vals))
        wsum += SCENARIO_WEIGHTS.get(k, 0.25)
    return total / wsum if wsum else 1e6


def evaluate(params: dict | None, data_dir: Path, work: Path, tag: str, source: Path = POLICY_SRC) -> dict:
    """Atajo: materializa, ejecuta y limpia. Devuelve metricas."""
    work.mkdir(parents=True, exist_ok=True)
    cand = work / f"cand_{tag}.py"
    out = work / f"rep_{tag}.json"
    materialize_candidate(params, cand, source)
    m = run_engine(cand, data_dir, out)
    for p in (cand, out):
        try:
            p.unlink()
        except OSError:
            pass
    return m
