---
title: "SAGAPI v2.0 — Informe de auditoría de correcciones"
subtitle: "Qué se encontró, qué se corrigió, cómo se verificó y qué no puede verificarse sin datos de la empresa"
lang: es
---

# 1. Método

1. **Estado inicial congelado.** Antes de tocar el código se registró la matriz de seguimiento inicial con evidencia (`Evidencias_Validacion/Matriz_Seguimiento_INICIAL.md`). Su punto de partida es la etapa 1, que comprende el diagnóstico E6, el plan E7 y los 84 errores del Excel.
2. **Correcciones por prioridad** P0 → P1 → P2 → P3. Cada una:
   * tiene una justificación técnica;
   * está ligada a una prueba automática o a un archivo de resultados que la respalda;
   * figura en `07_DOCUMENTACION/Registro_Cambios.md`.
3. **Estados finales** con cuatro categorías:
   * **Corregido y validado:** existe evidencia ejecutada.
   * **Parcialmente corregido.**
   * **No verificable:** requiere datos de SAGAPI.
   * **Pendiente.**

   Un estado «Corregido y validado» nunca se asigna sin una prueba ejecutada o un resultado que lo respalde.
4. **Hallazgos nuevos.** Los problemas encontrados durante la etapa 2 se agregaron a la matriz (N-01…N-05).

# 2. Resumen de estados (`06_AUDITORIA_Y_VALIDACION/Matriz_Errores.xlsx`)

| Tipo | Corregido y validado | Parcialmente corregido | No verificable | Pendiente | Total |
|---|---|---|---|---|---|
| Código y modelo (C-xx, N-xx) | 27 | 1 | 2 | 0 | 30 |
| Base de datos (E-001…E-084) | 55 | 2 | 27 | 0 | 84 |
| Datos de la empresa (PV-01…PV-18) | 0 | 0 | 18 | 0 | 18 |
| **Total** | **82** | **3** | **47** | **0** | **132** |

Ningún ítem queda «Pendiente» por falta de trabajo. Todo lo que no está corregido requiere información que solo la empresa puede dar: tiempos cronometrados, matriz real de habilidades, pedidos reales, historial de paradas, contratos y precios.

# 3. Correcciones críticas (P0)

| ID | Problema (v1.4) | Corrección | Verificación |
|---|---|---|---|
| C-01 | R11 «reservaba» personas por máquina sin variables de programación: no restringía el cronograma y daba una cobertura laboral aparente | Se eliminó del MILP. Se agregaron:<br>• un certificado de cobertura por flujo máximo (condición suficiente demostrada);<br>• una asignación MILP de los 25 trabajadores a todas las operaciones;<br>• una reparación laboral cuando no hay certificado;<br>• un verificador L1–L5 | `tests/test_personal.py` (9 pruebas), incluido el caso en que una sola persona para dos máquinas obliga a secuenciar; asignación anual óptima sin violaciones |
| C-04 | El curado en horno (POR_LOTE) podía partirse entre jornadas | R12 en el MILP, las reglas y el verificador | `test_R12_*`; enumeración con 317 casos con R12 |
| C-16 | Las fórmulas en columnas de entrada se leían como vacías | Lectura estricta: error Q01 | `test_defecto_detectado_y_bloquea[Q01]` |
| C-17 | Esquema implícito | Esquema declarado y controles Q00–Q17; los errores detienen la ejecución (código 2) | `tests/test_datos_calidad.py` (11 pruebas) |
| C-19 | El programa escribía en la base de entrada | Libro de resultados separado; la base es de solo lectura | `test_base_no_se_modifica` (SHA-256 antes y después) |

# 4. Correcciones importantes (P1)

