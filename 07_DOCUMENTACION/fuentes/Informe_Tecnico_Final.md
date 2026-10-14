---
title: "SAGAPI v2.0 — Informe técnico final"
subtitle: "Programación y reprogramación MILP con averías, personal y horizonte rodante: diseño, validación y resultados"
lang: es
---

# Resumen ejecutivo

La versión 2.0 reemplaza la entrega académica v1.4.0 con un sistema por capas, verificado y reproducible. Lo esencial:

1. **Formulación corregida.**
   * Se eliminó R11, que no restringía nada.
   * Se agregó R12 para que el curado en horno no se parta entre tramos de jornada.
   * Se corrigió el big-M de las ventanas de avería.
   * Se admite capacidad $k>1$.
   * La jerarquía de objetivos es explícita y configurable, sin mezclar unidades.
   * Todo se validó por enumeración exhaustiva: 438/438 microinstancias coinciden.
2. **Personal.** Los 25 trabajadores se tratan con tres herramientas:
   * un certificado de cobertura demostrado, que vuelve redundantes las restricciones laborales cuando se cumple;
   * una asignación MILP equilibrada de todas las operaciones del año;
   * una reparación laboral cuando el certificado falla.

   La matriz de habilidades es SIMULADA y puede reemplazarse por la real sin tocar el código.
3. **Horizonte rodante sistémico.**
   * Todos los pedidos activos entran en cada evento y el estado persiste entre periodos.
   * Las decisiones congeladas se respetan y ninguna operación se produce dos veces.
   * Los KPI se miden sobre el sistema completo.
4. **Comparación justa:** FIFO (práctica actual aproximada), EDD y MILP con las mismas restricciones y el mismo verificador independiente.
5. **Resultados** (datos SIMULADOS, año 2025 con 12 averías de la plegadora):
   * Frente a FIFO+CONV, el MILP reduce la tardanza ponderada de 1 115 a 307 h y los pedidos atrasados de 74 a 33.
   * Frente a EDD, reduce la tardanza ponderada un 62 %, pero **atrasa 5 pedidos más** (33 frente a 28).
   * Con la regla `PENALIDAD_FIJA` se obtienen 19 atrasados, a costa de más tardanza ponderada.
   * La elección de la regla es una decisión de la empresa, documentada con sus consecuencias.
6. **Límites.** Pedidos, averías y habilidades son simulados y los tiempos de ruta son estimados. Un programa factible y verificado **no está validado en planta**. Las cifras no son ahorros de SAGAPI.

# 1. Alcance y entregables

| N.º | Entregable | Ubicación |
|---|---|---|
| 1 | Código | `01_CODIGO_PYTHON/` (`Programa_principal.py`, `sagapi/`, `herramientas/`, `requirements.txt`) |
| 2 | Base corregida y diccionario | `02_BASE_DATOS/SAGAPI_BASE_CORREGIDA_FINAL.xlsx`, `Diccionario_de_datos.xlsx` |
| 3 | Formulación MILP | `03_MODELO_MATEMATICO/Formulacion_MILP_Actualizada.pdf` |
| 4 | Informe técnico | este documento |
| 5 | Auditoría de correcciones | `06_AUDITORIA_Y_VALIDACION/Informe_Correcciones.pdf`, `Matriz_Errores.xlsx` |
| 6 | Resultados computacionales | `04_RESULTADOS/Informe_Resultados_Computacionales.pdf` y tablas |
| 7 | Informe de KPI | `04_RESULTADOS/Indicadores_KPI/Informe_KPI.pdf` |
| 8 | Gráficos | `05_GRAFICOS/` (28 figuras, todas de corridas reales) |
| 9 | Pruebas de validación | `tests/`, `06_AUDITORIA_Y_VALIDACION/Reporte_Pruebas/` |
| 10 | Manual de usuario | `07_DOCUMENTACION/Manual_Ejecucion.pdf` |

# 2. Arquitectura

