# solucion/: resultados y respaldo del reto LOG-8092

El único archivo evaluado es `submission/candidate_strategy.py` (biblioteca estándar de Python); su versión de trabajo está en `../candidate_strategy.py`. Esta carpeta reúne la evidencia que sostiene `submission/STRATEGY.md`.

- `outputs/csvs/`: resultados en CSV y JSON. Cada cifra de `STRATEGY.md` se rastrea en `submission/generated_artifacts/VERIFICACION_CIFRAS.md`.
- `outputs/figs/`: figuras de los notebooks; `outputs/reports/`: informes JSON del motor para los ejemplos públicos.
- `scenarios_mc/`: índices y metadatos de los escenarios sintéticos (`tune_`, `hold_`, `final_`, `fin2_`, `edge_`). Los `shipments.csv` se regeneran con `src/build_scenarios.py` y `src/build_edge.py` (semillas fijas).
- `REFERENCIAS.md`: fuentes consultadas (los libros se citan, no se incluyen, por sus licencias).

La presentación interactiva (`presentacion.html`, autocontenida) y su generador están en `submission/generated_artifacts/presentacion/`.

El código (`src/`) y los cuadernos (`notebooks/`, 01 a 05, ejecutados) están en `submission/generated_artifacts/`, para no duplicarlos. Sus scripts suponen esta estructura de carpetas: copiados a `solucion/src/` y `solucion/notebooks/` funcionan tal cual.

Comprobaciones desde la raíz del repositorio:

```text
python run.py --strategy submission/candidate_strategy.py
python -S run.py --strategy submission/candidate_strategy.py
python run_150k.py
python -m unittest discover -s tests -v
```
