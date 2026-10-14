# Entregable 7 — Plan maestro de mejoras del código Python y del MILP

**Principio rector:** cada mejora se justifica por su efecto en la exactitud, el realismo, la eficiencia, la confiabilidad o la utilidad para SAGAPI. **En esta etapa no se reescribe el código**; este plan fija qué hacer, en qué orden y cómo se aceptará cada cambio. Los ID C-xx remiten al Entregable 6, los E-xxx a la matriz de errores del Excel y los PV-xx a los pendientes de validación.

> **Advertencia previa.** Ninguna mejora de código vuelve "real" un resultado obtenido con tiempos, pedidos, habilidades y fallas simulados. Los datos de la Fase 0 (PV-01 a PV-04) condicionan la utilidad de todo lo demás y se pueden pedir **en paralelo** al trabajo de código.

---

## 1. Matriz de priorización

| N.º | Problema | Gravedad | Mejora propuesta | Justificación | Prioridad |
|---|---|---|---|---|---|
| M-00 | Afirmaciones de la memoria más amplias que la evidencia: "restricciones de asignación de trabajadores", beneficio frente al FIFO atribuido a la reprogramación (C-01, C-11) | Crítica | Corregir el texto académico: R11 es una cobertura estática; la mejora frente al FIFO se debe sobre todo a la secuenciación (EDD logra 46 de los 54 pedidos de mejora); la cobertura de los pilotos es del 2 % y 0,17 % | Evita conclusiones indefendibles; costo nulo | **P0** |
| M-01 | Tiempos, pedidos, habilidades y brecha de horas-hombre sin datos reales (PV-01 a PV-04; E-037, E-046, E-051, E-063) | Crítica | Campaña de datos con las plantillas `12_REG_ENTREGAS` a `16_REG_HABILIDADES` de la base operativa. Prioridad: cronometrar plegado, perforación, armado y corte de los 8 productos | Sin esto el modelo optimiza supuestos | **P0** |
| M-02 | Lectura frágil y silenciosa del Excel (C-16, C-17, C-18, C-09) | Crítica | Nuevo lector `sagapi/datos_v2.py` para OPERATIVA + SIMULACION por claves, con esquema declarado: tipos, obligatorios, dominios y error ante fórmulas en columnas de entrada | Hoy un cambio razonable en el Excel cambia resultados sin aviso | **P0** |
| M-03 | Los reportes sobrescriben la base de entrada y pierden imágenes (C-19) | Crítica | `--escribir-excel` escribe en un libro de resultados aparte (`resultados/SAGAPI_RESULTADOS_<fecha>.xlsx`); la entrada se abre en solo lectura | Protege la integridad de los datos | **P0** |
| M-04 | R11 no restringe la programación (C-01) | Crítica | (a) Inmediato: renombrar R11 como "chequeo de cobertura" y sacarlo del MILP, o desactivarlo por defecto y reportarlo aparte. (b) Con PV-02: modelo de personal vinculado al horario (M-04b) | Una restricción que no restringe infla el tamaño y la narrativa | **P0** (a) / **P1** (b) |
| M-05 | Curado partido entre jornadas (C-04) | Alta | Restricción "no cruzar el cierre" para operaciones POR_LOTE: ventanas de cierre como en R6, solo para esas operaciones | Factibilidad física del horno | **P1** |
| M-06 | Comparador débil y diseño experimental sesgado (C-11, C-13) | Alta | Reglas de referencia EDD y ATC además de FIFO; descomponer el efecto en secuenciación (sin fallas) y reprogramación (con fallas sobre la misma base); estadística sobre réplicas independientes | Conclusiones correctamente atribuidas | **P1** |
| M-07 | Objetivo con penalidad fija que sacrifica la tardanza (C-05) | Alta | Según PV-14: (i) penalidad diaria con tope como f1 si es la cláusula real, o (ii) añadir el control de T_max y de la tardanza de pedidos ya atrasados en P2 | En S06A la solución "óptima" aumenta la tardanza ponderada en 43,6 h | **P1** |
| M-08 | Capacidad unitaria en puestos manuales (C-03) | Alta | Recursos con cantidad k: máquinas paralelas idénticas (x_{o,m,u}) o restricción acumulativa con PV-09 | Inspección, embalaje y armado sobrerrestringidos | **P1** |
| M-09 | Miopía de `evento_unico` (C-08) | Alta | Incluir las operaciones FIFO de pedidos futuros como reservas fijas (como ya hace el piloto rodante) o medir los KPI de todos los pedidos | Evita mejoras aparentes a costa de pedidos no modelados | **P1** |
| M-10 | Selección del piloto por índice (C-12) | Media | Elegir por afectación: pedidos con operaciones en la máquina averiada dentro del horizonte, ordenados por holgura | Reduce el sesgo de selección | **P1** |
| M-11 | Personal vinculado al horario a escala (C-02, C-10) | Alta | Con PV-02: disyunciones por trabajador con descomposición (pool de habilidades, fijar y optimizar por ventana) o evaluar CP-SAT solo para este submodelo | La pregunta "¿alcanzan 25 personas?" exige este modelo | **P1** (tras PV-02) |
| M-12 | Tres lexicográficos distintos (C-21) | Media | Una sola función `resolver_lexicografico(modelo, fases, politica_certificacion)` | Coherencia y menos defectos | **P2** |
| M-13 | Big-M de R6 latente (C-07) | Media | Usar `M = UB − a + p` en el término de x y añadir una prueba con a < p | Corrección para averías tempranas | **P2** |
| M-14 | Sensibilidad ignora el Excel (C-15) | Media | Leer los niveles desde `07_SENSIBILIDAD_SIM` | Coherencia datos–código | **P2** |
| M-15 | Pruebas sin cobertura de riesgos (C-24) | Media | Pruebas de esquema, feriados, horno, capacidad, R6, R11; regresión con tolerancias y no con IDs fijos; CI en GitHub Actions | Detecta regresiones de datos y modelo | **P2** |
| M-16 | Dependencias sin fijar; HiGHS sin control (C-23) | Media | `requirements.lock` (pip-tools); registrar versión de HiGHS; evaluar `highspy` directo (hilos, semilla, arranque en caliente) | Reproducibilidad entre equipos | **P2** |
| M-17 | Programa principal monolítico y estilo heterogéneo (C-22) | Media | Mover la lógica de `cmd_*` a `sagapi/pilotos.py`; formateo con ruff; versión única en `sagapi/__init__.py` | Mantenibilidad | **P2** |
| M-18 | Precedencia lineal sin solapes (C-06) | Media | Rutas como grafo (predecesores múltiples) y lotes de transferencia opcionales; añadir pares disyuntivos intrapedido cuando la ruta no sea una cadena | Plazos más realistas; requiere datos de flujo | **P2** (tras datos) |
| M-19 | Verificador incompleto | Media | Extender `verificacion.verificar` a personal, horno no partido y capacidad k; recomputar el objetivo de forma independiente | Factibilidad garantizada | **P2** |
| M-20 | Pipeline reproducible incompleto (C-20) | Media | `herramientas/pipeline.py`: construir BD → recalcular → verificar → experimentos → informe con manifiesto SHA-256 | Trazabilidad extremo a extremo | **P2** |
| M-21 | Indicadores industriales limitados (C-25) | Baja | Utilización por recurso del programa resultante, carga por persona, plazo de entrega, OTD por familia, distribución de la tardanza | Utilidad para la gerencia | **P3** |
| M-22 | Visualización | Baja | Gantt por recurso y por persona; informe HTML único por corrida | Comunicación | **P3** |
| M-23 | Incertidumbre de fallas sin datos (C-14) | Baja | Con PV-07: ajustar MTBF/MTTR por máquina; Monte Carlo con esas distribuciones; holguras protectoras en la plegadora | Robustez basada en evidencia | **P3** (tras datos) |

