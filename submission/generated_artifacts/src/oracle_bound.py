"""Cota de la espera para agrupar: un ORACULO que conoce el tamano real de cada cluster (lo lee del CSV del escenario; no es una estrategia
valida) frente al archivo final. Acota cuanto podria mejorar cualquier regla de espera mas inteligente. Escribe outputs/csvs/techo_retencion_oraculo.csv."""
import csv
import os
import pandas as pd
import sim_harness as H, sweep_worker as W

C = H.REPO / "solucion" / "outputs" / "csvs"
SC = ["tune_base_0", "tune_peak_1", "tune_rural_holiday_0", "tune_catalog_1", "hold_base_1", "hold_peak_2"]
WORK = H.REPO / "solucion" / "scratch" / "w"


def make_oracle() -> object:
    t = (H.REPO / "candidate_strategy.py").read_text(encoding="utf-8")
    t = t.replace("import heapq\nfrom collections import deque", "import heapq, os, csv\nfrom collections import deque", 1)
    t = t.replace("        self.p = dict(PARAMS)", "        self.p = dict(PARAMS)\n        self._truth = {}\n        _f = os.environ.get('ORACLE_CSV')\n        if _f:\n            for _r in csv.DictReader(open(_f, encoding='utf-8')):\n                self._truth[_r['delivery_cluster_id']] = self._truth.get(_r['delivery_cluster_id'], 0) + 1", 1)
    old = '''                full = self._max_size and seen + 1 >= self._max_size
                if not full and ((seen >= 1 and p["hold_second"])
                                 or (seen == 0 and self._p_multi(shape) >= p["hold_p_min"])):'''
    assert old in t
    t = t.replace(old, "                full = seen + 1 >= self._truth.get(cid, 1)\n                if not full:", 1)
    old2 = '        elif p["hold_full_release"] and self._max_size and len(g.members) >= self._max_size:'
    assert old2 in t
    t = t.replace(old2, "        elif len(g.members) >= self._truth.get(cid, 1):", 1)
    out = H.REPO / "solucion" / "scratch" / "policy_oracle.py"
    out.write_text(t, encoding="utf-8")
    return out


if __name__ == "__main__":
    WORK.mkdir(parents=True, exist_ok=True)
    orc = make_oracle()
    rows = []
    for s in SC:
        d = W.scenario_dir(s)
        os.environ["ORACLE_CSV"] = str(d / "shipments.csv")
        o = H.run_engine(orc, d, WORK / f"orc_{s}.json")
        os.environ.pop("ORACLE_CSV", None)
        c = H.run_engine(H.REPO / "candidate_strategy.py", d, WORK / f"cur_{s}.json")
        rows.append({"scenario": s, "coste_pct": round(100 * (o["cost_total"] / c["cost_total"] - 1), 2), "lead_pct": round(100 * (o["lead_mean"] / c["lead_mean"] - 1), 2),
                     "p95_pct": round(100 * (o["lead_p95"] / c["lead_p95"] - 1), 2), "rcp_delta": round(o["rcp"] - c["rcp"], 4), "lote_oraculo": o["avg_batch"], "lote_final": c["avg_batch"]})
    t = pd.DataFrame(rows)
    t.to_csv(C / "techo_retencion_oraculo.csv", index=False)
    print(t.to_string()); print(t[["coste_pct", "lead_pct", "p95_pct"]].mean().round(2))
