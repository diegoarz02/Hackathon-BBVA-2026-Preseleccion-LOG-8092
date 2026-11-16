# Hackathon BBVA 2026, preselección LOG-8092: estrategia de despacho de tarjetas

Mi solución al reto técnico individual de la preselección del Hackathon BBVA 2026 (código LOG-8092): una estrategia online que decide qué tarjetas bancarias salen en cada lote y con qué transportista, evaluada en un simulador de eventos discretos.

No es machine learning: es optimización de una política de decisión contra un simulador. La estrategia es de biblioteca estándar de Python, sin dependencias.

## Qué problema era

El simulador recibe tarjetas (producto, zona, cluster de entrega) y varios transportistas con precio, velocidad, riesgo de fallo y capacidades. La estrategia decide cuándo despachar, qué agrupar y con quién. Se mide coste, tiempo de entrega (lead y p95), cumplimiento de SLA, retención, CPU y RAM, con puertas que no se pueden violar (sin tarjetas sin resolver, sin infracciones de retención).

## Resultado frente al código inicial (starter)

| | 5 k starter | 5 k final | 150 k starter | 150 k final |
|---|---|---|---|---|
| Tarjetas sin resolver | 16 | 0 | 168 | 0 |
| Infracciones de retención | 42 | 0 | 837 | 0 |
| Coste (céntimos) | 4 443 213 | 3 593 368 | 138 126 792 | 111 100 128 |
| Lead medio (min) | 230,6 | 194,6 | 225,6 | 193,5 |
| p95 (min) | 1576 | 1523 | 1565 | 1515 |
| CPU neta (s) | 1,2 | 0,9 | 30,8 | 23,2 |

El coste baja cerca de 20 %, el lead medio entre 14 % y 16 %, y la CPU neta entre 25 % y 29 %. Fuera de muestra (16 escenarios generados después de fijar el candidato) la estrategia gana al starter en las cuatro métricas de negocio a la vez en 16 de 16. Cada cifra se rastrea en `submission/generated_artifacts/VERIFICACION_CIFRAS.md`.

## Cómo está planteada

Agrupa por (cluster, zona, intento, capacidades), retiene solo lo necesario para agrupar, da prioridad por plazo (EDD) cuando hay contención de flota, elige el carrier por valor esperado y, con flota escasa, resuelve un emparejamiento de coste mínimo con arrepentimiento. Todo está explicado, junto con lo que no funcionó y las limitaciones, en [`submission/STRATEGY.md`](submission/STRATEGY.md).

## Qué hay en este repositorio

- `candidate_strategy.py`: la estrategia (el único archivo evaluado).
- `submission/`: la entrega: `STRATEGY.md`, `submission_manifest.json` y `generated_artifacts/` (código de apoyo, cuadernos 01 a 05, presentación interactiva y verificación de cifras).
- `solucion/`: evidencia (resultados en CSV y JSON, figuras, índices de los escenarios sintéticos, referencias).
- `tests/test_policy_unit.py`: 16 pruebas unitarias de la política.

## Qué NO hay, a propósito

El kit oficial del reto (motor, datos, escenarios, reglas, evaluación, preguntas frecuentes, anexos y pruebas del kit) pertenece a BBVA y no se redistribuye aquí ni se relicencia. Está en el repositorio público oficial: <https://github.com/bbvaHackaton2026/BBVA-Hackaton-2026>. El `.gitignore` de este repo lista esos archivos para que, si los pones al lado para correr, no se suban por error.

Tampoco se publican las conversaciones completas con asistentes de IA que se entregaron a la organización. El uso de IA está declarado en `STRATEGY.md` y en `submission_manifest.json`. El correo de inscripción se omitió en los archivos donde aparecía (`submission_manifest.json`, `solucion/outputs/csvs/compliance_checks.json` y `submission/generated_artifacts/src/build_submission.py`).

## Cómo reproducirlo

```bash
git clone https://github.com/bbvaHackaton2026/BBVA-Hackaton-2026.git kit
git clone https://github.com/diegoarz02/Hackathon-BBVA-2026-Preseleccion-LOG-8092.git mi-solucion
cp mi-solucion/candidate_strategy.py kit/candidate_strategy.py
cp mi-solucion/tests/test_policy_unit.py kit/tests/
cd kit
python -S run.py --strategy candidate_strategy.py
python run_150k.py
python -m unittest discover -s tests -v
```

Los escenarios sintéticos de `solucion/scenarios_mc/` se regeneran con las semillas fijas de los scripts de `submission/generated_artifacts/src/` (`build_scenarios.py`, `build_edge.py`).

## Licencia

Mi código y mis documentos están bajo licencia MIT (ver [LICENSE](LICENSE)). El kit oficial de BBVA conserva sus propios derechos. Los libros y artículos que cito en `solucion/REFERENCIAS.md` se citan, no se incluyen.
