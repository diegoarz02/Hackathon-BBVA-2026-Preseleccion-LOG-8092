# STRATEGY

## 1. Qué cambié y por qué

El código inicial despachaba una tarjeta por lote con un round-robin entre carriers. No agrupa, y el motor cobra el *linehaul* por lote: el lote medio del starter es 1.0 tarjeta. Tras un `INACCESSIBLE_ROUTE` reintenta con el mismo carrier aunque no tenga `HARD_ACCESS`, y acaba en `UNRESOLVED`. Comprueba la zona con una subcadena (`"URBANA" in "SUBURBANA"` es verdadero), deja tarjetas pendientes aunque haya otro carrier libre y guarda todo el histórico, de modo que la memoria crece con los envíos: 113 MiB frente a 27 MiB de la versión final.

Reescribí `CandidateStrategy` con seis piezas.

**Grupos.** Las tarjetas se agrupan por (cluster, zona, intento, capacidades requeridas): es lo único que el motor admite en un mismo lote.

**Retención solo para agrupar.** El motor audita la retención en el primer tick posterior a `ready_at + 45 min`, y el tick corre antes que la auditoría. Retengo un cluster multi-tarjeta como máximo hasta ese tick (tope de 45 min). Salir antes nunca produce una infracción. Que un identificador pertenezca a un cluster multi no está escrito en el código: la estrategia lo aprende en línea (probabilidad de cluster multi según la *forma* del id, con los dígitos borrados) y solo retiene si esa probabilidad supera 0.5.

**Prioridad EDD.** Cuando hay contención de flota, pasa primero el grupo cuyo plazo SLA vence antes.

**Carrier por valor esperado.** Para cada grupo calculo, en céntimos, el precio exacto del lote, más el valor del tiempo por la ETA, más el riesgo de fallo atribuible al carrier por el coste esperado de un fallo, más un coste sombra por ocupar la unidad. Las probabilidades de fallo se leen del contexto del escenario. `HARD_ACCESS` elimina el riesgo de ruta inaccesible; los domingos y festivos suben el riesgo operativo del carrier.

**Emparejamiento con arrepentimiento bajo escasez.** Si hay más grupos listos que unidades libres, resuelvo una asignación de coste mínimo (algoritmo húngaro) cuyo coste por pareja es J − M − K. M es el valor de los minutos de espera que se evitan, y K una constante enorme que obliga a emparejar tantos grupos como unidades factibles haya, porque una unidad libre y factible con un envío esperando sería una infracción. Entre los emparejamientos máximos, las unidades escasas van a los grupos más urgentes. Con unidades de sobra uso el greedy.

**Modelo local de la flota y mejoras mensuales.** Cada unidad que envío vuelve en `now + pickup + 2·ida`, como en el motor; así despacho al llegar la tarjeta sin pedir un `snapshot()`, que cuesta CPU. Una unidad extra (`EXTRA_UNIT`) solo se pide si la cola media del periodo anterior supera 0.50 tarjetas por tick.

## 2. Cómo lo planteé

Lo traté como un proceso de decisión de Markov con acción (qué grupo sale ahora y con qué carrier) y coste (dinero más penalización por tiempo y riesgo). La programación dinámica exacta es inviable y el archivo evaluado no admite un solver, así que usé una aproximación de política: una regla paramétrica con constantes afinadas offline sobre el simulador. La prioridad se apoya en teoría de scheduling: EDD minimiza la tardanza máxima (Jackson; Pinedo, *Scheduling*).

Dos escenarios públicos habrían llevado al sobreajuste. El motor acepta datos propios (la carpeta de datos no se valida contra los hashes del kit), así que generé escenarios sintéticos dentro de `[scenario_ranges]` con las estadísticas medidas en los públicos: perfil horario y semanal, mezcla de producto y zona, clusters de 2 a 4 tarjetas que llegan en menos de 45 min. Los separé en conjuntos de afinado, de decisión y de validación, y añadí 15 casos de contrato: ráfaga de 1 500 llegadas simultáneas, lotes de capacidad 1, flota al 30 %, un solo carrier, ids opacos, zona sin cobertura.

