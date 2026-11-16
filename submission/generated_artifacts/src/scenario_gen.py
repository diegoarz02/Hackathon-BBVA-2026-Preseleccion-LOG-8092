"""Generador OFFLINE de escenarios sinteticos LOG-8092 (Monte Carlo de escenarios).

Reproduce las estadisticas medidas en los dos escenarios publicos (perfil horario/semanal,
mezcla producto x zona, metal, clusters de 2-4 tarjetas con llegadas en <= 45 min) y las
perturba DENTRO de ``[scenario_ranges]`` de rules.toml:
  - 4-6 carriers, precios/velocidades/capacidades/flota/disponibilidad variables,
  - pico de llegadas hasta x2,5 (max_arrival_peak_multiplier_bps = 25000),
  - 20-50 % de tarjetas en clusters (min/max_clustered_shipments_bps),
  - influencer 1-5 %  (cambia rules.toml -> [rcp].influencer_rate_bps),
  - festivos variables, zonas rurales/remotas con mas peso, mejoras on/off.

No usa ni lee nada del evaluador: es una reconstruccion estadistica de lo PUBLICO.
Cada escenario es una carpeta con los 5 inputs que valida el motor (sin manifest).
"""

from __future__ import annotations

import copy
import hashlib
import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
PUBLIC_5K = REPO / "data"
LIMA = timezone(timedelta(hours=-5))
START = datetime(2026, 1, 5, 0, 0, 0, tzinfo=LIMA)  # lunes
ADMISSION_DAYS = 90

PRODUCTS = ["STANDARD", "SME", "BUSINESS", "VIP_BLACK"]
P_PRODUCT = np.array([0.549, 0.220, 0.181, 0.050])
ZONES = ["URBANA", "SUBURBANA", "RURAL", "REMOTA"]
P_ZONE_BASE = np.array([0.581, 0.251, 0.119, 0.049])
P_ZONE_RURAL = np.array([0.34, 0.24, 0.26, 0.16])

# Perfil medido en el publico de 150k (llegadas/hora relativas, martes-jueves = 1,0 en horas punta)
HOUR_W = np.array([6.2, 6.8, 6.8, 6.7, 6.3, 6.5, 40, 40, 124, 119, 121, 121, 112, 112, 114,
                   139, 139, 138, 138, 94, 94, 93, 45, 45], dtype=float)
DOW_W = np.array([148.0, 124.0, 124.0, 124.0, 152.0, 71.0, 35.0]) / 124.0  # lun..dom


def _hourly_rate(rng: np.random.Generator, night_factor: float, peaks: list[tuple[int, int, float]]) -> np.ndarray:
    hours = ADMISSION_DAYS * 24
    rate = np.empty(hours)
    hw = HOUR_W.copy()
    hw[:6] *= night_factor
    for h in range(hours):
        day, hod = divmod(h, 24)
        rate[h] = DOW_W[day % 7] * hw[hod]
    for (start_day, length, mult) in peaks:
        a, b = start_day * 24, min(hours, (start_day + length) * 24)
        rate[a:b] *= mult
    return rate / rate.sum()


