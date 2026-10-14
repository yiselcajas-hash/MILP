# Entregable 1 — Informe de auditoría integral SAGAPI (Excel v1.2, Python 1.4.0, MILP)

**Objeto auditado:** `SAGAPI_MILP_ENTREGA_FINAL_1_4_0.zip` (83 archivos). El Excel `Base_Datos_SAGAPI_25_TRABAJADORES_SIMULADOS_v1_2.xlsx` (SHA-256 `8f75befc…7fffb3`, idéntico al manifiesto de la entrega) **no se modificó**; todo el trabajo se hizo sobre copias.

**Cómo leer este informe.** Cada afirmación lleva su evidencia (celda, fórmula, línea de código o resultado de una ejecución). Se distinguen cuatro tipos de hallazgo:

| Tipo | Significado |
|---|---|
| **Error comprobado** | Se reproduce con el archivo entregado (p. ej. una celda con `#VALUE!`). |
| **Riesgo** | No falla hoy, pero fallará o inducirá a error ante un cambio razonable. |
| **Limitación** | Supuesto de modelado o falta de datos que restringe lo que se puede concluir. |
| **Oportunidad** | Mejora con beneficio demostrable. |

Las rutas de las ejecuciones citadas están en `entrega_v2_0/verificacion/`. La matriz detallada de 84 hallazgos del Excel está en `entrega_v2_0/auditoria/SAGAPI_AUDITORIA_DATOS_v2_0.xlsx` (hoja `1_MATRIZ_ERRORES`).

---

## 1. Conclusiones principales

1. **El modelo está bien hecho en lo matemático, pero los datos no permiten sacar conclusiones industriales.** El MILP reproduce el óptimo exacto en 40/40 microinstancias enumeradas y todas las soluciones pasan un verificador independiente. Sin embargo, **ningún tiempo de ruta fue cronometrado** (215 heredados y 191 hipótesis técnicas), **los 96 pedidos y las 21 averías son sintéticos** y la **matriz de habilidades es simulada**. Lo único real y comprobable son las 4 familias, las ventas y unidades agregadas de 2025, la dotación (25 personas, 1 turno, 8 h) y la declaración de las operaciones del proceso.
2. **El Excel entregado contiene errores no detectados por su propia hoja de controles.** Hay 613 celdas con `#VALUE!` guardadas (toda la hoja `25_CAPACIDAD_CON_FALLAS` y `21B!I67`). Además, `24_VALIDACIONES` muestra 2 controles fallidos (`0` frente a `50` y `13` frente a `0`) por una referencia rota y una fórmula matricial mal evaluada.
3. **Los plazos simulados son incompatibles con las rutas, y eso domina los resultados.** Sin ninguna avería, el FIFO entrega tarde **73 de 96 pedidos**; una regla EDD simple baja a **27** y el MILP a **19**. Con las 12 averías de la plegadora, las cifras casi no cambian (74 / 27 / 19). La mejora atribuida al MILP se debe sobre todo a la **secuenciación frente a un FIFO débil**, no a la **reprogramación ante fallas**. Tres pedidos (P049, P050, P058) son infactibles por construcción: su ruta suma más horas que la ventana entre liberación y compromiso.
4. **La restricción de personal del modelo principal no restringe nada.** La R11 de `modelo.py` reserva una persona por máquina para todo el subproblema, sin ninguna variable de tiempo ni de asignación. Resolver S06A con R11 y sin R11 da el mismo óptimo (f1 = 9 066,34). La integración real de trabajadores existe solo en el piloto (`personal_integrado.py`), limitado a 24–36 operaciones; los pilotos rodantes comprometen el **2,0 %** (S08A) y el **0,17 %** (S13A) de las 1 152 operaciones.
5. **Hay una incoherencia de escala laboral sin resolver.** La carga anual de proceso es de **5 742 h**, mientras que 25 personas disponen de **52 200 h** (11 %). O los tiempos están subestimados, o la demanda modelada es parcial, o el trabajo indirecto no está representado. Mientras esto no se aclare, ninguna conclusión sobre dotación o rotación es defendible.
6. **La nueva base v2.0 corrige todo lo corregible sin inventar datos y es 100 % compatible con Python 1.4.0.** Las 50 pruebas, la enumeración, los pilotos, `caso S06A` y `anual` producen **salidas idénticas** con el original y con la v2.0 (Entregable 5).

