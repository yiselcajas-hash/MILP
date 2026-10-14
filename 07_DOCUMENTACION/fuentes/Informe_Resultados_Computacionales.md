---
title: "SAGAPI v2.0 — Resultados computacionales"
subtitle: "Experimentos E0–E5: programación anual por eventos, averías, escenarios operativos, sensibilidad y rendimiento"
lang: es
---

> **Lectura obligatoria.** Todas las corridas usan pedidos, averías y habilidades **SIMULADOS** y tiempos de ruta **ESTIMADOS**. Las diferencias entre métodos muestran cómo se comportan los métodos con esos datos: **no son ahorros ni mejoras históricas de SAGAPI**. Cada cifra sale de archivos de `04_RESULTADOS/` generados por `python Programa_principal.py experimentos` (registro: `04_RESULTADOS/registro_experimentos.log`, 2 771 s en total). Todos los programas pasaron el verificador independiente sin violaciones.

# 1. Condiciones de las corridas

* **Equipo:** contenedor Linux con Python 3.13 y HiGHS a través de SciPy 1.18.1, con un hilo y semilla 0. Límite de 60 s por fase lexicográfica y brecha relativa de $10^{-5}$.
* **Configuración por defecto de la base:**
  * jerarquía `TARDANZA_PONDERADA` (P1 Σw·T, P2 penalidad estimada, P3 estabilidad);
  * continuidad `TRAMO` (L = 4 h) y β = 8;
  * horizonte congelado de 0 h y feriados sin aplicar.
* **Comparación justa.** Todos los métodos usan el mismo subproblema en cada evento: mismas operaciones libres, mismas ventanas de avería, mismos tiempos restantes, mismas unidades disponibles y mismo verificador.
  * FIFO = orden de llegada en el recurso principal; aproxima la práctica actual.
  * EDD = fecha comprometida más próxima, eligiendo la unidad que termina antes.
  * CONV = conservar unidad y orden, desplazando a la derecha.
  * MILP = procedimiento lexicográfico.
  * Combinación «A+B» = A al llegar pedidos y B ante averías.
* **Personal:** en todas las corridas se cumplió el certificado de cobertura (15 unidades cubiertas por 15 trabajadores distintos y habilitados). Por eso las restricciones laborales no se agregaron al MILP. La asignación de trabajadores de las corridas anuales es óptima (MILP min-max) y sin violaciones L1–L5.

# 2. E0 — Datos, instancia y cuello de botella

| Elemento | Valor |
|---|---|
| Calidad de la base | 0 errores; 46 advertencias (43 fechas en fin de semana, 3 pedidos con plazo menor que su ruta); 3 avisos de naturaleza |
| Instancia | 96 pedidos, 1 152 operaciones, 15 unidades; horizonte de 283 días productivos (2 264 h) |
| Tardanza inevitable (cota inferior, capacidad infinita) | 3 pedidos, 27,5 h en total (49,5 h ponderadas): **ningún método puede bajar de ese valor** |
| Carga teórica de la plegadora PLE-01 | 1 437 h = 63 % de las horas del año |
| Programa FIFO | PLE-01: utilización 68 % y 1 245 h de espera en cola (máximo de la planta) |

![Diagnóstico del cuello de botella](05_GRAFICOS/Utilizacion_Recursos/diagnostico_cuello_botella.png)

**Conclusión sobre la plegadora (sin forzarla).** Con los tiempos estimados, PLE-01 es el recurso con mayor carga, utilización y espera, así que **sí es el cuello de botella** de la instancia. No es el único punto de congestión: en FIFO, PER-01 (1 191 h) y CCH-01 (1 075 h) también acumulan esperas largas aunque su utilización sea del 31–37 %. La conclusión depende de los tiempos de ruta, que no están cronometrados (PV-01).

# 3. E1 — Año completo por eventos (S00 sin averías, S20A con 12 averías de PLE-01)