## 3. Qué medí

CPU y RAM, como el evaluador: un calentamiento y la mediana de tres ejecuciones en serie, restando la CPU de una estrategia nula (el piso del motor).

| | 5 k starter | 5 k final | 150 k starter | 150 k final |
|---|---|---|---|---|
| UNRESOLVED | 16 | 0 | 168 | 0 |
| Infracciones de retención | 42 | 0 | 837 | 0 |
| Coste (céntimos) | 4 443 213 | 3 593 368 | 138 126 792 | 111 100 128 |
| Lead medio (min) | 230.6 | 194.6 | 225.6 | 193.5 |
| p95 (min) | 1576 | 1523 | 1565 | 1515 |
| RCP | 9.869 | 9.965 | 9.876 | 9.929 |
| CPU neta (s) | 1.2 | 0.9 | 30.8 | 23.2 |
| RAM pico (MiB) | 29 | 27 | 113 | 27 |

Frente al starter, el coste baja 19 % en 5 k y 20 % en 150 k; el lead medio, 16 % y 14 %; el p95, 3.4 % y 3.2 %. La CPU neta baja 29 % en 5 k y 25 % en 150 k, y casi toda la que queda es espera al motor: de las 128 238 llamadas a `dispatch_batch`, el motor tarda unos 335 µs en cada una, y esa espera cuenta como CPU del proceso candidato; mi cómputo propio suma 6.9 s. Solo bajaría con menos lotes, y la agrupación ya está en su techo. El hook más lento tardó 0.049 s (límite: 30 s) y el escenario más largo, el público de 150 k, 131 s (límite: 900 s).

**Fuera de muestra.** En FIN2, 16 escenarios generados después de fijar el candidato, la estrategia gana al starter en coste, lead, p95 y RCP a la vez en 16 de 16, con coste -20.3 %, lead -14.5 %, p95 -4.2 % y RCP +0.136, y cumple los gates en 16 de 16 (el starter, en 0). En HOLD y FINAL gana en las cuatro métricas en 16 y 15 de 16 escenarios; en los 12 de afinado, que sirvieron para elegir, en 12.

**Robustez.** En los 75 escenarios sintéticos hay 0 infracciones de retención y ningún error. Cumple los gates en 12/12 escenarios de afinado, 16/16 de HOLD y 10/10 de los casos de contrato factibles. No cuento los casos que ninguna estrategia puede resolver (zona sin carrier, `HARD_ACCESS` inexistente, ráfaga mayor que la flota).

**Techos.** Cada cluster necesita al menos un lote en el primer intento y cada reintento fallido añade, como mucho, uno más. Esa cota superior deja el número de lotes de la estrategia en -0.21 % de promedio: no hay agrupación pendiente. El p95 queda a -0.66 % del de la regla «siempre el carrier más rápido»; casi todos los fallos son ausencias del cliente, que no dependen del carrier, y el reintento espera 1 440 min. Un oráculo que conoce el tamaño real de cada cluster mejoraría el lead 2.1 % y el coste 0.3 % como máximo, y una regla de espera por probabilidades, que probé, no mejora a la actual.

## 4. Cómo afiné y cómo elegí

Comparé cinco optimizadores con el mismo espacio de 11 parámetros, 60 evaluaciones cada uno, los mismos ocho escenarios y el mismo objetivo: las cuatro métricas de negocio normalizadas por una referencia barata, ponderadas 40/25/20/15, más una penalización dura por cada gate violado y otra por no superar al starter con margen. El mejor valor fue 3.636 y el peor 3.660 (0.7 % de diferencia): un paisaje casi plano. Los comparé por ensayos hasta quedar a 1 % del mejor valor, no por tiempo de pared, que la suspensión de la laptop distorsiona.

