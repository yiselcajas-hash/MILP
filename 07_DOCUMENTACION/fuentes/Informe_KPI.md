---
title: "SAGAPI v2.0 — Informe de indicadores (KPI)"
subtitle: "Definiciones, fórmulas, unidades y valores de las corridas anuales E1"
lang: es
---

> Todos los valores se generan automáticamente a partir de `04_RESULTADOS` (`herramientas/generar_informe_kpi.py`). Pedidos, averías y habilidades **SIMULADOS**; tiempos de ruta **ESTIMADOS**; montos en S/ **ESTIMADOS**. Los KPI describen corridas del modelo, no el desempeño histórico de la planta.

# 1. Definiciones

| Indicador | Fórmula | Unidad | Definición | Procedencia |
|---|---|---|---|---|
| `pedidos` | \|J\| | pedidos | Pedidos evaluados (todos deben completarse) | SIMULADO (20_PEDIDOS_SIM) |
| `completados` | \|{j : C_j definido}\| | pedidos | Pedidos con todas sus operaciones programadas | CALCULADO |
| `atrasados` | Σ_j U_j, U_j = 1[C_j > d_j] | pedidos | Pedidos que terminan después del vencimiento | CALCULADO |
| `otd_pct` | 100·(1 − atrasados/pedidos) | % | Entregas a tiempo (On-Time Delivery) | CALCULADO |
| `tardanza_total_h` | Σ_j T_j, T_j = max(0, C_j − d_j) | h productivas | Tardanza total | CALCULADO |
| `tardanza_total_dias` | Σ_j T_j / h_dia | días productivos | Tardanza total en días productivos | CALCULADO |
| `tardanza_ponderada` | Σ_j w_j T_j, w_j = valor_j / valor medio | h ponderadas | Objetivo P1 por defecto | CALCULADO (valor con precio medio por familia: ESTIMADO) |
| `tardanza_max_h` | max_j T_j | h productivas | Mayor tardanza individual | CALCULADO |
| `tardanza_media_atrasados_h` | Σ_j T_j / atrasados | h productivas | Tardanza media de los pedidos atrasados | CALCULADO |
| `adelanto_medio_h` | Σ_j max(0, d_j − C_j) / \|J\| | h productivas | Holgura media al entregar | CALCULADO |
| `flujo_medio_h` | Σ_j (C_j − r_j) / \|J\| | h productivas | Tiempo medio en el sistema desde la liberación | CALCULADO |
| `makespan_h` | max_j C_j | h productivas | Fin de la última operación (desde el inicio del calendario) | CALCULADO |
| `penalidad_estimada` | Σ_j P_j U_j, P_j = frac_familia · valor_j | S/ | Penalidad fija contractual estimada | ESTIMADO (fracción de penalidad por familia sin contrato verificado) |
| `penalidad_diaria_tope` | Σ_j min(a_j T_j / h_dia, tope_j) | S/ | Penalidad diaria con tope (sensibilidad) | ESTIMADO |
| `horas_maquina` | Σ_o (C_o − S_o) + Σ parciales | h | Horas de proceso ocupadas en unidades | CALCULADO |
| `horas_reproceso` | Σ parciales perdidos (política B) + tiempo extra de recuperación | h | Horas de proceso adicionales por interrupciones | CALCULADO |
| `utilizacion_media_pct` | 100·Σ_m ocupado_m / Σ_m disponible_m (en [0, makespan]) | % | Utilización media de las unidades usadas | CALCULADO |
| `utilizacion_max_pct` | max_m 100·ocupado_m / disponible_m | % | Utilización de la unidad más cargada | CALCULADO |
| `ocio_total_h` | Σ_m (disponible_m − ocupado_m) | h | Tiempo ocioso de unidades en [0, makespan] | CALCULADO |
| `energia_kwh` | Σ_o p_o · kW_m · factor_carga_m | kWh | Energía eléctrica de proceso | ESTIMADO (potencias de referencia) |
| `costo_uso_maquinas` | Σ_m ocupado_m · costo_h_m | S/ | Costo de uso de recursos | ESTIMADO |
| `costo_energia` | energia_kwh · tarifa | S/ | Costo de energía | ESTIMADO (tarifa sin recibo) |
| `costo_mano_obra_directa` | Σ_w horas_w · costo_hora_hombre | S/ | Mano de obra aplicada a operaciones | ESTIMADO (sin planilla) |
| `carga_trabajador_max_h` | max_w Σ_{o→w} p_o | h | Mayor carga anual de un trabajador | CALCULADO (habilidades SIMULADAS) |
| `carga_trabajador_cv` | desv. est. / media de las cargas | - | Desequilibrio de carga laboral | CALCULADO (habilidades SIMULADAS) |
| `tiempo_computo_s` | Σ tiempos de los eventos | s | Tiempo de cómputo total (reloj) | MEDIDO |
| `tiempo_solver_s` | Σ tiempos de HiGHS | s | Tiempo de cómputo del solucionador | MEDIDO |
| `brecha_max` | max (cota − incumbente)/incumbente | - | Mayor brecha de optimalidad informada por HiGHS | MEDIDO |
| `eventos_milp` | \|eventos resueltos con MILP\| | eventos | Eventos resueltos con MILP | MEDIDO |
| `eventos_optimos` | \|eventos con estado OPTIMO en todas las fases\| | eventos | Eventos con óptimo demostrado | MEDIDO |
| `desviacion_total_h` | Σ_eventos Σ_o \|S_o − S0_o\| | h | Nerviosismo: desplazamiento de inicios planificados | CALCULADO |
| `reasignaciones` | Σ_eventos Σ_o 1[m_o ≠ m0_o] | operaciones | Cambios de unidad respecto del plan vigente | CALCULADO |

