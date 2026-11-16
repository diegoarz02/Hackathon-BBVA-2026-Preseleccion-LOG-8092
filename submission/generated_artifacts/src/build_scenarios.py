"""Construye los conjuntos de escenarios sinteticos: TUNE (afinar), HOLD (decision final, intacto),
EDGE (contrato/robustez). Reproducible: semillas fijas."""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
import scenario_gen as G

ROOT = G.REPO / "solucion" / "scenarios_mc"
KINDS = ["base", "peak", "rural_holiday", "catalog"]


def build(force=False):
    index = {}
    for split, seed0, per_kind in (("tune", 1000, 3), ("hold", 9000, 4), ("final", 12000, 4), ("fin2", 15000, 4)):
        rng = np.random.default_rng(seed0)
        for k in KINDS:
            for i in range(per_kind):
                seed = seed0 + KINDS.index(k) * 100 + i
                n = int(rng.integers(2000, 5000)) if split == "tune" else int(rng.integers(2500, 9000))
                name = f"{split}_{k}_{i}"
                d = ROOT / name
                if force or not (d / "scenario.toml").exists():
                    meta = G.make_scenario(d, seed=seed, n=n, kind=k)
                else:
                    meta = json.loads((d / "_meta.json").read_text())
                meta["split"] = split
                index[name] = meta
    (ROOT / "index.json").write_text(json.dumps(index, indent=1), encoding="utf-8")
    return index


if __name__ == "__main__":
    idx = build()
    for k, v in idx.items():
        print(k, v["n"], v["carriers"], v["fleet_units"], "upg" if v["upgrades_enabled"] else "---",
              "cl%.2f" % v["cluster_share"], v["peaks"][:1] if v["peaks"] else "")