| ID | Corrección | Verificación |
|---|---|---|
| C-02 | El personal cubre el 100 % de las operaciones (antes, pilotos del 2 % y del 0,17 %) | `carga_trabajadores_*.csv`; verificación L1–L5 = 0 violaciones |
| C-03 | Capacidad $k$ por unidades idénticas | `test_R4_R5_*`; enumeración con 2 unidades. La base actual solo tiene $k=1$: no hay un caso real con $k>1$ |
| C-05 | Jerarquía de objetivos configurable, con la tardanza ponderada primero | E4 muestra el compromiso frente a `PENALIDAD_FIJA` (más atrasados, menos tardanza ponderada) |
| C-07 | Big-M de R6 $=UB+p-a_w$ | `test_R6_ventana_futura_y_bigM_valido`; enumeración con 170 casos con ventanas futuras |
| C-08, C-11, C-12 | Evaluación sistémica del año completo; comparadores FIFO y EDD con las mismas restricciones; todos los pedidos activos en cada evento | E1, E2, E3; `test_anio_con_averias_sin_duplicados` |
| C-18 | Una sola lectura de feriados | E4 (`aplicar_feriados`) |
| N-01 | El verificador lanzaba KeyError ante una unidad no elegible | `test_R1_R2_asignacion_y_alternativa` |
| N-02 | El personal insuficiente producía un error interno poco claro | `test_personal_insuficiente_detiene_con_mensaje_claro` |
| N-04 | Fórmulas mezcladas en el área de chapa | `validar`: 0 errores; control Q08 |

# 5. Correcciones P2 y P3

* **Arquitectura y calidad:** C-09, C-10, C-13, C-15, C-21, C-22, C-23, C-24 y C-25, corregidos y validados (ver la matriz).
* **N-03:** el mantenimiento planificado ahora se trata como ventana anunciada (`test_mantenimiento_planificado_es_anunciado`).
* **C-14:** el Monte Carlo circular se retiró. Queda «Parcialmente corregido» porque la robustez frente a averías reales requiere su historial (PV-07).
* **C-06:** la precedencia sin lotes de transferencia queda «No verificable» (requiere el flujo real de la planta).
* **N-05:** la diferencia S20A MILP+CONV frente a v1.4 está documentada en `Evidencias_Validacion/regresion_v14.md`.

# 6. Validación global

| Evidencia | Resultado |
|---|---|
| Enumeración exhaustiva (`Reporte_Pruebas/enumeracion_exhaustiva.csv`) | 438/438 microinstancias: el MILP reproduce el óptimo lexicográfico enumerado (P1, P2 y, en 66 casos, P3) |
| Pruebas automáticas (`Reporte_Pruebas/pytest_*`) | 118 aprobadas y 4 omitidas por diseño: microinstancias de programación inicial con más de 7 operaciones, demasiado grandes para enumerar. Ejecutadas en Python 3.13 y en un entorno limpio desde el ZIP |
| Regresión con v1.4 (`Evidencias_Validacion/regresion_v14.md`) | Valores idénticos en el caso S06A y en 7 de 8 corridas anuales; 1 diferencia documentada |
| Verificador independiente en todas las corridas de E1–E5 | 0 violaciones de asignación, capacidad, precedencia, liberación, ventanas, continuidad, duración y personal |
| Calidad de la base final | 0 errores; 46 advertencias explicadas (fechas en fin de semana, 3 pedidos con plazo inferior a su ruta) |

# 7. Lo que no se corrigió y por qué

Los 47 ítems «No verificable» y los 3 «Parcialmente corregido» dependen de datos que no existen en la base:

* tiempos cronometrados (PV-01);
* habilidades reales (PV-02);
* pedidos reales (PV-03);
* distribución real del tiempo del personal (PV-04);
* historial de paradas (PV-07);
* precios, penalidades contractuales, jornada y feriados reales.

**No se inventaron esos datos.** Hay plantillas para cargarlos (hojas 12–16) y un mecanismo probado para reemplazar la matriz simulada de habilidades (Manual §7). Hasta entonces, todo programa generado es matemáticamente factible y verificado, **pero no está validado en planta**.