def _make_shipments(rng: np.random.Generator, n: int, cluster_share: float, p_zone: np.ndarray,
                    rate: np.ndarray, id_style: str) -> list[tuple]:
    """Devuelve filas (available_at_seconds, product, zone, cluster_id, is_metal)."""
    if n == 0:
        return []
    clustered = int(round(n * cluster_share))
    sizes = []
    left = clustered
    while left >= 2:
        k = int(rng.integers(2, 5))
        k = min(k, left)
        if k < 2:
            break
        sizes.append(k)
        left -= k
    n_clustered = sum(sizes)
    n_single = n - n_clustered
    events = [(1, True)] * n_single + [(k, False) for k in sizes]  # (size, singleton)
    n_events = len(events)
    hour_idx = rng.choice(len(rate), size=n_events, p=rate)
    # en segundos desde START; los clusters necesitan 45 min de holgura antes del cierre
    horizon = ADMISSION_DAYS * 86400
    t0 = hour_idx * 3600 + rng.integers(0, 3600, size=n_events)
    rows = []
    cl_seq = 0
    for ev, (size, single), t in zip(range(n_events), events, t0):
        zone = ZONES[int(rng.choice(4, p=p_zone))]
        if single:
            offsets = [0]
        else:
            t = min(int(t), horizon - 2700 - 1)
            # llegadas de los miembros ~ U(1 s, 45 min) desde la primera (medido en los datos publicos: p25/p50/p75 = 11.3/22.5/33.9 min)
            offsets = sorted([0] + [int(x) for x in rng.integers(1, 2701, size=size - 1)])
            # evita duplicados exactos de segundo dentro del cluster
            for i in range(1, len(offsets)):
                if offsets[i] <= offsets[i - 1]:
                    offsets[i] = offsets[i - 1] + 1
        if not single:
            cl_seq += 1
        for off in offsets:
            prod = PRODUCTS[int(rng.choice(4, p=P_PRODUCT))]
            metal = bool(rng.random() < (0.61 if prod == "VIP_BLACK" else 0.016))
            rows.append([int(t) + off, prod, zone, None if single else cl_seq, metal])
    rows.sort(key=lambda r: r[0])
    out = []
    for i, r in enumerate(rows, start=1):
        sid = f"S-{i:09d}"
        if r[3] is None:
            cid = {"public": f"CLU-S-{i:09d}", "opaque": f"D{i:09d}"}[id_style]
        else:
            cid = {"public": f"CLU-E{r[3]:09d}", "opaque": f"D{(10**8) + r[3]:09d}"}[id_style]
        out.append((r[0], sid, r[1], r[2], cid, r[4]))
    return out


# ----------------------------------------------------------------------------------------------
# Catalogo de carriers
# ----------------------------------------------------------------------------------------------
def _load_public_carriers() -> list[dict]:
    return json.loads((PUBLIC_5K / "carriers.json").read_text(encoding="utf-8"))["carriers"]


def _perturb_catalog(rng: np.random.Generator, scale: float, variant: bool, n_carriers: int) -> list[dict]:
    base = _load_public_carriers()
    cats = copy.deepcopy(base)
    names = ["ALFA_LOG", "BRAVO_EXP", "CONDOR_CARGO", "DELTA_POST", "ECHO_FLEET", "FOX_MOTO"]
    if variant:
        for i, c in enumerate(cats):
            f = lambda lo, hi: float(rng.uniform(lo, hi))
            c["base_fee_cents"] = max(60, int(c["base_fee_cents"] * f(0.65, 1.5)))
            for z in list(c["zone_surcharge_cents"]):
                c["zone_surcharge_cents"][z] = max(0, int(c["zone_surcharge_cents"][z] * f(0.6, 1.6)))
            c["speed_kmh"] = max(10, int(c["speed_kmh"] * f(0.7, 1.35)))
            c["pickup_minutes"] = max(3, int(c["pickup_minutes"] * f(0.6, 1.6)))
            c["batch_capacity"] = max(2, int(c["batch_capacity"] * f(0.6, 1.6)))
            c["operational_failure_bps"] = int(min(900, max(10, c["operational_failure_bps"] * f(0.5, 1.8))))
            c["night_multiplier_bps"] = int(rng.choice([10000, 12000, 15000, 18000]))
            c["holiday_multiplier_bps"] = int(rng.choice([10000, 14000, 18000, 22000]))
            c["operates_sundays"] = bool(rng.random() < (0.85 if "HARD_ACCESS" in c["capabilities"] else 0.4))
            c["operates_holidays"] = bool(c["operates_sundays"] and rng.random() < 0.8)
            c["fleet_units"] = max(1, int(round(c["fleet_units"] * f(0.55, 1.6))))
        # reasigna zonas/capabilities para variar cobertura (siempre cubriendo todas las zonas)
        hard_idx = list(rng.choice(len(cats), size=int(rng.integers(1, 3)), replace=False))
        for i, c in enumerate(cats):
            c["capabilities"] = ["HARD_ACCESS"] if i in hard_idx else []
    # numero de carriers 4-6
    if n_carriers < len(cats):
        keep = list(rng.choice(len(cats), size=n_carriers, replace=False))
        cats = [cats[i] for i in sorted(keep)]
    elif n_carriers > len(cats):
        extra = copy.deepcopy(cats[int(rng.integers(0, len(cats)))])
        extra["carrier_id"] = names[0]
        extra["display_name"] = names[0].replace("_", " ").title()
        extra["base_fee_cents"] = int(extra["base_fee_cents"] * rng.uniform(0.8, 1.3))
        extra["speed_kmh"] = max(10, int(extra["speed_kmh"] * rng.uniform(0.8, 1.25)))
        cats.append(extra)
    # fleet escalada con la demanda
    for c in cats:
        c["fleet_units"] = max(1, int(round(c["fleet_units"] * scale)))
    # garantias minimas de factibilidad (cobertura de zonas y HARD_ACCESS en rural/remota)
    _ensure_coverage(cats)
    # ids/orden sin semantica
    if variant:
        order = list(rng.permutation(len(cats)))
        cats = [cats[i] for i in order]
        for c in cats:
            if rng.random() < 0.5:
                new = names[int(rng.integers(0, len(names)))] + f"_{int(rng.integers(1, 99))}"
                c["carrier_id"], c["display_name"] = new, new.replace("_", " ").title()
    ids = set()
    for c in cats:  # ids unicos
        while c["carrier_id"] in ids:
            c["carrier_id"] += "X"
        ids.add(c["carrier_id"])
    return cats