| S20A | FIFO+CONV | FIFO+MILP | EDD+EDD | MILP+CONV | MILP+MILP |
|---|---|---|---|---|---|
| Pedidos atrasados (de 96) | 74 | 66 | **28** | 34 | 33 |
| OTD (%) | 22,9 | 31,2 | **70,8** | 64,6 | 65,6 |
| Σ w·T (h ponderadas) | 1 114,8 | 852,0 | 801,9 | 309,6 | **307,3** |
| Σ T (h productivas) | 1 276,4 | 977,6 | 509,5 | 288,0 | **286,5** |
| Tardanza máxima (h) | 48,9 | 43,8 | 44,4 | **36,8** | **36,8** |
| Penalidad ESTIMADA (S/) | 130 474 | 123 309 | 86 852 | 81 848 | **80 128** |
| Desviación por averías Σ\|S−S0\| (h) | 967 | 5 115 | 1 227 | 615 | **609** |
| Eventos MILP óptimos | — | 12/12 | — | 24/24 | 36/36 |
| Tiempo de HiGHS (s, año completo) | 0 | 43,5 | 0 | 17,9 | 22,3 |

En S00 los valores son: FIFO 73 atrasados y Σw·T 1 039,9; EDD 28 y 735,2; MILP 32 y 257,5.

![E1 S20A](05_GRAFICOS/Comparaciones/E1_kpis_S20A.png)

**Lectura (favorable y desfavorable):**

1. **MILP+MILP frente a FIFO+CONV:** Σw·T 72 % menor (1 114,8 → 307,3), 41 atrasados menos y OTD de 22,9 % a 65,6 %.
2. **MILP+MILP frente a EDD (la referencia más exigente):**
   * Σw·T 62 % menor y Σ T 44 % menor.
   * Penalidad estimada 8 % menor y tardanza máxima menor.
   * **Desfavorable:** **5 pedidos atrasados más** (33 frente a 28; OTD 65,6 % frente a 70,8 %). Es el costo de priorizar la tardanza ponderada por valor: el MILP retrasa poco a varios pedidos de menor valor (familia FAM-RAC: 14 atrasados) para no atrasar mucho a los de mayor valor (FAM-LOC: 0 atrasados). EDD hace lo contrario (FAM-RAC 22 atrasados y 451,7 h; FAM-GON 1).
3. **Separación de efectos:**
   * Reprogramar con MILP solo ante averías (FIFO+MILP) reduce Σw·T un 24 %.
   * Programar con MILP al llegar los pedidos (MILP+CONV) la reduce un 72 %.
   * Sobre un plan MILP, reaccionar con MILP en vez de CONV casi no cambia el resultado (309,6 → 307,3).
   * **La mayor parte de la mejora viene de la secuenciación, no de la reacción a las averías.**
4. **Estabilidad.** Reoptimizar un plan FIFO ante averías (FIFO+MILP) mueve mucho el programa (5 115 h de desviación acumulada), aunque P3 minimiza la estabilidad dentro del óptimo de P1 y P2. Con plan MILP, la desviación es la menor de todas.
5. **Costos.** El uso de recursos (≈ S/ 137–138 mil), la energía (≈ 9 000 kWh) y las horas-hombre (≈ 5 750 h) difieren en menos de 1 % entre métodos, porque el trabajo total es el mismo. **No hay ahorro de costos operativos que reportar.** Las diferencias están en el cumplimiento de fechas y en las penalidades estimadas.

![Evolución de la tardanza acumulada](05_GRAFICOS/Comparaciones/evolucion_tardanza_acumulada_S20A.png)

![Distribución de la tardanza](05_GRAFICOS/Comparaciones/distribucion_tardanza_S20A.png)

# 4. E2 — Escenarios de avería sobre el plan FIFO (sistema completo)

38 escenarios de `24_ESCENARIOS_FALLA_SIM` (S01–S19, S21; políticas A y B), cada uno simulado sobre el año completo y comparado con el mismo método sin averías.

| Δ frente a S00 (suma de 38 escenarios) | FIFO+CONV | EDD+EDD | FIFO+MILP |
|---|---|---|---|
| Δ Σw·T (h ponderadas): media / máx. | +10,9 / +36,4 | +16,9 / +134,6 | **−12,3** / +78,5 |
| Δ pedidos atrasados (suma) | +5 | +6 | **−15** |
| Δ penalidad estimada (suma, S/) | +16 433 | +16 167 | **+13 544** |
| Tiempo de reacción (s): media / máx. | 0 | 0 | 5,4 / 28,4 |

* La reacción MILP tiene menor Σw·T que la convencional en 35 de 38 escenarios, la iguala en 2 (S07A/B) y es **peor en 1: S14B** (tres averías recurrentes con política B: +78,5 frente a +36,4).
  * Cada evento se resuelve al óptimo con la información disponible.
  * Pero la secuencia de decisiones óptimas por evento no es óptima para el año: es la miopía propia del horizonte rodante.