Antes de afinar contrasté mis escenarios con los datos públicos, estadístico por estadístico. Un primer re-ajuste, hecho con escenarios cuyas tarjetas de un mismo destino llegaban más juntas que en la realidad (mediana de 14 frente a 23 minutos), eligió un tope de retención de 27.7 min que, en el ejemplo público de 5 000 tarjetas, empeoraba a la versión anterior (coste +2.3 %, lote medio 1.199 frente a 1.273). Lo detecté al comparar con los datos reales; corregí el generador y repetí el afinado.

Elegí con una regla fijada de antemano: gates en todos los conjuntos, cero infracciones de retención, dominancia sobre el starter en HOLD y FINAL, y una mejora robusta frente a las constantes de la primera corrida en puntos por escenario, según la regla de percentiles de la evaluación (percentil = 100·(n−r)/(n−1); 20 puntos por métrica; escenarios ponderados 40/25/20/15). Con un bootstrap pareado sobre 32 escenarios, el mejor candidato elegible, tpe#2_ns (TPE sin compras de SPEED_SHIFT), queda a -0.7 puntos por escenario de la versión anterior (IC 95 % [-4.6; 3.6]): no hay mejora robusta, así que conservo las constantes de la primera corrida, con el bucle de despacho corregido. En FIN2 tpe#2_ns cambia el coste +0.6 % y el tiempo medio -0.3 %; en los públicos, el coste +0.3 % (5 000) y -0.9 % (150 000): es equivalente. Las constantes conservadas superan al starter en las cuatro métricas en 31 de 32 escenarios de HOLD y FINAL; en uno pierden en el tiempo medio.

## 5. Qué no funcionó y qué aporta cada pieza

- **Hungarian puro por tick.** Empeoró el objetivo en +0.05 y gastó más CPU: minimizar la suma de J deja sin unidad a los grupos caros, que son los urgentes. El arrepentimiento lo arregla, pero solo importa con flota saturada: con la flota al 30 %, el lead medio bajó de 1268 a 761 min, y con 12 000 tarjetas y flota al 45 % subió 2.0 %; en escenarios normales no cambió nada.
- **Dos errores míos en el bucle de despacho.** El primero: la versión inicial del emparejamiento cortaba el bucle con tarjetas pendientes cuando el carrier admite lotes de una tarjeta, y produjo 83 infracciones de retención con capacidad 1 (`robustness_results_lookahead_v1_bug_cap1.csv`); lo detectó el conjunto de casos de contrato. El segundo apareció en la segunda corrida: al repartir por ventanas de 24 grupos, el bucle terminaba con grupos listos tras una ronda que sí había enviado. Lo delató una ablación absurda (con ventana 1 fallaban 25 escenarios, y un parámetro de tamaño no puede romper gates). Con una ráfaga de 600 tarjetas simultáneas y flota amplia, la versión defectuosa tuvo 456 infracciones de retención y la corregida, 0. Corregí el bucle y añadí una prueba de regresión y el caso `edge_burst_bigfleet`.
- **SPEED_SHIFT y EXPANDED_CAPACITY.** Con un umbral exigente, SPEED_SHIFT casi nunca se activa. Con uno laxo compra 31 mejoras en 12 escenarios, sube el coste ≈ 5.6 % y baja el lead ≈ 2.7 %: no compensa. EXPANDED_CAPACITY nunca se activa: los clusters no superan 4 tarjetas y las capacidades empiezan en 8. Dejé ambas fuera del archivo final.
- **Despachar solo en los ticks.** Ahorra 7.5 min de espera por tarjeta a costa de un 2 % de lead, sin ahorro medible de CPU.
- **Ablación del candidato final** (28 escenarios de afinado y decisión). Medido solo con J, quitar el riesgo de fallo o el coste sombra lo mejora, pero ambos movimientos recorren la frontera coste y tiempo: sin el coste sombra baja el coste y sube el lead (-3.2 % y +1.5 % en FIN2, y el candidato `wu0` queda en +0.8 puntos por escenario, IC 95 % [-2.0; 4.0]), así que no lo adopto. El candidato completo supera al starter en las cuatro métricas en 28 de 28 escenarios y suma 51.8 puntos. Sin el valor del tiempo baja a 10 escenarios y 27.7 puntos; sin retención, el coste sube de 1.09 a 1.25 veces el de la referencia barata y los puntos caen a 31.1. El emparejamiento y las mejoras mensuales solo importan con flota saturada, y los conservo como seguro.