| Capa | Módulo | Responsabilidad |
|---|---|---|
| Datos | `datos/esquema.py`, `lector.py`, `calidad.py`, `carga.py` | Esquema declarado, lectura estricta (valores y fórmulas), controles Q00–Q17, modelo de datos tipado. Los errores detienen la ejecución |
| Instancia | `instancia.py`, `calendario.py` | Conjuntos y parámetros, unidades de capacidad $k$, eje de horas productivas y tramos continuos |
| Modelo | `modelo/milp.py` | Formulación R1–R10, R12 y objetivos |
| Solucionador | `solver.py` | HiGHS (API pública de SciPy), estados distinguidos, verificación algebraica del vector |
| Optimización | `optimizacion.py` | Lexicográfico único, respaldo heurístico rotulado, post-proceso coherente |
| Estado y simulación | `estado.py`, `simulacion.py` | Partición $O^C/O^E/O^I/O^P$, horizonte congelado, recuperación A/B, tramos parciales, controles de inmutabilidad |
| Reglas | `reglas.py` | FIFO, EDD, reacción convencional, cronogramas semiactivos (respetan R12 y personal) |
| Personal | `personal.py` | Certificado de cobertura, reparación laboral, MILP de asignación |
| Verificación | `verificacion.py` | Verificador independiente R1–R12 y L1–L5 |
| KPI | `indicadores.py` | Definiciones, fórmulas, unidades y procedencia |
| Reportes | `reportes/graficos.py`, `reportes/excel.py` | Figuras y libro de resultados, solo desde `04_RESULTADOS` |
| Interfaz | `cli.py`, `experimentos.py`, `escenarios.py` | Comandos, registro (`logging`), códigos de salida, experimentos E0–E5 |

Excepciones de dominio: `ErrorDatos` (código 2) y `ErrorSimulacion` (código 3). Todas las rutas son relativas a la carpeta del proyecto y las dependencias tienen versiones fijas.

# 3. Datos

* **Base única** de 26 hojas: maestros, registros reales vacíos (plantillas), simulación y configuración.
* **Naturaleza de cada dato:** REAL, REFERENCIA, CALCULADO, ESTIMADO, SIMULADO, CONFIGURACION o PENDIENTE.
* **Controles previos a la optimización:**
  * tipos, rangos y dominios;
  * claves e integridad referencial;
  * consistencia de rutas, elegibilidad, fechas, calendario, personal y eventos;
  * factibilidad elemental (pedidos con plazo menor que su ruta).
* **Base final:** 0 errores y 46 advertencias explicadas.

# 4. Formulación (síntesis; detalle en el documento 3)

* **Variables:** $S_o$, $x_{om}$, $y_{ab}$, $z_{ow}$, $k_o$, $T_j$, $U_j$ y desviaciones.
* **Restricciones:**
  * asignación (R1) y disponibilidad (R2);
  * precedencia y liberación (R3);
  * capacidad por unidad mediante disyunción (R4–R5);
  * ventanas futuras de avería o mantenimiento (R6);
  * tardanza (R7–R8) y penalidad diaria con tope (R9);
  * estabilidad (R10);
  * continuidad de las operaciones no interrumpibles (R12).
* **Objetivos lexicográficos:**
  * P1 $\sum w_jT_j$ (h ponderadas);
  * P2 $\sum P_jU_j$ (S/, estimado);
  * P3 estabilidad (h equivalentes), solo al reprogramar.

  Alternativas: `PENALIDAD_FIJA` (reproduce v1.4) y `PENALIDAD_DIARIA_CON_TOPE`.
* **Big-M:** cada big-M es el mínimo válido sobre una cota $UB$ demostrada.
* **Materiales y setups dependientes de la secuencia:** no se modelan porque no hay datos confiables. Se declara así, sin inventar restricciones.

# 5. Validación

| Tipo | Evidencia | Resultado |
|---|---|---|
| Matemática (exhaustiva) | 438 microinstancias aleatorias: 2 jerarquías, recurso de 2 unidades, R12, averías actuales, simultáneas y futuras, políticas A y B | 438/438 coinciden con el óptimo enumerado |
| Por restricción | 10 pruebas dirigidas (R1–R12), cada una con su violación detectada por el verificador | Aprobadas |
| Datos | 11 pruebas: cada defecto (Q01, Q03, Q04, Q05, Q06, Q07, Q10) bloquea; reemplazo de la matriz de habilidades por la REAL | Aprobadas |
| Personal | Certificado, flujo con dotación 2, reservas, asignación anual, verificador L1–L5, secuenciación forzada con 1 trabajador, personal insuficiente | Aprobadas |
| Horizonte rodante | Partición, políticas A/B, año con averías sin duplicados, horizonte congelado, mantenimiento anunciado, coherencia de KPI | Aprobadas |
| Estados del solucionador | Óptimo, infactible, no acotado, verificación algebraica, límite de tiempo (nunca declarado óptimo) | Aprobadas |
| Regresión v1.4 | Caso S06A y 8 corridas anuales | Idénticos salvo 1 corrida (documentada) |
| Extremo a extremo | CLI `validar`, `programar` y `caso`; base no modificada; gráficos sin datos inventados | Aprobadas |