### Mejoras que **no** se recomiendan ahora

Aumentarían la complejidad sin beneficio comprobable con los datos disponibles:

- **MILP estocástico o robusto con árboles de escenarios:** no hay distribución real de fallas (todas son sintéticas).
- **Metaheurísticas (GA, tabú, ALNS) en lugar del MILP:** los subproblemas actuales (≤ 358 binarias) se resuelven a optimalidad en segundos; se perdería la certificación.
- **Formulación indexada en el tiempo del año completo:** 1 152 operaciones × 2 264 h discretizadas es inmanejable y no aporta precisión.
- **Predicción de fallas con aprendizaje automático:** no hay historial.
- **Migración completa a CP-SAT u otro solucionador:** solo se justificaría para el submodelo de personal a escala (M-11), y debe evaluarse con datos reales primero.
- **Objetivos adicionales (energía, CO₂):** falta el factor de emisión y la tarifa no está verificada; serían indicadores, no objetivos.

---

## 2. Hoja de ruta (orden exacto de implementación)

Cada paso indica el archivo o módulo, el cambio conceptual, las dependencias, los riesgos, las pruebas necesarias y el criterio de aceptación.

### Fase 0 — Inmediata, sin código (en paralelo)

**Paso 1 · M-00 Corregir afirmaciones**
- **Archivos:** `LEEME_ENTREGA_FINAL.md`, memoria, PDF.
- **Cambio:** reformular "restricciones de asignación de trabajadores" (solo cobertura estática en el modelo general; integración real solo en el piloto) y atribuir la mejora frente al FIFO a la secuenciación (EDD 27, MILP 19, FIFO 73).
- **Dependencias:** ninguna.
- **Riesgo:** ninguno.
- **Aceptación:** cada cifra citada en la memoria tiene una fuente en `entrega_v2_0/verificacion`.