* Frente a EDD, la reacción MILP es peor en 6 escenarios (S03A/B, S07A/B, S14B, S17B).
* En S03A/B atrasa un pedido más que CONV.
* Todos los eventos MILP de E2 terminaron con óptimo demostrado.

![Impacto de las averías](05_GRAFICOS/Comparaciones/E2_impacto_fallas.png)

**E2b — reacción sobre el mismo subproblema.** CONV, EDD y MILP resuelven exactamente el mismo subproblema de la primera avería.

| Caso | CONV | EDD | MILP |
|---|---|---|---|
| S06A (8 pedidos, 73 ops) | 7 atr · 205,9 · D 33 | 6 atr · 200,3 · D 1 855 | 6 atr · **142,3** · D 943 |
| S13A (4 pedidos, 35 ops) | 3 atr · 89,3 · D 295 | 4 atr · 160,0 · D 840 | 3 atr · **68,7** · D 550 |
| S19A (8 pedidos, 75 ops) | 8 atr · 164,9 · D 65 | **6 atr** · 205,3 · D 1 434 | 8 atr · **135,4** · D 674 |

(Valores: atrasados · Σw·T · desviación en h.) El MILP siempre logra la menor Σw·T. En S19A atrasa más pedidos que EDD y su penalidad estimada es mayor (S/ 18 280 frente a S/ 15 299). CONV es siempre el más estable.

![Reacción S06A](05_GRAFICOS/Diagramas_Gantt/gantt_reaccion_S06A.png)

# 5. E3 — Escenarios operativos (SIMULADOS)

| Escenario | FIFO+CONV atr · Σw·T | EDD+EDD atr · Σw·T | MILP+MILP atr · Σw·T | Notas |
|---|---|---|---|---|
| Base | 73 · 1 040 | 28 · 735 | 32 · 257 | |
| Carga baja (×0,75) | 3 · 11 | 0 · 0 | 0 · 0 | |
| Carga alta (×1,25) | 96 · 3 275 | 62 · 2 498 | 52 · 1 555 | tardanza inevitable 415 h |
| Carga muy alta (×1,5) | 96 · 9 171 | 94 · 8 447 | 84 · 5 408 | **2 eventos al límite de tiempo, brecha máx. 14 %**; 857 s |
| Plazo ajustado (×0,8) | 96 · 2 554 | 46 · 1 797 | 44 · 1 162 | 2 eventos al límite de tiempo |
| Plazo holgado (×1,25) | 20 · 111 | 6 · 109 | 2 · 14 | |
| Personal 20 / 15 | = base | = base | = base | certificado cumplido: el personal no restringe |
| Mantenimiento PLE (F21) | 73 · 1 045 | 28 · 771 | 33 · 267 | ventana anunciada |
| Averías PLE (F01–F12) | 74 · 1 115 | 28 · 802 | 33 · 307 | = S20A |
| Falla larga (F13) | 73 · 1 062 | 28 · 772 | 33 · 278 | |
| Carga alta + averías | 96 · 3 449 | 64 · 2 822 | 58 · 1 855 | |

![E3](05_GRAFICOS/Comparaciones/E3_escenarios_operativos.png)

* Con carga alta, el MILP atrasa menos pedidos que EDD (52 frente a 62), pero ningún método evita la saturación.
* Con carga muy alta, el modelo por evento crece y HiGHS no demuestra el óptimo en 2 eventos: la solución es factible y verificada, pero su estado es `FACTIBLE_LIMITE_TIEMPO`.
* **Personal:** reducir la dotación a 20 o 15 trabajadores no cambia ningún resultado con la matriz de habilidades SIMULADA. Esto no prueba que la planta pueda operar con 15 personas: la matriz real (PV-02) y la distribución real del tiempo del personal (PV-04) son indispensables para esa conclusión.

# 6. E4 — Sensibilidad (26_SENSIBILIDAD_SIM)