**Total:** 118 pruebas aprobadas y 4 omitidas por diseño, ejecutadas en Python 3.13 y de nuevo desde el ZIP descomprimido en un entorno limpio (ver `Reporte_Pruebas/`).

# 6. Resultados principales

![KPI E1 S20A](05_GRAFICOS/Comparaciones/E1_kpis_S20A.png)

| S20A (12 averías de PLE-01) | FIFO+CONV | EDD+EDD | MILP+MILP |
|---|---|---|---|
| Atrasados / OTD | 74 / 22,9 % | **28 / 70,8 %** | 33 / 65,6 % |
| Σ w·T (h ponderadas) | 1 114,8 | 801,9 | **307,3** |
| Σ T (h) | 1 276,4 | 509,5 | **286,5** |
| Penalidad ESTIMADA (S/) | 130 474 | 86 852 | **80 128** |
| Desviación por averías (h) | 967 | 1 227 | **609** |
| Eventos con óptimo demostrado | — | — | 36/36 |

**Hallazgos (favorables y desfavorables):**

1. **El beneficio del MILP viene sobre todo de la secuenciación** al llegar los pedidos (MILP+CONV: 309,6), no de la reacción a las averías (FIFO+MILP: 852,0).
2. **Compromiso entre tardanza ponderada y número de atrasos.** Con la regla por defecto, el MILP atrasa más pedidos que EDD. Con `PENALIDAD_FIJA` obtiene 19 atrasados (OTD 80,2 %) pero un 29–35 % más de tardanza ponderada. La empresa debe elegir según la estructura real de sus penalidades.
3. **Miopía del horizonte rodante.** La reacción MILP es mejor que la convencional en 35 de 38 escenarios de avería, pero **peor en S14B** (averías recurrentes, política B). Con averías 4 veces más largas, la desviación del MILP supera a la de CONV.
4. **Escalabilidad.** Con carga ×1,5, 2 eventos terminan al límite de tiempo (brecha máxima 14 %). Esas soluciones son factibles y verificadas, pero no óptimas demostradas.
5. **Plegadora.** Es el cuello de botella de la instancia (utilización 68–70 %, mayor espera en cola). PER-01 y CCH-01 también acumulan esperas largas en FIFO.
6. **Personal.** Con las habilidades SIMULADAS:
   * la dotación no restringe la programación, ni siquiera con 15 trabajadores;
   * la asignación equilibrada concentra la mayor carga en los 3 habilitados para la plegadora (483 h/año).

   La utilización media del personal (≈10 %) refleja la brecha PV-04 entre las horas de proceso y las horas disponibles, que debe explicarse con datos reales.
7. **Costos operativos.** Prácticamente iguales entre métodos (diferencia < 1 %). No se reportan ahorros de costos.
8. **Eficiencia del modelo.** Sin R11, el modelo tiene entre 10 % y 21 % menos variables con el mismo óptimo que v1.4. R12 y la tardanza como P1 hacen algunos subproblemas más lentos (hasta 22,5 s). El presolve de HiGHS se mantiene porque acelera 5 de 8 casos.

Detalle completo en el informe de resultados computacionales y en el informe de KPI.

# 7. Limitaciones y trabajo pendiente

Ver `07_DOCUMENTACION/Limitaciones_y_Supuestos.md`. Prioridades para validar en planta:

* tiempos cronometrados de la plegadora y de las demás rutas (PV-01);
* matriz real de habilidades (PV-02);
* pedidos reales con fechas, precios y penalidades (PV-03);
* distribución del tiempo del personal (PV-04);
* historial de paradas (PV-07);
* confirmación de jornada y feriados.

Con esos datos cargados en las plantillas (hojas 12–16), el mismo programa se ejecuta sin cambios de código. Las conclusiones de este informe deben recalcularse en ese momento.

# 8. Ejecución

```bash
pip install -r 01_CODIGO_PYTHON/requirements.txt
cd 01_CODIGO_PYTHON
python Programa_principal.py validar
python Programa_principal.py todo        # E0–E5 (≈ 45 min), gráficos y libro de resultados
cd .. && python -m pytest tests -q        # ≈ 2 min
```

Manual completo: `07_DOCUMENTACION/Manual_Ejecucion.pdf`.