**Paso 2 · M-01 Campaña de datos**
- **Archivos:** `SAGAPI_BD_OPERATIVA_v2_0.xlsx` (hojas 12–16).
- **Cambio:** registrar pedidos reales, tiempos cronometrados (≥ 5 observaciones por operación crítica), paradas, habilidades y capacidad de los puestos.
- **Dependencias:** acceso a planta.
- **Riesgo:** datos incompletos; mitigación: priorizar la plegadora y los 8 productos.
- **Aceptación:** el verificador no reporta campos obligatorios vacíos en las plantillas usadas y `origen_tiempo = CRONOMETRADO` en al menos todas las operaciones de plegado.

### Fase 1 — P0 de código (integridad)

**Paso 3 · M-02 Lector v2**
- **Archivos:** nuevo `sagapi/datos_v2.py`; `sagapi/datos.py` queda como adaptador del esquema heredado.
- **Cambio:** leer OPERATIVA + SIMULACION por claves (PRD-, CCH-, OP-) con `data_only=True`. El esquema se declara en una sola tabla y se contrasta con `00_DICCIONARIO`. Hay error explícito ante fórmulas en columnas de entrada, columnas desconocidas en la matriz de habilidades o parámetros ausentes. Se leen la hora de liberación y la de vencimiento.
- **Dependencias:** BD v2.0 (hecha).
- **Riesgo:** divergencia con el lector heredado; mitigación: prueba de equivalencia.
- **Pruebas:** `test_datos_v2.py` con instancias defectuosas (fórmula, columna extra, parámetro ausente) que deben fallar con un mensaje claro, más la **equivalencia**: los parámetros MILP de `datos_v2` deben ser idénticos a los de `datos.leer(MODELO)` (como en V09).
- **Aceptación:** las 50 pruebas actuales y la nueva equivalencia pasan; `verificar_bd_v2.py` sigue en verde.

**Paso 4 · M-03 Salidas separadas**
- **Archivo:** `sagapi/reportes.py`.
- **Cambio:** `escribir_excel(E, salida)` crea un libro nuevo con 28–33 y una hoja de controles; elimina la dependencia de `24_VALIDACIONES` y de `herramientas/img`.
- **Dependencias:** ninguna.
- **Riesgo:** bajo.
- **Pruebas:** comprobar que el SHA-256 del Excel de entrada no cambia tras `reportes --escribir-excel`.
- **Aceptación:** la entrada queda intacta y el libro de resultados se genera.