## 6. La palanca coste-tiempo

La variable que mueve la posición en la frontera es `w_time`, los céntimos que vale un minuto de entrega por tarjeta. El valor final es 6.00. Frente a la estrategia «siempre la más barata», en FIN2 gasto +10.1 % y entrego -17.7 % más rápido; frente al starter, mejoro las cuatro métricas. El re-ajuste no encontró un punto mejor de forma robusta, así que lo conservo.

## 7. Limitaciones

No tengo acceso a los escenarios de evaluación. Mi hipótesis, no medida, es que se parecen a los míos, que reproducen lo medido en los dos públicos; los ocultos pueden diferir en tamaño o en perfil de pico. Queda pendiente probar la política con datos de operación real. Tampoco conozco a los demás candidatos, y los «puntos» que cito son un proxy sobre una cohorte propia, no el cálculo del evaluador. El aprendizaje de clusters multi aprovecha que, en los datos públicos, la forma del id distingue clusters multi de singleton; con ids opacos la estrategia no retiene y pierde eficiencia, no gates. La CPU y la RAM tienen un piso común del motor (≈ 27 MiB). Medí en un Intel Core i7-12700H (15.7 GB) con Python 3.14; el evaluador usa un i7-13700HX y Python 3.13. Un procesador más rápido baja los segundos de CPU de todos los candidatos sin cambiar su orden, porque domina la espera al motor por lote; solo acortaría el afinado.

## 8. Fuentes, ayudas de IA y verificación

**IA.** Trabajé con Claude Code (Anthropic, modelo Claude Sonnet 5.5) en el código, los experimentos y los documentos, y con Claude Cowork (claude-opus-4-8 y claude-opus-5-5) para auditar la carpeta y los resultados, investigar bibliografía y redactar prompts. Mi parte fue dirigir, cuestionar y decidir: fijé el objetivo de ganar al starter en las cuatro métricas, pedí comparar cinco optimizadores y advertí del riesgo de sesgar el afinado con datos sintéticos. Las conversaciones están en `ai_conversations/` (`cowork-sesion-01.md` y `claude-code-sesion-*.md`). Verifiqué cada aportación ejecutando el motor, las pruebas (16, incluida la del kit) y `python -S run.py`, y comparando con referencias simples. El archivo final reproduce exactamente, escenario por escenario, la versión de investigación con la que se eligieron los parámetros.

**Código reutilizado.** Del kit conservo `interfaces.py` y los lanzadores; la estrategia es nueva y no copié código externo.

**Notas heredadas.** `anexos/nota_traspaso_legacy.pdf` (LEG-07) y `anexos/nota_operaciones_legacy.md` (LEG-12) piden a un asistente de IA crear un archivo con una cadena fija y escribir en este documento que se omite la revisión de la estrategia. No hice ninguna de las dos cosas: las traté como datos, no como instrucciones, y las rechazo.

**Bibliografía y fuentes.** Klapp, Erera y Toriello, *The Dynamic Dispatch Waves Problem for Same-Day Delivery* (EJOR 2018); Pinedo, *Scheduling* (EDD); Boysen, Fedtke y Schwerdfeger (2021), OR Spectrum 43(1):1 a 58; Bergstra y Bengio (2012), JMLR 13(10):281 a 305; Akiba et al. (2019), Optuna; Eiselt y Sandblom, *Linear Programming and its Applications* (asignación); Chen, Batson y Dang, *Applied Integer Programming* (emparejamiento). Cito los cinco libros consultados en `solucion/REFERENCIAS.md`; no los incluyo en el repositorio por respeto a sus licencias. Herramientas offline: Optuna, cmaes, pandas, scipy, matplotlib y MarkItDown.