---

## 2. Auditoría del Excel hoja por hoja

Leyenda de acción: **C** conservar · **K** corregir · **I** integrar · **S** separar (a simulación) · **R** reubicar (al documento de auditoría) · **E** eliminar.
"Lee Python" indica si `sagapi/datos.py` (u otro módulo) consume la hoja.

| Hoja | Propósito | Filas × col. | Lee Python | Utilidad real | Problemas principales (ID de matriz) | Acción |
|---|---|---|---|---|---|---|
| 00_LEEME | Guía narrativa | 16 × 3 | No | Ninguna operativa | Cita un archivo inexistente (E-011) | R |
| 01_PRODUCTOS | Catálogo | 50 × 13 | Sí (nombre, familia, lote) | Alta (8 productos con pedidos) | "No aplica" en Puertas (E-012); 19 productos con dimensiones de plantilla (E-013); lote = 10 en todos (E-014); demanda simulada mezclada (E-015) | K |
| 01B_IMAGENES | Esquemas | 8 × 8 | Solo al escribir resultados | Nula | Esquemas generados; columna sin encabezado; imágenes que se pierden al reescribir (E-017) | E |
| 02_MATERIALES | Maestro de materiales | 41 × 8 | No | Media (costos) | 114 celdas con "Según especificación" (E-018); 33 sin costo (E-019); unidad del perfil incoherente (E-021) | K |
| 03_DESPIECE | Lista de materiales | 224 × 11 | Sí (masa de chapa, opcional) | Media | Masa y costo sin fórmula, con supuestos ocultos (E-026); planchas mal calculadas (E-029); 53 costos de herrajes calculables vacíos (E-027); espesores en conflicto con el catálogo (E-024) | K |
| 04_MAQUINAS | Recursos | 17 × 16 | Sí | Alta | Inventario no certificado (E-031); puestos manuales con capacidad 1 (E-033); referencias por número de fila (E-005) | K |
| 05_RUTAS | Rutas y tiempos | 406 × 12 | Sí (núcleo del MILP) | Crítica | 0 tiempos cronometrados (E-037); precedencia lineal sin solapes (E-040); "Inicio" mezclado con números (E-038) | K |
| 06_OPERARIOS | Personal | 25 × 9 | Sí (lista) | Alta | Mezcla dato real y especialidad simulada; horas como texto (E-045) | K + S |
| 06B_HABILIDADES | Habilidades | 26 × 19 | Sí (R11–R15) | Media | 100 % simulada (E-046); fila de totales dentro de la tabla (E-047) | S |
| 06C_SUPUESTOS_PERSONAL | Supuestos | 15 × 3 | No | Baja | Narrativa (E-048) | R (+ hechos a parámetros) |
| 07_CALENDARIO | Calendario | 396 × 11 | Sí | Crítica | 12 feriados laborables por defecto (E-049); 6 columnas constantes o de texto (E-050) | K |
| 08_PEDIDOS | Demanda | 96 × 26 | Sí | Crítica | 100 % sintéticos (E-051); 480 celdas históricas vacías (E-052); 43 fechas en fin de semana (E-053); 3 infactibles (E-054); lote leído como vacío (E-056) | S |
| 09_CARGA_ORDEN | Carga por operación | 1 152 × 15 | No (Python recalcula) | Alta (análisis) | Tiempos tomados por posición de fila (E-058) | K (derivada) |
| 10_MATERIALES_ORDEN | Materiales por pedido | 636 × 11 | No | Media | Sin herrajes; planchas erróneas (E-059, E-029) | K (derivada) |
| 11_CAPACIDAD | Capacidad mensual | 204 × 11 | No | Alta | "Paradas históricas = 0" sin historial (E-060) | K |
| 12_PRECIOS | Ventas y penalidades | 4 × 6 | Sí | Alta | Penalidad 10 % sin cláusula (E-064); precio por familia (E-057) | K |
| 13_ELEGIBILIDAD | Máquinas alternativas | 473 × 8 | Sí | Alta | Factor 1,10 sin medición (E-044); redundancias (E-043) | K |
| 14_FALLAS_ESC | Averías | 21 × 10 | Sí | Media (escenarios) | 100 % sintéticas (E-065); instantes artificiales (E-066) | S |
| 15_RECUPERACION | Políticas tras avería | 62 × 11 | Sí | Media | Tipos mixtos (E-069); pseudoproductos "(Genérico)" (E-070) | S + K |
| 16_PROGRAMA_BASE | FIFO de referencia | 1 152 × 11 | Sí (opcional) | Media (comparación) | Columnas constantes (E-071) | S |
| 17_ESTADO_PLANTA | Estado en F01 | 1 152 × 10 | No | Nula (reproducible) | Solo para un evento (E-072) | E |
| 18_ESCENARIOS | Escenarios | 40 × 8 | Sí | Alta | Política mezclada con regla; duraciones sumadas (E-073) | S |
| 19_PARAMETROS | Parámetros | 42 × 5 | Sí (6 nombres) | Crítica | Valor con tipos mixtos (E-074); texto del solver obsoleto (E-075); duplicados (E-076) | K |
| 20_COSTOS | Costo por pedido | 96 × 7 | No | Media | Tarifa promedio en lugar de tarifa por recurso (E-061); margen 70 % (E-062) | K (derivada) |
| 21_INCIDENCIAS_REAL | Plantilla | 0 × 9 | No | Potencial | Vacía y sin validaciones (E-079) | I (plantilla) |
| 21B_PARADAS_ARCHIVO_ORIG | Paradas archivo original | 66 × 11 | No | Nula para SAGAPI | Equipo "ROLADORA" inexistente; 13 registros en fin de semana; `#VALUE!` (E-080) | R |
| 22_CALIDAD_REAL | Plantilla | 0 × 8 | No | Potencial | Vacía (E-079) | I (plantilla) |
| 23_ORIGEN_DATOS | Procedencia | 21 × 4 | No | Trazabilidad | Texto (E-081) | R |
| 24_VALIDACIONES | Controles | 25 × 4 | Solo al escribir | Alta | 2 controles fallidos sin aviso; referencia rota (E-002–E-004) | K |
| 25_CAPACIDAD_CON_FALLAS | Capacidad residual | 204 × 8 | No | Nula (rota) | 612 `#VALUE!`; suma escenarios excluyentes (E-001, E-067) | E → reemplazo |
| 26_REGISTRO_CAMBIOS | Bitácora v1.2 | 65 × 7 | No | Trazabilidad | Texto (E-081) | R |
| 27_SENSIBILIDAD | Factores | 5 × 5 | Sí (sin usar) | Baja | El código ignora los niveles (E-082) | S |
| 28–33 (6 hojas) | Resultados | — | Las escribe Python | Ninguna como entrada | Resultados dentro de la base; el programa sobrescribe el archivo (E-010, E-083) | E |