def _ensure_coverage(cats: list[dict]) -> None:
    allz = ZONES
    def covered(z, need_hard=False):
        return any(z in c["allowed_zones"] and (not need_hard or "HARD_ACCESS" in c["capabilities"]) for c in cats)
    # el carrier de mayor cobertura cubre todo y tiene HARD_ACCESS
    big = max(cats, key=lambda c: len(c["allowed_zones"]))
    for z in allz:
        if not covered(z, need_hard=z in ("RURAL", "REMOTA")):
            tgt = big
            if z not in tgt["allowed_zones"]:
                tgt["allowed_zones"].append(z)
                tgt["zone_surcharge_cents"][z] = {"URBANA": 0, "SUBURBANA": 150, "RURAL": 400, "REMOTA": 800}[z]
            if z in ("RURAL", "REMOTA") and "HARD_ACCESS" not in tgt["capabilities"]:
                tgt["capabilities"] = ["HARD_ACCESS"]
    for c in cats:
        order = [z for z in allz if z in c["allowed_zones"]]
        c["allowed_zones"] = order
        c["zone_surcharge_cents"] = {z: c["zone_surcharge_cents"].get(z, 0) for z in order}


# ----------------------------------------------------------------------------------------------
def make_scenario(out_dir: Path, seed: int, n: int, kind: str = "base", *, id_style: str = "public",
                  upgrades_enabled: bool | None = None, fleet_mult: float = 1.0) -> dict:
    """Crea una carpeta de escenario. kind in {base, peak, rural_holiday, catalog}."""
    rng = np.random.default_rng(seed)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    cluster_share = float(rng.uniform(0.20, 0.50))
    night_factor = float(rng.choice([0.0, 0.5, 1.0]))
    p_zone = P_ZONE_BASE
    peaks: list[tuple[int, int, float]] = []
    n_hol = 2
    variant = False
    infl_bps = 300
    if kind == "peak":
        for _ in range(int(rng.integers(1, 4))):
            peaks.append((int(rng.integers(0, ADMISSION_DAYS - 10)), int(rng.integers(3, 11)),
                          float(rng.uniform(1.8, 2.5))))
    if kind == "rural_holiday":
        p_zone = P_ZONE_RURAL
        n_hol = int(rng.integers(5, 10))
        infl_bps = int(rng.integers(100, 501))
    if kind == "catalog":
        variant = True
        infl_bps = int(rng.integers(100, 501))
    if kind == "base":
        infl_bps = int(rng.integers(100, 501)) if rng.random() < 0.5 else 300

    rate = _hourly_rate(rng, night_factor, peaks)
    rows = _make_shipments(rng, n, cluster_share, p_zone, rate, id_style)

    # festivos: fechas unicas dentro de la admision (y algunas de los dias posteriores)
    span_days = ADMISSION_DAYS + 14
    hol_days = sorted(rng.choice(span_days, size=n_hol, replace=False).tolist())
    holidays = [(START + timedelta(days=int(d))).date() for d in hol_days]

    n_car = int(rng.integers(4, 7)) if kind in ("catalog", "rural_holiday") else (5 if kind != "peak" else int(rng.integers(4, 7)))
    scale = max(0.05, n / 5000.0) * (float(rng.uniform(0.7, 1.15)) if kind == "peak" else float(rng.uniform(0.85, 1.25)))
    scale *= fleet_mult
    carriers = _perturb_catalog(rng, scale, variant or kind == "peak", n_car)
    if upgrades_enabled is None:
        upgrades_enabled = bool(rng.random() < 0.6) if kind != "peak" else bool(rng.random() < 0.8)

    # ---- escritura ----
    with (out_dir / "shipments.csv").open("w", encoding="utf-8", newline="") as f:
        f.write("shipment_id,available_at,product,zone,delivery_cluster_id,is_metal\n")
        for (t, sid, prod, zone, cid, metal) in rows:
            ts = (START + timedelta(seconds=int(t))).isoformat()
            f.write(f"{sid},{ts},{prod},{zone},{cid},{'true' if metal else 'false'}\n")
    (out_dir / "carriers.json").write_text(
        json.dumps({"carriers": carriers, "note": "Escenario sintetico OFFLINE.", "schema_version": "0.2.0"},
                   indent=2, sort_keys=True), encoding="utf-8")
    (out_dir / "holidays.csv").write_text(
        "date,name\n" + "".join(f"{d.isoformat()},Festivo sintetico {i + 1}\n" for i, d in enumerate(holidays)),
        encoding="utf-8")
    rules = (PUBLIC_5K / "rules.toml").read_text(encoding="utf-8")
    rules = rules.replace("influencer_rate_bps = 300", f"influencer_rate_bps = {infl_bps}")
    (out_dir / "rules.toml").write_text(rules, encoding="utf-8")
    fingerprint = hashlib.sha256(f"synthetic|{kind}|{seed}|{n}".encode()).hexdigest()
    sid_name = f"SYN-{kind.upper()}-{seed:05d}"
    (out_dir / "scenario.toml").write_text(
        'schema_version = "0.2.0"\nspec_version = "0.4.0"\n'
        f'scenario_id = "{sid_name}"\nsimulation_start = "{START.isoformat()}"\n'
        f"admission_days = {ADMISSION_DAYS}\nreference_budget_cents = {n * 600}\n"
        f'resource_profile = "MEASURED_RESOURCES"\nupgrades_enabled = {"true" if upgrades_enabled else "false"}\n'
        f'seed_fingerprint = "sha256:{fingerprint}"\n', encoding="utf-8")
    meta = {
        "scenario": sid_name, "kind": kind, "seed": seed, "n": len(rows), "carriers": len(carriers),
        "cluster_share": round(cluster_share, 3), "night_factor": night_factor, "peaks": peaks,
        "holidays": [d.isoformat() for d in holidays], "upgrades_enabled": upgrades_enabled,
        "influencer_bps": infl_bps, "id_style": id_style, "fleet_units": sum(c["fleet_units"] for c in carriers),
    }
    (out_dir / "_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return meta


def validate_scenario(out_dir: Path) -> None:
    """Pasa por el validador del propio motor (carga estricta + stream de envios)."""
    import sys
    sys.path.insert(0, str(REPO / "engine"))
    from log8092_engine.config import load_config, stream_shipments
    cfg = load_config(Path(out_dir))
    n = sum(1 for _ in stream_shipments(cfg))
    return n


if __name__ == "__main__":
    import sys
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else REPO / "solucion" / "scenarios_mc" / "demo"
    print(make_scenario(out, seed=1, n=2000, kind="peak"))
    print("validado, envios:", validate_scenario(out))
