# Verificación de cifras de STRATEGY.md

Cada cifra del texto, con el archivo y el filtro de donde sale (rutas relativas a `solucion/outputs/csvs/`).

| cifra | valor | fuente |
|---|---|---|
| lote medio starter 5k | 1.0 | baseline_metrics.csv avg_batch |
| RAM starter 150k MiB | 113 | cpu_eval_public_150k.csv estrategia=starter rss_mib_mediana3 |
| RAM final 150k MiB | 27 | cpu_eval_public_150k.csv estrategia=final rss_mib_mediana3 |
| hold_cap_min | 45 | v2_decision.json params_ganador.hold_cap_min |
| up_wait_thr | 0.50 | v2_decision.json params_ganador.up_wait_thr |
| n edge | 15 | final_file_validation.csv scenario=edge_* |
| unres s5 | 16 | cpu_eval_public_5k.csv |
| unres f5 | 0 | cpu_eval_public_5k.csv |
| unres s1 | 168 | cpu_eval_public_150k.csv |
| unres f1 | 0 | cpu_eval_public_150k.csv |
| ret s5 | 42 | cpu_eval_public_5k.csv |
| ret f5 | 0 | cpu_eval_public_5k.csv |
| ret s1 | 837 | cpu_eval_public_150k.csv |
| ret f1 | 0 | cpu_eval_public_150k.csv |
| cost s5 | 4 443 213 | cpu_eval_public_5k.csv cost_total |
| cost f5 | 3 593 368 | cpu_eval_public_5k.csv cost_total |
| cost s1 | 138 126 792 | cpu_eval_public_150k.csv cost_total |
| cost f1 | 111 100 128 | cpu_eval_public_150k.csv cost_total |
| lead s5 | 230.6 | cpu_eval_public_5k.csv lead_mean |
| lead f5 | 194.6 | cpu_eval_public_5k.csv lead_mean |
| lead s1 | 225.6 | cpu_eval_public_150k.csv lead_mean |
| lead f1 | 193.5 | cpu_eval_public_150k.csv lead_mean |
| p95 s5 | 1576 | cpu_eval_public_5k.csv lead_p95 |
| p95 f5 | 1523 | cpu_eval_public_5k.csv lead_p95 |
| p95 s1 | 1565 | cpu_eval_public_150k.csv lead_p95 |
| p95 f1 | 1515 | cpu_eval_public_150k.csv lead_p95 |
| rcp s5 | 9.869 | cpu_eval_public_5k.csv rcp |
| rcp f5 | 9.965 | cpu_eval_public_5k.csv rcp |
| rcp s1 | 9.876 | cpu_eval_public_150k.csv rcp |
| rcp f1 | 9.929 | cpu_eval_public_150k.csv rcp |
| cpu s5 | 1.2 | cpu_eval_public_5k.csv cpu_neta_s |
| cpu f5 | 0.9 | cpu_eval_public_5k.csv cpu_neta_s |
| cpu s1 | 30.8 | cpu_eval_public_150k.csv cpu_neta_s |
| cpu f1 | 23.2 | cpu_eval_public_150k.csv cpu_neta_s |
| ram s5 | 29 | cpu_eval_public_5k.csv |
| ram f5 | 27 | cpu_eval_public_5k.csv |
| ram s1 | 113 | cpu_eval_public_150k.csv |
| ram f1 | 27 | cpu_eval_public_150k.csv |
| dcost 5k | 19 | cpu_eval_public_5k.csv |
| dcost 150k | 20 | cpu_eval_public_150k.csv |
| dlead 5k | 16 | cpu_eval_public_5k.csv |
| dlead 150k | 14 | cpu_eval_public_150k.csv |
| dp95 5k | 3.4 | cpu_eval_public_5k.csv |
| dp95 150k | 3.2 | cpu_eval_public_150k.csv |
| dcpu 5k | 29 | cpu_eval_public_5k.csv cpu_neta_s |
| dcpu 150k | 25 | cpu_eval_public_150k.csv cpu_neta_s |
| llamadas dispatch | 128 238 | hook_timing.json svc_dispatch_calls |
| us por lote | 335 | hook_timing.json svc_dispatch_us_per_call |
| compute propio s | 6.9 | hook_timing.json own_compute_s |
| hook max | 0.049 | hook_timing.json max_hook_s |
| wall 150k | 131 | cpu_eval_public_150k.csv wall_s_mediana3 final |
| dom fin2 | 16 | final_file_validation.csv vs starter, fin2_* |
| fin2 coste | -20.3 | idem |
| fin2 lead | -14.5 | idem |
| fin2 p95 | -4.2 | idem |
| fin2 rcp | +0.136 | idem |
| gates fin2 | 16 | final_file_validation.csv |
| gates st fin2 | 0 | starter en fin2_* |
| dom hold | 16 | idem hold_* |
| dom final | 15 | idem final_* |
| dom tune | 12 | idem tune_* |
| ret total | 0 | final_file_validation.csv hold_breaches sum |
| gates tune | 12 | idem |
| lotes vs cota | -0.21 | ceiling_batches_p95.csv lote_vs_cota_sup_pct mean |
| p95 vs eta | -0.66 | ceiling_batches_p95.csv p95_vs_eta_pct mean |
| oraculo lead | 2.1 | techo_retencion_oraculo.csv lead_pct |
| oraculo coste | 0.3 | techo_retencion_oraculo.csv coste_pct |
| J mejor | 3.636 | optimizers_comparison.csv mejor_J |
| J peor | 3.660 | idem |
| rango J | 0.7 | idem |
| dpts | -0.7 | v2_decision.json robustez_puntos_vs_incumbente |
| f2 dc | +0.6 | fin2_results.csv |
| f2 dl | -0.3 | fin2_results.csv |
| p5 dc | +0.3 | public_control.csv |
| p1 dc | -0.9 | public_control.csv |
| dom hf | 31 | final_file_validation.csv hold+final |
| hung dJ | +0.05 | ablation_components.csv J hungarian - full |
| lead greedy | 1268 | emparejamiento_casos_extremos.csv edge_stress_noup |
| lead lookahead | 761 | idem |
| lead xl | 2.0 | idem edge_stress_xl |
| speed buys | 31 | speed_capacity_rules.csv speed_total speed_k0.2 |
| speed coste | 5.6 | idem |
| speed lead | 2.7 | idem |
| wu0 coste fin2 | -3.2 | fin2_results.csv wu0 |
| wu0 lead fin2 | +1.5 | fin2_results.csv wu0 |
| wu0 pts | +0.8 | v2_decision.json |
| dom completo | 28 | ablation_final.csv domina_starter_de_28 |
| proxy completo | 51.8 | ablation_final.csv puntos_proxy |
| dom sin tiempo | 10 | ablation_final.csv |
| proxy sin tiempo | 27.7 | ablation_final.csv |
| coste completo | 1.09 | ablation_final.csv coste_vs_ref |
| coste sin ret | 1.25 | ablation_final.csv coste_vs_ref |
| proxy sin ret | 31.1 | ablation_final.csv |
| w_time | 6.00 | v2_decision.json params_ganador.w_time |
| vs barata coste | +10.1 | idem fin2 ref_price |
| vs barata lead | -17.7 | idem |
| piso ram | 27 | cpu_eval_public_5k.csv noop |
| n tests | 16 | python -m unittest discover -s tests -v |

Palabras de STRATEGY.md: 2468 (límite 2 500).

## No verificado en esta corrida
- Citas bibliográficas de libros (Pinedo; Eiselt y Sandblom; Chen, Batson y Dang): verificadas por su existencia (índices de los PDF para los dos últimos), no re-leídas en su totalidad.
- Klapp, Erera y Toriello (EJOR 2018), Boysen et al. (2021), Bergstra y Bengio (2012), Akiba et al. (2019): existencia y datos bibliográficos comprobados en búsqueda web el 16-oct-2026.