**Paso 5 · M-04a R11 honesto**
- **Archivo:** `sagapi/modelo.py`.
- **Cambio:** `reservar_personal=False` por defecto. Se mantiene `personal.resumen_dotacion` como diagnóstico y el texto de R11 pasa a decir "chequeo de cobertura (no restricción temporal)".
- **Dependencias:** M-00.
- **Riesgo:** cambian las cifras de "binarias" en los reportes.
- **Pruebas:** f1, f1b y f2 idénticos con y sin R11 en los 40 escenarios E2 (lo que demuestra que no restringía); actualizar `test_personal_25`.
- **Aceptación:** óptimos idénticos y documentación coherente.

### Fase 2 — P1 de validez del modelo y de los experimentos

**Paso 6 · M-10 Selección por afectación**
- **Archivo:** `Optimizacion_MILP_SAGAPI.py` (`cmd_integrar_personal`, `cmd_rodante_personal`).
- **Cambio:** la candidata es un pedido con operación pendiente en la máquina averiada dentro de `--horizonte-externos`; el orden es por holgura (d_j − C_j del FIFO).
- **Pruebas:** S08A y S13A deben seguir auditando 0 errores; se reportan los pedidos elegidos.
- **Aceptación:** el informe explica el criterio de selección.

**Paso 7 · M-09 Pedidos futuros en `evento_unico`**
- **Archivo:** `sagapi/experimentos.py`.
- **Cambio:** pasar las operaciones FIFO de pedidos con r_j > t_b como reservas fijas (reutilizar `cobertura_externa.preparar_reservas_futuras` sin personal) o evaluar los KPI sobre los 96 pedidos.
- **Dependencias:** Paso 6.
- **Riesgo:** subproblemas más grandes (más ventanas R6).
- **Pruebas:** 0 cruces con reservas en E2; tiempo por caso inferior a 60 s.
- **Aceptación:** E2 repetido con los KPI de todos los pedidos.

**Paso 8 · M-06 Diseño experimental**
- **Archivos:** `sagapi/experimentos.py`, `sagapi/reglas.py`, `sagapi/reportes.py`.
- **Cambio:** añadir ATC; tabla de descomposición (Δ secuenciación = S00; Δ reprogramación = S20A − S00 con la misma base); reemplazar Wilcoxon sobre escenarios dependientes por intervalos bootstrap sobre réplicas Monte Carlo independientes.
- **Pruebas:** reproducibilidad con semilla.
- **Aceptación:** cada conclusión de la memoria indica contra qué regla se compara.

**Paso 9 · M-05 Horno no partible**
- **Archivo:** `sagapi/modelo.py` (nuevo bloque R12_LOTE).
- **Cambio:** para cada operación POR_LOTE libre, las ventanas de cierre (fin de jornada → inicio de la siguiente) entran como ventanas R6 de su máquina; las reglas FIFO, EDD y convencional usan `_empujar_ventanas` con esas mismas ventanas.
- **Dependencias:** M-13 (corregir el big-M de R6 antes de reutilizarlo).
- **Riesgo:** cambia el FIFO, así que `16_PROGRAMA_BASE` deja de reproducirse; regenerarlo y documentarlo.
- **Pruebas:** 0 operaciones POR_LOTE que crucen el cierre, en el MILP y en las reglas; enumeración 40/40.
- **Aceptación:** el verificador incluye la regla y la cumple.

**Paso 10 · M-08 Capacidad k**
- **Archivos:** `sagapi/instancia.py`, `sagapi/modelo.py`, `sagapi/verificacion.py`.
- **Cambio:** un recurso con cantidad k se expande en k unidades idénticas (`ARM-01#1`, `#2`) con simetría rota (orden lexicográfico de uso); el verificador comprueba ≤ k operaciones simultáneas.
- **Dependencias:** PV-09.
- **Riesgo:** más binarias; mitigación: solo para recursos con k > 1.
- **Pruebas:** microinstancia con k = 2 frente a enumeración.
- **Aceptación:** óptimos iguales a los enumerados.

**Paso 11 · M-07 Objetivo**
- **Archivos:** `sagapi/modelo.py`, `sagapi/optimizacion.py`.
- **Cambio:** según PV-14, regla de penalidad configurable desde la base y fase opcional "min T_max" antes de la estabilidad.
- **Dependencias:** PV-14.
- **Pruebas:** enumeración extendida a la nueva regla.
- **Aceptación:** en S06A la tardanza ponderada no empeora frente a CONV sin una justificación económica explícita.