### 2.1 Auditoría de celdas vacías (requisito 4.1)

Se recorrieron todas las celdas dentro del rango usado de cada hoja. La clasificación es la siguiente.

| Clase | Casos en v1.2 | Tratamiento en v2.0 |
|---|---|---|
| **1. Obligatorias vacías** | Ninguna en columnas que lea Python: `datos.validar` las rechaza. | El verificador V02 exige cada campo marcado como obligatorio en `00_DICCIONARIO` (0 faltantes). |
| **2. Opcionales con nulo válido** | 379 fechas sin feriado; puertas en productos sin puertas (44, escritas como "No aplica"); medidas de pieza que no aplican según el tipo (437 celdas con "No aplica" o 0); paso de las reglas genéricas (4); momento de S00 y S20A. | Vacío real (sin texto de relleno), marcado "Opcional (vacío válido)" en el diccionario. |
| **3. Vacías por error de construcción** | 480 celdas históricas de 08 (J:N) que nunca se llenarán con datos simulados; "Paradas históricas = 0" (204, un cero falso); columna H de 01B sin encabezado; fila de totales dentro de 06B. | Eliminadas o reemplazadas por plantillas de captura reales (`12_REG_ENTREGAS` … `16_REG_HABILIDADES`). |
| **4. Calculables con datos existentes** | Costo de 53 líneas de herrajes (piezas × 0,90 S/); masa y costo de 150 líneas (fórmula oculta); fin de evento; componentes y pasos por producto; planchas equivalentes. | **Reconstruidas con fórmula** y verificadas contra un recálculo independiente (V05). |
| **5. Requieren información de SAGAPI** | 33 costos de materiales; masa de herrajes; costo de SAL-PIN; factor de emisión; medidas de 19 productos; espesores reales; tiempos; habilidades; pedidos; paradas. | Vacíos a propósito, con naturaleza `PENDIENTE` o `ESTIMADO`, y listados en `2_PENDIENTES_VALIDACION` (18 pendientes). |

