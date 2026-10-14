# Registro de cambios — SAGAPI

Cada cambio indica su **justificación** y la **evidencia** que lo respalda. La versión inicial (v1.4.0) se conserva sin modificaciones en `06_AUDITORIA_Y_VALIDACION/Evidencias_Validacion/version_inicial_v1_4_0/` (código, pruebas y Excel v1.2). En el repositorio también está en `historial/v1_4_0_original/`.

## [2.0.0] — 2026-10-14 · Versión optimizada final

Proceso en ciclos controlados: (1) matriz de seguimiento inicial con evidencia; (2) base de datos y controles de calidad; (3) correcciones P0 → P1 → P2 → P3 en código y formulación, cada una con su prueba; (4) experimentos, KPI y gráficos desde corridas reales; (5) documentación y empaquetado verificado. Seguimiento detallado en `06_AUDITORIA_Y_VALIDACION/Matriz_Errores.xlsx`.

### Base de datos

| Cambio | Justificación | Evidencia |
|---|---|---|
| Un único libro `SAGAPI_BASE_CORREGIDA_FINAL.xlsx` que integra la base operativa y la de simulación de la etapa 1, con hojas numeradas por tipo (maestros 01–11, registros reales 12–16, simulación 20–28) | Una sola fuente de verdad que el programa lee; la separación REAL/SIMULADO se conserva en la hoja y en la columna `naturaleza` | `validar`: 0 errores |
| `Diccionario_de_datos.xlsx` (tipo, unidad, obligatoriedad, rango, naturaleza y uso en Python de cada columna) | Esquema explícito y verificable | `sagapi/datos/esquema.py` |
| 06_RUTAS: `trabajadores_requeridos` (=1) e `interrumpible_en_pausas` (0 para el curado POR_LOTE) | Datos que el modelo necesita para L1 y R12. El valor 1 es el supuesto de v1.4 (ESTIMADO) | Diccionario |
| 11_PARAMETROS / 28_CONFIG_MODELO: `lote_no_cruza`, `horizonte_congelado_h`, `fuente_habilidades`, `fuente_pedidos`, `regla_objetivo`, `limite_asignacion_personal_s` | Configuración desde la base, sin tocar el código | Manual §5 |
| 27_ESCENARIOS_OPERATIVOS_SIM (carga, plazos, ausencias, indisponibilidad) | Escenarios operativos exigidos, rotulados SIMULADO | E3 |
| 04_DESPIECE: el área de chapa se escribe como valor y el control Q08 la contrasta con ancho × alto | La columna mezclaba fórmulas y valores en un campo de entrada (hallazgo N-04) | `validar` |
| Se eliminan `99_LISTAS` y `09_PROGRAMA_FIFO_REF` | El FIFO de referencia lo calcula el programa; ninguna hoja de resultados vive en la base | C-19 |

### Capa de datos (`sagapi/datos/`, reemplaza `datos.py`)

* **Esquema declarado y lectura estricta** (`esquema.py`, `lector.py`). Se leen valores y fórmulas; una fórmula en una columna de entrada es un error (C-16). Cada celda se convierte al tipo declarado y se comprueban la obligatoriedad, los rangos y los dominios.
* **Controles de calidad Q00–Q17** (`calidad.py`): claves duplicadas, integridad referencial, consistencia de rutas, fechas, calendario, personal, eventos y parámetros, y factibilidad elemental (tardanza inevitable). Un ERROR detiene la ejecución con hoja, fila, columna y código de salida 2 (C-17).
* Un único calendario: el feriado se aplica en un solo lugar (C-18). Las horas de liberación y de vencimiento se leen de la base (C-09).

### Formulación y modelo (`sagapi/modelo/milp.py`, reemplaza `modelo.py`)

| Cambio | Justificación | Evidencia |
|---|---|---|
| Se elimina R11 (reserva de personas sin variables de programación) | No restringía el cronograma: daba una cobertura laboral aparente (C-01) | Formulación §5, §7 |
| Nueva R12: operaciones no interrumpibles dentro de un tramo continuo ($k_o$ entero) | El curado se partía entre jornadas, lo que es físicamente imposible (C-04) | `test_R12_*`, enumeración |
| Big-M de R6: $UB+p-a_w$ (antes $UB$) | El valor anterior no relajaba la fila cuando $a_w<p$ (C-07) | `test_R6_ventana_futura_y_bigM_valido` |
| Capacidad $k$: unidades $m\#1..m\#k$ | Antes toda capacidad era unitaria (C-03) | `test_R4_R5_*`, enumeración con 2 unidades |
| Jerarquía de objetivos configurable; por defecto P1 Σw·T, P2 penalidad estimada, P3 estabilidad | La penalidad fija (estimada, escalonada) como primer objetivo sacrificaba la tardanza; las unidades no se mezclan (C-05) | Formulación §8; E4 |
| UB incluye la holgura de R12; los pares disyuntivos solo se crean entre pedidos distintos con unidades comunes | Cota válida y modelo más pequeño | Formulación §6, §11 |