**Paso 12 · M-04b / M-11 Personal vinculado al horario**
- **Archivos:** `sagapi/personal_integrado.py` y un nuevo `sagapi/descomposicion.py`.
- **Cambio:** con la matriz real y las personas por operación, generalizar q[o,w] a dotaciones de 1 o más; descomponer por ventanas de 1–2 turnos con todos los pedidos activos (no N fijos); estudiar CP-SAT si HiGHS no escala.
- **Dependencias:** PV-02, Pasos 6–10.
- **Riesgo:** tiempo de cómputo; mitigación: límites por ventana y una heurística de reparación verificada.
- **Pruebas:** el verificador de personal (sin solapes por persona, habilidades válidas, ≤ 8 h por día) en el horizonte completo.
- **Aceptación:** cobertura ≥ 95 % de las operaciones del horizonte evaluado, 0 conflictos.

### Fase 3 — P2 de mantenibilidad y reproducibilidad

| Paso | Mejora | Archivo o módulo | Pruebas | Criterio de aceptación |
|---|---|---|---|---|
| 13 | M-13 Big-M R6 | `modelo.py:113` | Microinstancia con ventana a < p | Óptimo igual al enumerado |
| 14 | M-12 Lexicográfico único | `optimizacion.py`, `rodante_personal.py`, programa principal | Las 50 pruebas actuales + enumeración | Mismos resultados; una sola implementación |
| 15 | M-14 Sensibilidad desde la base | `experimentos.e4_*` | Cambiar un nivel en la base cambia la corrida | Sin niveles fijos en el código |
| 16 | M-19 Verificador ampliado | `verificacion.py` | Casos negativos (persona solapada, horno partido, capacidad excedida) | Cada caso negativo se detecta |
| 17 | M-15 Pruebas + CI | `tests/`, `.github/workflows/ci.yml` | `pytest` y `verificar_bd_v2.py` en cada push | Pipeline en verde |
| 18 | M-16 Fijar dependencias | `requirements.lock`, `solver.version_highs` | Ejecución limpia en Python 3.11 y 3.13 | Resultados idénticos fuera de los tiempos |
| 19 | M-17 Refactorización | programa principal → `sagapi/pilotos.py`; ruff | Pruebas sin cambios | Programa principal < 150 líneas |
| 20 | M-20 Pipeline con manifiesto | `herramientas/pipeline.py` | Ejecución completa | Manifiesto SHA-256 de entradas, código y salidas |
| 21 | M-18 Rutas como grafo | `datos_v2`, `instancia`, `modelo` (R3 y pares intrapedido) | Enumeración con ruta ramificada | Óptimo igual al enumerado |

### Fase 4 — P3 complementaria

| Paso | Mejora | Condición de inicio |
|---|---|---|
| 22 | M-21 Indicadores industriales | Tras el Paso 12 |
| 23 | M-22 Gantt e informe HTML | En cualquier momento tras el Paso 4 |
| 24 | M-23 Incertidumbre con datos reales | Cuando `13_REG_PARADAS` tenga ≥ 6 meses de registros |

---

## 3. Dependencias entre pasos

```
Fase 0: 1 (M-00) ── 2 (M-01, datos) ─────────────────────────────┐
Fase 1: 3 (lector v2) ─► 4 (salidas) ─► 5 (R11 honesto)          │
Fase 2: 6 (selección) ─► 7 (pedidos futuros) ─► 8 (diseño exp.)   │
        13 (big-M R6) ─► 9 (horno) ; PV-09 ─► 10 (capacidad k)    │
        PV-14 ─► 11 (objetivo) ; PV-02 + 6..10 ─► 12 (personal) ◄─┘
Fase 3: 14, 15, 16, 17, 18, 19, 20, 21   (17 conviene antes de 9–12 para proteger los cambios)
Fase 4: 22, 23, 24
```

**Recomendación de ejecución:** completar la Fase 1 y los Pasos 13 y 17 (CI) antes de tocar el modelo. Así cada cambio posterior del MILP queda protegido por el lector estricto, las salidas separadas y la integración continua, y se puede comprobar que lo que no debía cambiar no cambió.
