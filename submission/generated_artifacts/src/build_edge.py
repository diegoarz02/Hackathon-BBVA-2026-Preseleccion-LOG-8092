"""Escenarios EDGE (contrato / robustez / estres). Cada uno intenta romper una suposicion distinta."""
from __future__ import annotations
import json
from pathlib import Path
import scenario_gen as G

ROOT = G.REPO / "solucion" / "scenarios_mc"


def _edit_carriers(d: Path, fn):
    f = d / "carriers.json"; j = json.loads(f.read_text(encoding="utf-8")); fn(j["carriers"]); f.write_text(json.dumps(j, indent=1), encoding="utf-8")


def build(force=False):
    idx = {}
    def mk(name, n, kind, seed, post=None, **kw):
        d = ROOT / name
        if force or not (d / "scenario.toml").exists():
            meta = G.make_scenario(d, seed=seed, n=n, kind=kind, **kw)
            if post: post(d)
        else:
            meta = json.loads((d / "_meta.json").read_text())
        meta["split"] = "edge"; idx[name] = meta
    mk("edge_stress_up", 4000, "peak", 71, upgrades_enabled=True, fleet_mult=0.3)
    mk("edge_stress_noup", 4000, "peak", 71, upgrades_enabled=False, fleet_mult=0.3)
    mk("edge_stress_xl", 12000, "peak", 72, upgrades_enabled=True, fleet_mult=0.45)
    mk("edge_empty", 0, "base", 73)
    mk("edge_one", 1, "base", 74)
    mk("edge_tiny", 25, "base", 75)
    mk("edge_opaque_ids", 3000, "base", 76, id_style="opaque")
    mk("edge_no_upgrades", 3000, "base", 77, upgrades_enabled=False)
    def cap1(cs):
        for c in cs: c["batch_capacity"] = 1 if c["carrier_id"] != cs[0]["carrier_id"] else 2
    mk("edge_cap1", 2500, "base", 78, post=lambda d: _edit_carriers(d, cap1))
    def nohard(cs):
        for c in cs: c["capabilities"] = []
    mk("edge_no_hard_access", 2500, "rural_holiday", 79, post=lambda d: _edit_carriers(d, nohard))
    def nosun(cs):
        for c in cs: c["operates_sundays"] = False; c["operates_holidays"] = False
    mk("edge_all_closed_sun_hol", 2500, "rural_holiday", 80, post=lambda d: _edit_carriers(d, nosun))
    def one(cs):
        del cs[1:]
        cs[0]["allowed_zones"] = ["URBANA","SUBURBANA","RURAL","REMOTA"]
        cs[0]["zone_surcharge_cents"] = {"URBANA":0,"SUBURBANA":100,"RURAL":300,"REMOTA":600}
        cs[0]["capabilities"] = ["HARD_ACCESS"]; cs[0]["fleet_units"] = 6
    mk("edge_single_carrier", 2500, "base", 81, post=lambda d: _edit_carriers(d, one))
    def nourban(cs):
        for c in cs:
            c["allowed_zones"] = [z for z in c["allowed_zones"] if z != "REMOTA"] or ["URBANA"]
            c["zone_surcharge_cents"] = {z: c["zone_surcharge_cents"].get(z, 0) for z in c["allowed_zones"]}
    mk("edge_zone_uncovered", 2500, "rural_holiday", 82, post=lambda d: _edit_carriers(d, nourban))
    def burst(d):
        lines = (d / "shipments.csv").read_text(encoding="utf-8").splitlines()
        head, rows = lines[0], [l.split(",") for l in lines[1:]]
        t0 = "2026-01-12T10:00:00-05:00"
        out = [head]
        for i, r in enumerate(rows[:1500], start=1):
            out.append(",".join([f"S-{i:09d}", t0, r[2], r[3], f"CLU-S-{i:09d}", r[5]]))
        (d / "shipments.csv").write_text("\n".join(out) + "\n", encoding="utf-8")
    mk("edge_burst_1500", 3000, "base", 83, post=burst)
    def burst_big(d):
        lines = (d / "shipments.csv").read_text(encoding="utf-8").splitlines()
        head, rows = lines[0], [l.split(",") for l in lines[1:]]
        out = [head]
        for i, r in enumerate(rows[:600], start=1):
            out.append(",".join([f"S-{i:09d}", "2026-01-12T10:00:00-05:00", r[2], "URBANA", f"CLU-S-{i:09d}", r[5]]))
        (d / "shipments.csv").write_text(chr(10).join(out) + chr(10), encoding="utf-8")
        def big(cs):
            for c in cs:
                c["fleet_units"] = 400
                c["batch_capacity"] = max(c["batch_capacity"], 8)
        _edit_carriers(d, big)
    # 600 grupos listos a la vez con flota de sobra: atrapa bucles que despachan solo una ventana de grupos
    mk("edge_burst_bigfleet", 3000, "base", 84, post=burst_big)
    (ROOT / "index_edge.json").write_text(json.dumps(idx, indent=1), encoding="utf-8")
    return idx

if __name__ == "__main__":
    import scenario_gen
    for k, v in build().items():
        print(k, v["n"], v["carriers"], v["fleet_units"])
    for k in build():
        try: print(k, scenario_gen.validate_scenario(ROOT / k))
        except Exception as e: print(k, "INVALID", e)