### Solución (`optimizacion.py`, `solver.py`)

* **Un único procedimiento lexicográfico** (reemplaza las tres implementaciones de v1.4: C-21) con estado global, respaldo heurístico rotulado `HEURISTICA_VERIFICADA` y verificación algebraica del vector en cada fase.
* **Estados distinguidos:** óptimo, factible al límite de tiempo, sin solución al límite, infactible, no acotado, solución inválida, error y heurística.
* Opción `presolve` para medir su efecto (E5).

### Personal (`personal.py`, reemplaza `personal.py`, `personal_integrado.py`, `rodante_personal.py`, `auditoria_personal.py`, `cobertura_externa.py`, `jornada_piloto.py`)

* **Certificado de cobertura por flujo máximo** (condición suficiente, demostrada en la formulación §7). Cuando se cumple, las restricciones laborales son redundantes y no se agregan.
* **MILP de asignación de trabajadores** para todas las operaciones del año, con cliques maximales de intervalos (sin solapes exacto) y equilibrio min-max de carga (C-02).
* **Reparación laboral** cuando no hay certificado; los resultados se rotulan heurísticos.
* Verificación L1–L5: dotación, habilidad, sin solapes, ≤ 8 h por día y disponibilidad.
* **Justificación de la eliminación de los módulos piloto:** cubrían el 2 % y el 0,17 % de las operaciones y duplicaban la lógica; la nueva capa cubre el 100 % con una sola implementación.

### Horizonte rodante (`estado.py`, `simulacion.py`)

* En cada evento se incluyen todos los pedidos activos (C-12). El estado persiste entre periodos: programa, tiempos restantes y tramos parciales.
* Horizonte congelado (`congelar_h`) y controles de inmutabilidad en cada evento: nada iniciado ni congelado vuelve a decidirse y nada completado cambia.
* Tramos interrumpidos registrados aparte: ocupan la unidad y el personal, pero no cuentan como producción (sin producción duplicada).
* Los mantenimientos planificados se conocen desde el inicio (hallazgo N-03).
* La comprobación previa de personal falla con un mensaje claro (hallazgo N-02).

### Experimentos, KPI y reportes

* `experimentos.py` reescrito (E0–E5), con las mismas restricciones, datos y verificador para todos los métodos (C-11). E2 evalúa el impacto sobre el año completo (C-08). La sensibilidad lee `26_SENSIBILIDAD_SIM` (C-15).
* **Retirados, con justificación:** Monte Carlo de averías (circular: remuestreaba averías sintéticas, C-14); prueba de Wilcoxon (escenarios dependientes, C-13); frente de Pareto ε-restricción y variante MILP-MONO (sustituidos por la jerarquía explícita y la sensibilidad a β, que muestra el compromiso tardanza–estabilidad).
* `indicadores.py`: KPI con fórmula, unidad y procedencia; cota inferior de la tardanza; utilización, ocio, espera en cola, carga laboral, costos estimados y tiempo de cómputo (C-25).
* `reportes/`: gráficos y libro de resultados separado, construidos solo con archivos de resultados (C-19). Se reemplaza `reportes.py`, que escribía en la base de entrada.

### Arquitectura, calidad y pruebas

* Capas separadas, CLI con `logging`, códigos de salida y excepciones de dominio (`ErrorDatos`, `ErrorSimulacion`) (C-22). Versiones fijadas en `requirements.txt` (C-23).
* Pruebas reescritas (C-24): enumeración exhaustiva, una prueba por restricción, calidad de datos, personal, horizonte rodante, regresión con v1.4, estados del solucionador y CLI.
* Corrección del verificador (hallazgo N-01): informaba con KeyError en lugar de reportar una unidad no elegible.

### Equivalencia con v1.4

Con la configuración de v1.4 (`regla_continuidad = NINGUNA`, `regla_objetivo = PENALIDAD_FIJA`), v2.0 reproduce exactamente los valores de v1.4 en los siguientes casos:

* el caso S06A (CONV 7/8 y S/ 14 834; EDD 6/8 y S/ 15 299; MILP 4/8, S/ 9 066,34 y Σw·T 249,18);
* el año S00 con FIFO+CONV (73; S/ 127 293,85), EDD+EDD (27; S/ 83 231,19) y MILP+CONV (19; S/ 41 519,81);
* el año S20A con FIFO+CONV (74; S/ 130 474), FIFO+MILP (55; S/ 94 970), EDD+EDD (27; S/ 84 065) y MILP+MILP (19; S/ 41 520).

Excepción: S20A MILP+CONV da 22 atrasados frente a 23 (hallazgo N-05, ver `Evidencias_Validacion/regresion_v14.md`).

## [1.4.0] — versión inicial entregada

Conservada sin cambios. Diagnóstico en `06_AUDITORIA_Y_VALIDACION/Evidencias_Validacion/etapa1_auditoria/informes/E6_Diagnostico_Codigo.md`.
