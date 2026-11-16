# Referencias consultadas

Esta lista recoge las fuentes que guiaron el diseño de la estrategia y el método de ajuste. Los libros se citan aquí y no se incluyen en el repositorio por respeto a sus licencias. El texto de los libros convertido para consulta rápida se generó localmente con MarkItDown y tampoco se versiona.

## Libros consultados

| Obra | Dónde la usé |
|---|---|
| Chen, D.-S., Batson, R. G. y Dang, Y. (2010). *Applied Integer Programming*. Wiley. | §2.6 (transporte con coste fijo, p. 38), §5.2 y §5.3 (partición de conjuntos y emparejamiento, pp. 106 y 115). El coste fijo por viaje del motor justifica agrupar tarjetas; el reparto por tick es un emparejamiento. |
| Eiselt, H. A. y Sandblom, C.-L. (2007). *Linear Programming and its Applications*. Springer. | §2.8 (transporte, p. 91), §2.9 (asignación, p. 102) y cap. 9 (varios objetivos): asignación óptima y lectura coste frente a tiempo. |
| Cortez, P. (2021). *Modern Optimization with R*. Springer. | Cap. 4 y 5 (búsqueda local y métodos evolutivos) como marco para comparar optimizadores; §6.5 (frente de Pareto, p. 164). |
| Axsäter, S. (2015). *Inventory Control*. Springer. | Fórmula de Little (L = λW) para interpretar el disparador de mejoras por cola. |
| Bičer, I. (2023). *Supply Chain Analytics*. Springer. | Contexto general; aplicación directa escasa, porque el reto no gestiona inventario. |

## Fuentes web (consultadas el 16 de octubre de 2026)

- Klapp, M. A., Erera, A. L. y Toriello, A. *The Dynamic Dispatch Waves Problem for Same-Day Delivery*. https://optimization-online.org/2016/10/5667/ (decidir cuándo despachar o esperar).
- Lyft Engineering. *Solving Dispatch in a Ridesharing Problem Space*. https://eng.lyft.com/solving-dispatch-in-a-ridesharing-problem-space-821d9606c3ff (emparejamiento por lotes).
- *Timing the Match*. arXiv 2503.13200. https://arxiv.org/pdf/2503.13200 (retención de órdenes para emparejar mejor).
- Bergstra, J. y Bengio, Y. (2012). Random search for hyper-parameter optimization. *JMLR*, 13(10), 281-305. https://jmlr.org/papers/v13/bergstra12a.html
- Boysen, N., Fedtke, S. y Schwerdfeger, S. (2021). Last-mile delivery concepts: a survey from an operational research perspective. *OR Spectrum*, 43(1), 1-58. https://link.springer.com/10.1007/s00291-020-00607-8
- Akiba, T., Sano, S., Yanase, T., Ohta, T. y Koyama, M. (2019). Optuna: a next-generation hyperparameter optimization framework. https://arxiv.org/abs/1907.10902
- Hansen, N. *The CMA Evolution Strategy: A Tutorial*. https://arxiv.org/abs/1604.07269 (citado desde una nota propia; no lo releí en esta corrida).
- Pinedo, M. *Scheduling: Theory, Algorithms, and Systems* (regla EDD y SPT; libro citado de memoria, no releído).

## Herramientas

Optuna 4.9 y `cmaes` 0.13.1 se usaron solo en el ajuste fuera de línea. El archivo evaluado usa únicamente la biblioteca estándar de Python.