**No se rellenó ninguna celda con ceros, promedios ni valores repetidos.**

### 2.2 Información innecesaria (requisito 4.2)

Se retiraron de la base operativa los textos que no aportan a la operación, **sin perderlos**: quedan íntegros en el libro de auditoría (hojas `5A`–`5H`):

- Columnas de comentario o naturaleza repetidas en cada fila (04!P, 06!I, 06B!S, 13!H, 15!H, 16!J:K).
- Referencias metodológicas (00_LEEME, 06C, 23, 26).
- Campos duplicados (05!B familia, 05!L clave de unión, 13!C operación, 19 duplicados de 12 y 05).
- Variables que no intervienen en ningún cálculo (marca y modelo "del escenario").
- Hojas derivadas o de resultados (17, 28–33).
- Elementos visuales (imágenes de 01B, colores sin leyenda).

Se conservó todo lo que Python lee. El mapa completo origen → destino está en `3_MAPA_MIGRACION`.

---

## 3. Auditoría de realismo industrial

| Ámbito | Observación (evidencia) | Diagnóstico |
|---|---|---|
| **Familias y productos** | 4 familias reales. De 50 productos, solo 8 tienen pedidos. 19 comparten 85 × 120 × 60 cm, incluidos bancos de bar y carros de taller. | Catálogo de prueba; solo los 8 productos con pedidos importan al modelo. |
| **Materiales y despiece** | Los lockers usan chapa de 1,5 mm y las góndolas de 1,0 mm, frente a 0,6 y 0,8 mm del catálogo. Toda la chapa vale 6,80 S/ por kg. El perfil genérico pesa 1,5 kg/m. Las mermas implícitas son del 8 % y 4 %. | La masa de lockers podría estar sobrestimada hasta 2,5 veces. Las mermas son verosímiles pero no están medidas. |
| **Rutas** | Las operaciones son coherentes con la metalmecánica (corte → perforado → plegado → soldadura → acabado → pintura → curado → armado → inspección → embalaje). La precedencia es estrictamente lineal y cada operación espera el lote completo anterior. | Secuencia verosímil, pero el plazo de entrega se sobrestima: el corte de tubos podría ir en paralelo con el de planchas y los lotes de transferencia acortarían el flujo. |
| **Tiempos** | Ejemplos de tiempo por unidad: plegado de 196 min en la góndola central, 104 min en el locker de 4 puertas; perforación de 97 min. Preparaciones de 2–12 min por lote; curado de 45 min por lote de 10 unidades. | Plausibles en orden de magnitud, pero **ninguno medido**. El plegado de 3,3 h por góndola debe validarse primero: decide el cuello de botella. |
| **Máquinas** | La plegadora carga al 68,8 % anual (80–81 % en jun–ago) y **no tiene alternativa**; el resto queda por debajo del 38 %. Puestos manuales y áreas tienen capacidad 1. | El cuello de botella en la plegadora es coherente con el objetivo del estudio. La capacidad 1 en inspección, embalaje y armado es poco realista con 25 personas. |
| **Horno** | 10 de 96 curados del FIFO quedan partidos entre el cierre de una jornada y la siguiente (`evidencia_diagnostico_codigo.json`). | Un ciclo térmico no puede pausarse durante la noche: es un error físico del modelo de tiempo, no del dato. |
| **Trabajadores** | 25 personas, 1 turno, 8 h (real). Carga de proceso de 5 742 h frente a 52 200 h disponibles (11 %). | Incoherencia grave (E-063); puede deberse a tiempos subestimados o a demanda parcial. |
| **Pedidos** | 8 por mes, liberados los días 3 y 16; plazo de 14–18 días; 43 con fecha en fin de semana; lote fijo de 10; precio medio por familia. Las unidades totales (851) coinciden con las ventas reales agregadas. | El total anual está anclado en un dato real; el reparto en pedidos es artificial. |
| **Plazos y capacidad** | Sin averías: FIFO 73 atrasados, EDD 27, MILP 19 (corrida `anual`, idéntica con v1.2 y v2.0). | Los plazos no son compatibles con las rutas y el FIFO es un comparador débil. |
| **Costos** | El costo de los 96 pedidos (580 k S/ en v1.2, 632 k S/ en v2.0) frente a ventas de 1,97 M S/ implica un margen bruto del 65–71 %. La mano de obra solo cuenta horas de proceso. | Inverosímil para una pequeña empresa metalmecánica: los costos son incompletos. |
| **Averías** | 12 fallas de la plegadora entre junio y noviembre (ninguna en el primer semestre), de 2 a 6 h, más una de 29 h. Las duraciones se "calibraron" con paradas de una roladora que la empresa no tiene. | No representan la fiabilidad real. Las 12 averías apenas alteran los resultados anuales (FIFO 73 → 74 atrasados). |

