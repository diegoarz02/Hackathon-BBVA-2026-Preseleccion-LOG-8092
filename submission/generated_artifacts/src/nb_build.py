"""Construye y ejecuta los notebooks de solucion/notebooks con nbformat + nbclient.

 python nb_build.py 01 [02 03 04 05]   (sin args: todos)
Los notebooks LEEN resultados ya calculados (CSV/JSON en outputs/) y producen tablas y figuras (modulo ``figs``);
los calculos pesados viven en scripts reanudables (optimize*.py, robust_*.py, public_eval.py, ...).
"""
from __future__ import annotations

import sys
from pathlib import Path

import nbformat as nbf
from nbclient import NotebookClient

HERE = Path(__file__).resolve().parent
NB_DIR = HERE.parent / "notebooks"

SETUP = '''
import sys, json, warnings
from pathlib import Path
import numpy as np, pandas as pd
import matplotlib.pyplot as plt
from IPython.display import display
warnings.filterwarnings("ignore")
ROOT = Path("..").resolve()                 # solucion/
REPO = ROOT.parent
sys.path.insert(0, str(ROOT / "src"))
import plotstyle as PS, figs
PS.apply()
CSV, FIG = ROOT / "outputs" / "csvs", ROOT / "outputs" / "figs"
pd.set_option("display.width", 200); pd.set_option("display.max_columns", 40)
def show(fig):
    display(fig); plt.close(fig)
'''


def md(t):
    from estilo import limpiar
    return nbf.v4.new_markdown_cell(limpiar(t.strip("\n")))


def code(t):
    return nbf.v4.new_code_cell(t.strip("\n"))


def build(name: str, cells: list) -> Path:
    nb = nbf.v4.new_notebook()
    nb.cells = cells
    nb.metadata["kernelspec"] = {"display_name": "Python 3", "language": "python", "name": "python3"}
    path = NB_DIR / name
    NB_DIR.mkdir(parents=True, exist_ok=True)
    NotebookClient(nb, timeout=1800, kernel_name="python3", resources={"metadata": {"path": str(NB_DIR)}}).execute()
    nbf.write(nb, path)
    return path