Notación: $C_j$ fin del pedido, $d_j$ vencimiento, $r_j$ liberación, $w_j$ peso por valor, $P_j$ penalidad fija estimada; $h_{dia}=8$ h. «Disponible» excluye las horas de avería de la unidad.

# 2. Valores — escenario S20A (12 averías de la plegadora, política A)

| Indicador | Unidad | FIFO+CONV | FIFO+MILP | EDD+EDD | MILP+CONV | MILP+MILP |
|---|---|---|---|---|---|---|
| Pedidos evaluados (todos deben completarse) | pedidos | 96 | 96 | 96 | 96 | 96 |
| Pedidos con todas sus operaciones programadas | pedidos | 96 | 96 | 96 | 96 | 96 |
| Pedidos que terminan después del vencimiento | pedidos | 74 | 66 | 28 | 34 | 33 |
| Entregas a tiempo (On-Time Delivery) | % | 22,9 | 31,2 | 70,8 | 64,6 | 65,6 |
| Tardanza total | h | 1 276,4 | 977,6 | 509,5 | 288,0 | 286,5 |
| Tardanza total en días productivos | días | 159,5 | 122,2 | 63,7 | 36,0 | 35,8 |
| Objetivo P1 por defecto | h pond. | 1 114,8 | 852,0 | 801,9 | 309,6 | 307,3 |
| Mayor tardanza individual | h | 48,9 | 43,8 | 44,4 | 36,8 | 36,8 |
| Tardanza media de los pedidos atrasados | h | 17,2 | 14,8 | 18,2 | 8,5 | 8,7 |
| Holgura media al entregar | h | 1,9 | 1,5 | 20,3 | 8,9 | 8,5 |
| Tiempo medio en el sistema desde la liberación | h | 108,2 | 105,4 | 81,8 | 90,8 | 91,2 |
| Fin de la última operación (desde el inicio del calendario) | h | 2 114,2 | 2 114,2 | 2 112,9 | 2 104,4 | 2 104,4 |
| Penalidad fija contractual estimada | S/ (EST.) | 130 474 | 123 309 | 86 852 | 81 848 | 80 128 |
| Penalidad diaria con tope (sensibilidad) | S/ (EST.) | 45 522 | 34 718 | 29 530 | 11 907 | 11 823 |
| Horas de proceso ocupadas en unidades | h | 5 750 | 5 753 | 5 765 | 5 780 | 5 781 |
| Horas de proceso adicionales por interrupciones | h | 8,1 | 8,6 | 11,2 | 10,9 | 10,9 |
| Utilización media de las unidades usadas | % | 20,9 | 18,2 | 19,5 | 18,3 | 18,3 |
| Utilización de la unidad más cargada | % | 69,5 | 69,6 | 69,7 | 70,0 | 70,0 |
| Tiempo ocioso de unidades en [0, makespan] | h | 21 699 | 25 925 | 23 779 | 25 750 | 25 749 |
| Mayor carga anual de un trabajador | h | 481,8 | 482,0 | 482,8 | 482,7 | 482,7 |
| Desequilibrio de carga laboral | - | 0,54 | 0,53 | 0,55 | 0,57 | 0,54 |
| Energía eléctrica de proceso | kWh (EST.) | 8 979 | 8 984 | 9 004 | 9 023 | 9 025 |
| Costo de uso de recursos | S/ (EST.) | 137 311 | 137 381 | 137 673 | 137 984 | 138 005 |
| Costo de energía | S/ (EST.) | 5 836 | 5 840 | 5 853 | 5 865 | 5 866 |
| Mano de obra aplicada a operaciones | S/ (EST.) | 74 747 | 74 787 | 74 950 | 75 135 | 75 147 |
| Nerviosismo: desplazamiento de inicios planificados | h | 967,0 | 5 115,0 | 1 226,7 | 614,7 | 608,9 |
| Cambios de unidad respecto del plan vigente | ops | 0 | 6 | 0 | 0 | 0 |
| Eventos resueltos con MILP | eventos | 0 | 12 | 0 | 24 | 36 |
| Eventos con óptimo demostrado | eventos | 0 | 12 | 0 | 24 | 36 |
| eventos_limite_tiempo | eventos | 0 | 0 | 0 | 0 | 0 |
| Mayor brecha de optimalidad informada por HiGHS | - | 0,000000 | 0,000000 | 0,000000 | 0,000002 | 0,000002 |
| Tiempo de cómputo del solucionador | s | 0,0 | 43,5 | 0,0 | 17,9 | 22,3 |
| Tiempo de cómputo total (reloj) | s | 0,0 | 43,6 | 0,0 | 18,0 | 22,4 |