**Magnitudes físicamente imposibles detectadas:** (a) curados partidos entre jornadas; (b) bancos de bar de 120 cm de ancho y otras medidas de plantilla (sin efecto en el modelo); (c) tres pedidos que no caben en su ventana aun con la planta vacía. **No se detectaron** capacidades negativas, tiempos nulos, rutas sin máquina ni cargas mensuales por encima de la capacidad (máximo 81 %).

---

## 4. Auditoría del modelo MILP y del código Python (resumen)

El diagnóstico completo, con evidencia línea por línea, está en el **Entregable 6**. Resumen:

| Componente | Estado | Hallazgo clave |
|---|---|---|
| Formulación R1–R10 (`modelo.py`) | **Correcta** | Disyunciones con big-M bien derivadas, tardanza y penalidad bien vinculadas, penalidad con tope correcta (min{aT, tope}). Validada por enumeración en 40/40 microinstancias. |
| R11 personal (`modelo.py`) | **Defecto de diseño** | No contiene variables de programación; no restringe nada mientras haya 15 personas habilitadas distintas. |
| Personal integrado (`personal_integrado.py`) | Correcta, de alcance piloto | Límite de 24–36 operaciones; big-M del horizonte; un trabajador por operación sin relevo. |
| Capacidad de recursos | Limitación | Siempre capacidad 1 (la "Cantidad" solo se valida si es ≥ 1). |
| Tiempo y calendario | Limitación física | Las operaciones POR_LOTE (horno) se parten entre jornadas. |
| Objetivo lexicográfico | Correcto, con efecto colateral | En S06A el MILP baja de 7 a 4 atrasados, pero la tardanza ponderada sube de 205,6 a 249,2 h y desplaza 2 031 h de inicios. |
| Horizonte rodante | Piloto | Selecciona los primeros N pedidos activos por índice, no por afectación; cobertura del 2 % / 0,17 %. |
| Solver | Correcto | Usa la API pública de SciPy/HiGHS con verificación algebraica independiente; el arranque en caliente no se usa (no existe en esa API). |
| Lectura de datos | Riesgo | `data_only=False`: una celda de entrada convertida en fórmula se lee como vacía **sin aviso** (pasa hoy con el "Lote"). |
| Reportes | Error de arquitectura | `--escribir-excel` sobrescribe la base de datos de entrada. |
| Pruebas | Buenas, pero no validan la industria | 50 pruebas estructurales y de regresión; no cubren lectura del Excel, calendario con feriados, capacidad > 1 ni horno. |

**¿Justifican los resultados las conclusiones actuales?** Parcialmente. Se sostiene que **el prototipo es matemáticamente correcto y verificable en subproblemas**. No se sostiene: (a) un beneficio del MILP "ante averías" separado del efecto de secuenciación; (b) cualquier afirmación sobre personal (R11 no restringe y la matriz es simulada); (c) la validez para los 96 pedidos (los pilotos cubren menos del 2 %). El `LEEME_ENTREGA_FINAL.md` ya advierte (b) y (c); (a) no está advertido.

---

