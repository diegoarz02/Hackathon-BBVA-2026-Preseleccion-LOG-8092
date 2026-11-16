"""Compara estadisticas de llegadas entre los datos publicos y los escenarios sinteticos (fidelidad del generador)."""
import sys, json
import numpy as np, pandas as pd
from pathlib import Path
REPO = Path(__file__).resolve().parents[2]

def stats(p):
    d = pd.read_csv(p); d["t"] = pd.to_datetime(d.available_at.str.slice(0, 19))
    n = len(d); cs = d.groupby("delivery_cluster_id").shipment_id.transform("size")
    g = d.groupby("delivery_cluster_id").t.agg(["min", "max", "size"]); g = g[g["size"] > 1]
    off = []
    for cid, x in d.groupby("delivery_cluster_id"):
        if len(x) > 1:
            t = np.sort(x.t.values); off += list(((t - t[0]).astype("timedelta64[s]").astype(float) / 60)[1:])
    out = {"n": n, "share_multi": (cs > 1).mean(), "metal": d.is_metal.mean(), "mean_size": g["size"].mean(),
           "off_p25": np.percentile(off, 25), "off_p50": np.percentile(off, 50), "off_p75": np.percentile(off, 75), "off_max": max(off)}
    for pr, v in d["product"].value_counts(normalize=True).items(): out["p_" + pr] = v
    for z, v in d["zone"].value_counts(normalize=True).items(): out["z_" + z] = v
    h = d.t.dt.hour.value_counts(normalize=True).sort_index()
    out["h_night(0-5)"] = h[h.index < 6].sum(); out["h_peak(9-12)"] = h[(h.index >= 9) & (h.index < 12)].sum(); out["h_eve(18-21)"] = h[(h.index >= 18) & (h.index < 21)].sum()
    w = d.t.dt.dayofweek.value_counts(normalize=True); out["dow_sat"] = w.get(5, 0); out["dow_sun"] = w.get(6, 0)
    days = (d.t.max() - d.t.min()).days + 1; out["per_day"] = n / days
    return out

if __name__ == "__main__" and "--gate" not in sys.argv:
    rows = {"pub5k": stats(REPO / "data/shipments.csv"), "pub150k": stats(REPO / "scenarios/public_150k/shipments.csv")}
    idx = json.loads((REPO / "solucion/scenarios_mc/index.json").read_text())
    for k in sys.argv[1:] or ["tune_base_0", "hold_base_1", "hold_peak_1", "tune_rural_holiday_0", "tune_catalog_1"]:
        rows[k] = stats(REPO / "solucion/scenarios_mc" / k / "shipments.csv")
    print(pd.DataFrame(rows).round(3).to_string())


def gate(tol_off_min: float = 4.0) -> bool:
    """Puerta de fidelidad: los escenarios sinteticos (no edge, n >= 1500) deben reproducir los desfases de llegada dentro del cluster
    (cuartiles) de los datos publicos con tolerancia ``tol_off_min`` minutos en la MEDIA de cada cuartil. Devuelve True si pasa."""
    ref = stats(REPO / "data/shipments.csv"); ref2 = stats(REPO / "scenarios/public_150k/shipments.csv")
    target = {k: (ref[k] + ref2[k]) / 2 for k in ("off_p25", "off_p50", "off_p75")}
    idx = json.loads((REPO / "solucion/scenarios_mc/index.json").read_text())
    got = {k: [] for k in target}
    for name, meta in idx.items():
        if meta.get("n", 0) < 1500:
            continue
        s = stats(REPO / "solucion/scenarios_mc" / name / "shipments.csv")
        for k in target:
            got[k].append(s[k])
    ok = True
    for k, v in target.items():
        m = float(np.mean(got[k])); good = abs(m - v) <= tol_off_min; ok &= good
        print(f"{k}: publico {v:.1f} min | sinteticos {m:.1f} min | {'OK' if good else 'FALLA'}")
    return ok

if __name__ == "__main__" and "--gate" in sys.argv:
    raise SystemExit(0 if gate() else 1)