def nb01():
    c = [md("""
# 01 · EDA del simulador y baseline (LOG-8092)

**Qué hace:** entiende los dos escenarios públicos (5 k y 150 k tarjetas), mide el *starter* tal cual en las 7 métricas de la evaluación y
diagnostica por qué incumple los gates. Todo medido sobre el motor real. Datos: `data/` y `scenarios/public_150k/`.
Resultados del starter: `outputs/csvs/baseline_metrics.csv`.
"""), code(SETUP), code('''
sh = {}
for name, p in [("5k", REPO/"data"/"shipments.csv"), ("150k", REPO/"scenarios"/"public_150k"/"shipments.csv")]:
    d = pd.read_csv(p); d["t"] = pd.to_datetime(d.available_at.str.slice(0,19))
    d["csz"] = d.groupby("delivery_cluster_id").shipment_id.transform("size")
    sh[name] = d
summ = pd.DataFrame({k: {"envíos": len(d), "clusters": d.delivery_cluster_id.nunique(),
    "% en cluster multi": round(100*(d.csz>1).mean(),1), "% metal": round(100*d.is_metal.mean(),1),
    "VIP %": round(100*(d["product"]=="VIP_BLACK").mean(),1), "REMOTA %": round(100*(d.zone=="REMOTA").mean(),1),
    "envíos/día": round(len(d)/90,0)} for k, d in sh.items()})
summ
'''), md("""
## Perfil de llegadas y mezcla
La demanda sigue un perfil semanal × horario (picos 15–18 h, lunes y viernes, domingo ≈ ¼) y la mezcla producto × zona es casi idéntica entre zonas.
Es lo que reproduce `src/scenario_gen.py` para el Monte Carlo de escenarios.
"""), code('''
show(figs.eda_arrivals(sh["150k"]))
'''), md("""
## Clusters: lo que permite (y limita) agrupar
Un lote solo admite tarjetas del mismo `delivery_cluster_id`, zona e intento. Los clusters multi-tarjeta (2–4) llegan **dentro de 45 min** (la ventana de retención) y
su identificador tiene una forma distinta (`CLU-E…` vs `CLU-S-…`). La política **no** hardcodea ese patrón: lo aprende en línea.
"""), code('''
show(figs.eda_clusters(sh["150k"]))
d = sh["150k"]; first = d.drop_duplicates("delivery_cluster_id")
print("tamaño de cluster por forma de id:")
print(pd.crosstab(first.delivery_cluster_id.str.replace(r"\\d+", "#", regex=True), first.csz))
'''), md("""
## Catálogo de carriers: coste y ETA por zona
`ida = ceil(km·60·10⁴ / (km/h · mult))`, ETA = pickup + ida; la unidad queda ocupada pickup + 2·ida.
"""), code('''
car = json.load(open(REPO/"data"/"carriers.json"))["carriers"]
dist = {"URBANA":12,"SUBURBANA":35,"RURAL":80,"REMOTA":150}
rows = []
for c in car:
    for z in c["allowed_zones"]:
        ida = -(-dist[z]*600000 // (c["speed_kmh"]*10000))
        rows.append({"carrier": c["carrier_id"], "zona": z, "ETA_min": c["pickup_minutes"]+ida, "ocupa_min": c["pickup_minutes"]+2*ida,
                     "precio_1_tarjeta": c["base_fee_cents"]+c["zone_surcharge_cents"][z], "HARD_ACCESS": "HARD_ACCESS" in c["capabilities"],
                     "op_fail_bps": c["operational_failure_bps"], "unidades": c["fleet_units"]})
cat = pd.DataFrame(rows)
show(figs.eda_catalog(cat))
cat.round(1)
'''), md("""
## Baseline: el starter tal cual (rival a vencer)
Medido con `src/public_eval.py` (motor real, en serie, máquina quieta). CPU neta = CPU − CPU de una estrategia nula (el piso del motor).
"""), code('''
bm = pd.read_csv(CSV/"baseline_metrics.csv")
bm
'''), code('''
diag = []
for scen in ["public_5k", "public_150k"]:
    r = json.load(open(ROOT/"outputs"/"reports"/f"starter_{scen}.json"))
    diag.append({"escenario": scen.replace("public_", ""), "UNRESOLVED": r["counts"]["unresolved"], "infracciones_retencion": r["counts"]["voluntary_hold_breaches"],
                 "despachos_rechazados": r["counts"]["rejected_dispatches"], "lote_medio": r["batching"]["average_batch_size"],
                 "CAPABILITY_UNSUPPORTED": r["diagnostics"]["dispatch_rejections"]["CAPABILITY_UNSUPPORTED"],
                 "ZONE_UNSUPPORTED": r["diagnostics"]["dispatch_rejections"]["ZONE_UNSUPPORTED"],
                 "coste/ref": round(r["costs"]["total_cents"]/r["costs"]["reference_budget_cents"],2)})
diag = pd.DataFrame(diag); show(figs.baseline_diag(diag)); diag
'''), md("""
### Diagnóstico de los fallos del starter (verificado en el código y en el reporte)
1. **Round-robin de 1 tarjeta por lote** → `average_batch_size = 1,0`: nunca aprovecha que el linehaul se cobra por lote (coste ≈ +46 % sobre la referencia).
2. **Reintento al mismo carrier tras `INACCESSIBLE_ROUTE`**: `last_carrier_by_shipment` fija el carrier original aunque no tenga `HARD_ACCESS`
   → `CAPABILITY_UNSUPPORTED` repetido y, al final, **UNRESOLVED** (incumple el gate).
3. **Chequeo de zona por subcadena** (`shipment.zone in "|".join(zonas)`): `"URBANA" in "SUBURBANA"` es verdadero → intentos a carriers que no cubren la zona (`ZONE_UNSUPPORTED`).
4. **Retención involuntaria**: examina cada tarjeta una vez por tick con un carrier fijo; si no cabe, la deja pendiente aunque haya otro carrier libre → **infracciones de retención** (gate).
5. **`all_historical_records`** guarda todos los envíos (memoria ∝ nº de tarjetas: ≈ 113 MiB en 150 k vs ≈ 28 MiB de piso).
""")]
    return build("01_eda_simulador.ipynb", c)


