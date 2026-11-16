# generated_artifacts/

Código y cuadernos del trabajo offline: `src/` (política parametrizable, generador de escenarios, harness, optimizadores, robustez, validación y constructores de documentos), `notebooks/` (01 a 05, ejecutados), `presentacion/` (presentación interactiva autocontenida, `presentacion.html`, y su generador), `tests/test_policy_unit.py` (copia de la prueba de la raíz) y `VERIFICACION_CIFRAS.md` (cada cifra de `STRATEGY.md` con el CSV de donde sale).

Los resultados (CSV, figuras e informes del motor), los índices de los escenarios sintéticos y las referencias están en `solucion/` del mismo repositorio, para no duplicarlos aquí. Los scripts de `src/` suponen esa estructura (`solucion/outputs/`, `solucion/scenarios_mc/`).

No incluye dependencias, cachés ni datasets: los `shipments.csv` sintéticos se regeneran con `src/build_scenarios.py` y `src/build_edge.py` (semillas fijas).