## 5. Mapa de dependencias Excel–Python (requisito 6.1)

Detalle completo en `SAGAPI_AUDITORIA_DATOS_v2_0.xlsx`, hoja `4_DEPENDENCIAS_PYTHON`.

```
Optimizacion_MILP_SAGAPI.py ─► sagapi.datos.leer(archivo)  [openpyxl, data_only=False, por nombre de hoja y encabezado]
   19_PARAMETROS ─ 6 nombres exactos ─► calendario (jornada, feriados), β, Monte Carlo, máquina crítica
   07_CALENDARIO ─ Fecha, Productivo, Feriado ─► Calendario: eje de horas productivas ─► r_j, d_j, ventanas (a, b)
   01_PRODUCTOS ─ Nombre, Familia, Lote guía ─► productos
   04_MAQUINAS ─ Equipo, Cantidad, kW, factor ─► M (validación), energía
   05_RUTAS ─ Producto, Paso, Equipo, Min fijos, Min unidad, Precedencia, Tratamiento ─► O_j, p_om = (⌈q/L⌉·s + q·u)/60
   13_ELEGIBILIDAD ─ Máquina elegible, Tipo, Factor ─► M_o, p_om alternativo
   12_PRECIOS ─ Ventas/Unidades, Penalidad % ─► valor_j ─► w_j (f1b), P_j (f1), tope y penalidad diaria (R9)
   08_PEDIDOS ─ Pedido, Producto, Unidades, Lote, Liberación, Compromiso ─► J, q_j, r_j, d_j
   14_FALLAS_ESC ─ Evento, Inicio, Horas de reloj, Equipo ─► ventanas de indisponibilidad (R2, R6)
   15_RECUPERACION ─ Política, Conserva, Reinicia, Repite setup, Piezas, Verificación ─► tiempo restante (pR)
   18_ESCENARIOS ─ Escenario, Evento, Recuperación ─► casos, rodante, experimentos
   06_OPERARIOS + 06B_HABILIDADES ─► R11 (reserva estática), R11–R15 (piloto), control_personal
   16_PROGRAMA_BASE (opcional) ─► E0 (Python reproduce el FIFO)
   03_DESPIECE (opcional) ─ Masa ─► indicador material_reproceso_kg
   27_SENSIBILIDAD ─► leída, no usada
Salidas: CSV/JSON en --salida; con --escribir-excel: hojas 28–33 + 24_VALIDACIONES DENTRO del Excel de entrada.
```

**Parámetros que intervienen en las restricciones:** p_om (05 + 13 + 08 + 01), r_j y d_j (08 + 07 + horario fijo en el código), ventanas (14 + 07), habilidades (06B), cantidad ≥ 1 (04). **En los objetivos:** P_j = penalidad × precio × q (12 + 08); w_j = valor_j / valor medio; β (19). **Indicadores:** energía (04 kW × factor), masa de chapa (03).

**Errores que surgirían al renombrar o eliminar columnas:**

- *Ruidosos* (KeyError o ErrorDatos): nombres de producto, máquina, pedido, fechas, tiempos, evento.
- *Silenciosos* (valores por defecto **sin aviso**): Lote, Lote guía, Penalidad %, kW, factor de carga, Piezas a repetir, Min de verificación, los 6 parámetros de `19_PARAMETROS` (se usarían 8, 40, 2025200, …), toda la hoja 06B (desaparece la restricción de personal) y 03 (indicador = 0).
- *Peligrosos*: una columna extra en 06B se interpreta como una máquina; cambiar el texto "ALTERNATIVA CON UTILLAJE COMPATIBLE" anula la sensibilidad del factor de tiempo sin aviso.

**Cambios necesarios para reconstruir el Excel sin romper el programa:** mantener exactamente los nombres de hoja y encabezado de la tabla anterior, escribir como **valores** (no fórmulas) las columnas que lee Python, conservar el texto "Inicio", los rótulos "(Genérico) …", las políticas "A - reanudar" y "B - reiniciar lote" y la hoja 24 si se usa `--escribir-excel`. La v2.0 resuelve esto con un libro **MODELO generado** (Entregable 3) y el **mapa de migración** (`3_MAPA_MIGRACION`), que fija cómo la próxima versión del código leerá directamente las bases normalizadas.