| Factor | Resultado |
|---|---|
| Duración de las averías ×0,5 / 1 / 2 / 4 (S20A) | FIFO+CONV: 74 → 79 atrasados, Σw·T 1 078 → 1 405. MILP+MILP: 33 → 38 atrasados, 282 → 533. **Con ×4 la desviación del MILP (4 325 h) supera a la de CONV (3 937 h).** |
| Regla del objetivo (MILP+MILP) | `PENALIDAD_FIJA`: **19 atrasados (OTD 80,2 %)**, penalidad S/ 41 520, Σw·T 398 (S00) / 430 (S20A). `TARDANZA_PONDERADA`: 32–33 atrasados, S/ 76 682 / 80 128, Σw·T 257 / 307. **Compromiso real:** la regla por defecto reduce la tardanza ponderada un 29–35 % pero atrasa 13–14 pedidos más y casi duplica la penalidad estimada. |
| β = 0 / 8 / 24 (S20A) | Mismos KPI. Con β = 0 aparecen 2 reasignaciones inútiles; con β ≥ 8, ninguna. Efecto pequeño porque la plegadora no tiene recurso alternativo. |
| Horizonte congelado 0 / 8 h | Mismos KPI de cumplimiento; menos operaciones reoptimizadas por evento; desviación 609 → 624 h |
| Factor de la alternativa 1,0 / 1,1 / 1,25 (S15A, S16A) | Efecto pequeño: la reacción MILP usa la alternativa en a lo sumo 1 operación; Σw·T sube 1–7 h |
| Feriados (S00) | Con feriados hay menos horas productivas: FIFO 80 atrasados, MILP+CONV 38 (Σw·T 469) |
| Continuidad TRAMO / JORNADA | Diferencia despreciable (Σw·T 257,5 / 256,8) |

![Regla del objetivo](05_GRAFICOS/Analisis_Sensibilidad/sensibilidad_regla_objetivo.png)

# 7. E5 — Rendimiento y comparación con v1.4 en las mismas condiciones

Mismo subproblema (la primera avería de cada escenario sobre el plan FIFO), mismo equipo y misma versión de HiGHS. v1.4 se ejecutó con su propio código y su Excel v1.2.

| Caso | Versión | Variables | Enteras | Filas | Tiempo HiGHS (s) | P1 / P2 |
|---|---|---|---|---|---|---|
| S06A | v1.4.0 | 567 | 342 | 696 | 4,0 | 9 066,35 / 249,18 |
| S06A | v2.0 config. v1.4 | 507 | 282 | 659 | 3,7 | 9 066,35 / 249,18 |
| S06A | v2.0 por defecto | 514 | 289 | 673 | 8,2 | 142,33 / 13 573,76 |
| S19A | v1.4.0 | 588 | 359 | 729 | 3,6 | 12 511,98 / 149,88 |
| S19A | v2.0 config. v1.4 | 528 | 299 | 692 | 3,0 | 12 511,98 / 149,88 |
| S19A | v2.0 por defecto | 535 | 306 | 706 | 22,5 | 135,37 / 18 279,97 |

* **Equivalencia:** con la configuración de v1.4, v2.0 obtiene los mismos valores óptimos en los 4 casos (S06A, S13A, S19A, S08A).
* **Tamaño:** al eliminar R11, el modelo tiene entre 10 % y 21 % menos variables y entre 17 % y 37 % menos variables enteras, sin cambiar el óptimo.
* **Tiempo:**
  * similar entre v1.4 y v2.0 con la configuración equivalente (corrida única, sujeta a variación);
  * con R12 y la nueva jerarquía, v2.0 tarda más en S06A y S19A (8,2 y 22,5 s): las variables $k_o$ y el objetivo de tardanza son más difíciles;
  * desactivar el presolve empeora el tiempo en 5 de 8 casos (hasta 3×), así que se mantiene activo.
* **Año completo** (S20A, MILP+MILP): por evento hay en promedio 53 operaciones libres, 172 binarias y 0,6 s de cómputo (máximos: 78 operaciones, 323 binarias y 2,7 s).

![E5](05_GRAFICOS/Comparaciones/E5_rendimiento_v14_v20.png)

# 8. Validación matemática

* **Enumeración exhaustiva:** 438 microinstancias. En todas, el MILP coincide con el óptimo lexicográfico enumerado.
  * Cobertura: 317 casos con R12, 170 con ventanas futuras, 66 con comparación de P3 y recurso de 2 unidades.
  * Archivo: `06_AUDITORIA_Y_VALIDACION/Reporte_Pruebas/enumeracion_exhaustiva.csv`.
* **Pruebas automáticas:** ver `Reporte_Pruebas/` (la batería completa se ejecutó dentro del ZIP).
* **Estados de solución:** de todos los eventos MILP de E1–E4, solo 4 (E3, carga muy alta y plazo ajustado) terminaron en `FACTIBLE_LIMITE_TIEMPO`; el resto se resolvió con óptimo demostrado. Ninguno quedó sin solución ni con la verificación fallida.
