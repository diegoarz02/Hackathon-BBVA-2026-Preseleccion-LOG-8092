"""Re-ejecuta los comandos de validacion con el archivo FINAL y mide el hook mas lento (copia instrumentada, 150 k).
Escribe outputs/csvs/reverify_commands.json y hook_timing.json. Uso: python final_checks.py [ruta_candidate]"""
import json, os, subprocess, sys, time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
C = REPO / "solucion" / "outputs" / "csvs"

def run(cmd, label):
    t0 = time.time()
    p = subprocess.run(cmd, cwd=str(REPO), capture_output=True, text=True)
    return {"comando": label, "codigo_salida": p.returncode, "segundos": round(time.time() - t0, 1), "ultima_linea": (p.stdout.strip().splitlines() or [""])[-1].replace(str(REPO) + chr(92), "")[:160]}

if __name__ == "__main__":
    py = sys.executable
    rows = []
    for label, cmd, rep in [("python run.py", [py, "run.py"], "performance_report.json"),
                            ("python -S run.py", [py, "-S", "run.py"], "performance_report.json"),
                            ("python run_150k.py", [py, "run_150k.py"], "performance_report_150k.json"),
                            ("python -m unittest discover -s tests", [py, "-m", "unittest", "discover", "-s", "tests"], None)]:
        r = run(cmd, label)
        if rep:
            j = json.loads((REPO / "output" / rep).read_text(encoding="utf-8"))
            r["estado"] = j["status"]; r["integridad"] = j["integrity"]["protected_files_pristine"]
            r["UNRESOLVED"] = j["counts"]["unresolved"]; r["retencion"] = j["counts"]["voluntary_hold_breaches"]; r["SLA"] = j["sla"]["breach_rate"]
        else:
            r["estado"] = "OK" if r["codigo_salida"] == 0 else "FALLO"; r["ultima_linea"] = (subprocess.run(cmd, cwd=str(REPO), capture_output=True, text=True).stderr.strip().splitlines() or [""])[-1]
        rows.append(r); print(r, flush=True)
    (C / "reverify_commands.json").write_text(json.dumps(rows, indent=1, ensure_ascii=False), encoding="utf-8")
    # hook timing (150 k) con copia instrumentada
    subprocess.run([py, str(REPO / "solucion/scratch/make_timing.py")], cwd=str(REPO), check=True)
    out = REPO / "solucion/scratch/tstats.json"
    env = dict(os.environ, TSTATS_OUT=str(out))
    subprocess.run([py, str(REPO / "solucion/src/engine_cli.py"), "--data", str(REPO / "scenarios/public_150k"), "--strategy", str(REPO / "solucion/scratch/cand_timing.py"),
                    "--output", str(REPO / "solucion/scratch/o_timing.json")], cwd=str(REPO), env=env, capture_output=True)
    d = json.loads(out.read_text()); st, mx = d["st"], d["max"]
    hooks = ["on_shipments_available", "on_dispatch_tick", "on_delivery_failed", "on_delivery_succeeded", "on_monthly_planning"]
    own = sum(st[h][0] for h in hooks if h in st) - st["svc.dispatch_batch"][0] - st.get("svc.snapshot", [0, 0])[0]
    timing = {"max_hook_s": max(mx[h] for h in hooks if h in mx), "svc_dispatch_calls": st["svc.dispatch_batch"][1],
              "svc_dispatch_us_per_call": 1e6 * st["svc.dispatch_batch"][0] / st["svc.dispatch_batch"][1], "own_compute_s": own,
              "hook_totals_s": {h: st[h][0] for h in hooks if h in st}, "nota": "tiempos de pared dentro de los hooks (copia instrumentada, 150 k); el max incluye esperas al motor"}
    (C / "hook_timing.json").write_text(json.dumps(timing, indent=1), encoding="utf-8"); print(timing)