def nb03(prefix="v2", tag="") -> Path:
    """Comparativa de optimizadores. prefix '' = 1.a corrida; 'v2' = re-tuning con la estructura final."""
    csvname = "optimizers_trials.csv"
    out_cmp = "optimizers_comparison.csv"
    title = "03 · Tuning del policy: comparativa de optimizadores en el MISMO flujo" if not prefix else \
        "03 · Re-ajuste de la política: comparativa de cinco optimizadores sobre la estructura y el objetivo finales"
    suf = ""
    c = [md(f"""
# {title}

**Pregunta:** ¿qué optimizador encuentra mejores parámetros del policy, y con qué coste de cómputo?
**Diseño (idéntico para todos):** mismo espacio de parámetros continuos (`SPACE` en `src/optimize{'2' if prefix else ''}.py`), 60 evaluaciones,
8 escenarios TUNE (2 por tipo: base, pico, rural-festivos, catálogo), misma función objetivo, semilla 2026. Cada evaluación ejecuta el **motor real**.
Optimizadores: Grid (rejilla gruesa barajada), Random, Sobol (QMC), Optuna/TPE (multivariado) y CMA-ES. Corrida **reanudable** con checkpoints atómicos
(`outputs/cache/`); sobrevivió a varias suspensiones de la laptop.

**Función objetivo (minimizar), por escenario**, referencia R = política "más barata inmediata":
`J = coste/coste_R + lead/lead_R + p95/p95_R + (10−RCP)/(10−RCP_R) + penalización dura por gate violado (+100 c/u)`, agregada con pesos de negocio
base 40 / pico 25 / rural-festivos 20 / catálogo 15.{" En la 2.ª corrida se suma una **penalización de dominancia sobre el starter** (con márgenes: coste −10 %, lead −8 %, p95 −1,5 %, RCP mayor)." if prefix else ""}
CPU no entra en el tuning (es ruidosa); se mide aparte en serie.
"""), code(SETUP), code(f'''
tr = pd.read_csv(CSV/"{csvname}")
order = ["grid","random","sobol","tpe","cmaes"]
J_THR = {"3.50" if not prefix else "float(tr.value.min()) * 1.01"}   # umbral comparable: 1 % por encima del mejor valor global
rows = []
for o in order:
    d = tr[tr.optimizer==o].sort_values("n").reset_index(drop=True)
    b = d.loc[d.value.idxmin()]
    reach = d[d.value <= J_THR]
    rows.append({{"optimizador": o, "ensayos": len(d), "mejor_J": round(b.value,4), "ensayo_del_mejor": int(b.n)+1,
                 "wall_a_mejor_s": round(b.wall_s), "tiempo_medio_ensayo_s": round(d.trial_s.mean(),1),
                 "J_medio_top5": round(d.nsmallest(5, "value").value.mean(),4), "J_mediana_ensayos": round(d.value.median(),3),
                 "ensayos_hasta_J<=umbral": (int(reach.n.iloc[0])+1 if len(reach) else None),
                 "coste/ref": round(b.cost_ratio,3), "lead/ref": round(b.lead_ratio,3), "p95/ref": round(b.p95_ratio,3), "rcp": round(b.rcp,3),
                 "gates_violados_en_mejor": int(b.gate_bad)}})
cmp_ = pd.DataFrame(rows)
cmp_.to_csv(CSV/"{out_cmp}", index=False)
print("umbral J =", round(J_THR, 4))
cmp_
'''), md("""
> **Cómo leer la tabla.** `wall_a_mejor_s` mezcla la velocidad del optimizador **y** la de la máquina (cambió ×1,5–1,8 entre sesiones: ver `tiempo_medio_ensayo_s`).
> Por eso se reporta también `ensayo_del_mejor` y `ensayos_hasta_J<=umbral`, que no dependen de la máquina.
"""), code(f'''
show(figs.opt_convergence(tr, order, name="opt_convergencia{suf}.png"))
'''), code(f'''
show(figs.opt_frontier(tr, order, name="opt_frontera_y_distribucion{suf}.png"))
'''), md("""
### Sensibilidad: ¿qué parámetros importan?
Correlación de Spearman entre cada parámetro y J en los ensayos con todos los parámetros libres (random, sobol, tpe, cmaes).
"""), code(f'''
pc = [c for c in tr.columns if c.startswith("p_")]
a = tr[tr.optimizer.isin(["random","sobol","tpe","cmaes"])]
sens = a[pc+["value"]].corr(method="spearman")["value"].drop("value").rename(lambda s: s[2:]).sort_values()
show(figs.opt_sensitivity(sens, name="opt_sensibilidad{suf}.png"))
sens.round(2)
'''), md("""
### Qué muestra
El paisaje es casi plano: la diferencia entre el mejor y la mediana de cada método es pequeña frente a la variación **entre escenarios**; lo que mueve J es el intercambio
coste ↔ tiempo (`w_time`). Los métodos dirigidos (TPE, CMA-ES) y el cuasi-aleatorio (Sobol) rinden más por ensayo que Grid/Random. Como las diferencias entre los mejores son
pequeñas, **no se elige por J de TUNE**: los mejores de cada método pasan a robustez (notebook 04) con HOLD intacto y los casos de contrato.
""")]
    return build("03_tuning_optuna_random_grid_cmaes.ipynb", c)


if __name__ == "__main__":
    which = sys.argv[1:] or ["01", "02", "03", "04", "05"]
    for w in which:
        fn = globals().get(f"nb{w}") or getattr(__import__(f"nb_build{w}"), f"nb{w}")
        print(w, fn())