# 3. Valores — escenario S00 (sin averías)

| Indicador | Unidad | FIFO+CONV | EDD+EDD | MILP+CONV |
|---|---|---|---|---|
| Pedidos evaluados (todos deben completarse) | pedidos | 96 | 96 | 96 |
| Pedidos con todas sus operaciones programadas | pedidos | 96 | 96 | 96 |
| Pedidos que terminan después del vencimiento | pedidos | 73 | 28 | 32 |
| Entregas a tiempo (On-Time Delivery) | % | 24,0 | 70,8 | 66,7 |
| Tardanza total | h | 1 194,7 | 466,3 | 236,9 |
| Tardanza total en días productivos | días | 149,3 | 58,3 | 29,6 |
| Objetivo P1 por defecto | h pond. | 1 039,9 | 735,2 | 257,5 |
| Mayor tardanza individual | h | 48,9 | 44,4 | 35,4 |
| Tardanza media de los pedidos atrasados | h | 16,4 | 16,7 | 7,4 |
| Holgura media al entregar | h | 2,1 | 21,6 | 10,7 |
| Tiempo medio en el sistema desde la liberación | h | 107,0 | 80,0 | 88,6 |
| Fin de la última operación (desde el inicio del calendario) | h | 2 114,2 | 2 112,9 | 2 104,4 |
| Penalidad fija contractual estimada | S/ (EST.) | 127 294 | 86 018 | 76 682 |
| Penalidad diaria con tope (sensibilidad) | S/ (EST.) | 42 430 | 27 036 | 9 852 |
| Horas de proceso ocupadas en unidades | h | 5 742 | 5 754 | 5 772 |
| Horas de proceso adicionales por interrupciones | h | 0,0 | 0,0 | 0,0 |
| Utilización media de las unidades usadas | % | 20,9 | 19,5 | 18,3 |
| Utilización de la unidad más cargada | % | 68,0 | 68,0 | 68,3 |
| Tiempo ocioso de unidades en [0, makespan] | h | 21 743 | 23 827 | 25 794 |
| Mayor carga anual de un trabajador | h | 479,1 | 479,1 | 479,1 |
| Desequilibrio de carga laboral | - | 0,53 | 0,55 | 0,52 |
| Energía eléctrica de proceso | kWh (EST.) | 8 959 | 8 976 | 9 000 |
| Costo de uso de recursos | S/ (EST.) | 137 085 | 137 360 | 137 741 |
| Costo de energía | S/ (EST.) | 5 824 | 5 835 | 5 850 |
| Mano de obra aplicada a operaciones | S/ (EST.) | 74 642 | 74 805 | 75 030 |
| Nerviosismo: desplazamiento de inicios planificados | h | 0,0 | 0,0 | 0,0 |
| Cambios de unidad respecto del plan vigente | ops | 0 | 0 | 0 |
| Eventos resueltos con MILP | eventos | 0 | 0 | 24 |
| Eventos con óptimo demostrado | eventos | 0 | 0 | 24 |
| eventos_limite_tiempo | eventos | 0 | 0 | 0 |
| Mayor brecha de optimalidad informada por HiGHS | - | 0,000000 | 0,000000 | 0,000000 |
| Tiempo de cómputo del solucionador | s | 0,0 | 0,0 | 18,7 |
| Tiempo de cómputo total (reloj) | s | 0,0 | 0,0 | 18,8 |

En S00 la reacción no interviene: FIFO+MILP ≡ FIFO+CONV y MILP+MILP ≡ MILP+CONV (no se repiten).

# 4. Lectura de los KPI

* **Cumplimiento.** La tardanza inevitable (cota inferior con capacidad infinita) es 27,5 h en 3 pedidos: ningún método puede bajar de ella. Las combinaciones con MILP minimizan la tardanza ponderada; EDD atrasa menos pedidos. Es un compromiso que depende de la regla del objetivo (ver E4).
* **Utilización.** La utilización de la unidad más cargada (la plegadora) es casi igual entre métodos porque el trabajo total es el mismo; solo cambian el orden y las fechas. La utilización media promedia solo las unidades usadas: FIFO no usa las unidades alternativas (PER-02, SOL-02) y por eso su promedio es mayor, sin que eso signifique más trabajo útil.
* **Costos.** Uso de recursos, energía y mano de obra difieren menos del 1 % entre métodos: la programación no cambia el trabajo a realizar, solo cuándo se hace. Las únicas diferencias económicas relevantes son las penalidades ESTIMADAS.
* **Personal.** La carga máxima corresponde a los trabajadores habilitados para la plegadora (habilidades SIMULADAS). La utilización media del personal es baja porque la base registra 5 742 h de proceso frente a 52 200 h disponibles: esa brecha (PV-04) debe explicarse con datos reales antes de concluir nada sobre la dotación.
* **Cómputo.** `brecha_max` = 0 y `eventos_optimos` = `eventos_milp` indican que todos los eventos terminaron con óptimo demostrado por HiGHS.
