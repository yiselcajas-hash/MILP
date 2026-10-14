# Entregable 4 — Informe de cambios: Excel v1.2 → Base de datos SAGAPI v2.0

## 1. Arquitectura nueva

El libro v1.2 (38 hojas que mezclaban datos reales, supuestos, simulación, resultados y textos metodológicos) se reemplaza por **tres libros con funciones separadas**, más un libro de auditoría:

| Libro | Contenido | Naturaleza admitida | ¿Se edita? |
|---|---|---|---|
| `SAGAPI_BD_OPERATIVA_v2_0.xlsx` | Familias, productos, materiales, despiece, recursos, rutas, elegibilidad, personal, calendario, capacidad, parámetros y **5 plantillas de captura** de datos reales | REAL, REFERENCIA, CALCULADO, ESTIMADO, PENDIENTE, CONFIGURACION | **Sí** (fuente) |
| `SAGAPI_BD_SIMULACION_v2_0.xlsx` | Pedidos, perfiles y habilidades, eventos de falla, escenarios, recuperación, sensibilidad, configuración del modelo y FIFO de referencia | SIMULADO (más ESTIMADO y CONFIGURACION) | **Sí** (fuente) |
| `SAGAPI_BD_MODELO_v2_0.xlsx` | Unión de ambas con los **nombres de hoja y encabezados que lee Python 1.4.0**, más hojas derivadas con fórmulas vivas (carga, materiales, capacidad, costos, pérdida por escenario, controles) | Hereda la naturaleza de cada fila | **No**: se genera |
| `auditoria/SAGAPI_AUDITORIA_DATOS_v2_0.xlsx` | Matriz de errores, pendientes, mapa de migración, dependencias de Python y textos de procedencia archivados | — | Documento |

**Regeneración:**

```
python herramientas/construir_bd_v2.py --paso modelo     # OPERATIVA + SIMULACION → MODELO
python herramientas/recalcular_bd_v2.py entrega_v2_0/base_datos/*.xlsx
python herramientas/verificar_bd_v2.py --pruebas-python
```

**Uso con el programa actual:** copiar `SAGAPI_BD_MODELO_v2_0.xlsx` junto al programa y ejecutar con `--excel SAGAPI_BD_MODELO_v2_0.xlsx` (o renombrarlo con el nombre por defecto).

## 2. Hojas: correspondencia v1.2 → v2.0

| v1.2 | v2.0 | Cambio |
|---|---|---|
| 00_LEEME | OPERATIVA/SIMULACION `00_DICCIONARIO` + `00_CODIGOS`; MODELO `00_INDICE`; texto en Auditoría `5A` | Narrativa reemplazada por un diccionario de datos (hoja, columna, tipo, unidad, obligatoriedad, naturaleza, uso en Python) |
| 01_PRODUCTOS | OPERATIVA `02_PRODUCTOS` (+ `01_FAMILIAS`) | Claves PRD-xxx/FAM-xxx; "No aplica" → vacío; demanda e hipervínculos fuera; fórmulas de componentes, pasos y dimensiones genéricas |
| 01B_IMAGENES | — | Eliminada (esquemas generados, no datos) |
| 02_MATERIALES | OPERATIVA `03_MATERIALES` | Vocabulario normalizado; 114 textos de relleno → vacío; marca de material genérico |
| 03_DESPIECE | OPERATIVA `04_DESPIECE` | Fórmulas explícitas de área, masa, costo y planchas con parámetros con nombre; costo de 53 herrajes calculado; planchas corregidas (× piezas) |
| 04_MAQUINAS | OPERATIVA `05_RECURSOS` | Tipo de recurso; inventario_verificado = 0; marca, modelo y estatus archivados |
| 05_RUTAS | OPERATIVA `06_RUTAS` | Claves; paso_predecesor entero; origen_tiempo codificado; tiempos limpiados de ruido flotante (78,39999999999999 → 78,4) |
| 06_OPERARIOS | OPERATIVA `08_PERSONAL` + SIMULACION `02_PERFILES_SIM` | Dato real separado de la especialidad simulada; horas como hora; control de jornada por fórmula |
| 06B_HABILIDADES | SIMULACION `03_HABILIDADES_SIM` | Columnas = recurso_id; sin fila de totales ni columna de texto; validación 0/1 |
| 06C_SUPUESTOS_PERSONAL | OPERATIVA `11_PARAMETROS` (25, 1, 8 = REAL) + Auditoría `5D` | Hechos a parámetros; narrativa archivada |
| 07_CALENDARIO | OPERATIVA `09_CALENDARIO` | 7 columnas (antes 11); productivo efectivo y horas por fórmula con nombre definido |
| 08_PEDIDOS | SIMULACION `01_PEDIDOS_SIM` (+ MODELO `08_PEDIDOS` con derivadas) | Lote como valor; 6 columnas vacías eliminadas (plantilla `12_REG_ENTREGAS`); marcas de fin de semana y de ruta que excede la ventana |
| 09_CARGA_ORDEN | MODELO `09_CARGA_ORDEN` | SUMIFS por (producto, paso) en lugar de referencias por posición |
| 10_MATERIALES_ORDEN | MODELO `10_MATERIALES_ORDEN` | Incluye herrajes; planchas corregidas; indicador de costo completo |
| 11_CAPACIDAD | OPERATIVA `10_CAPACIDAD_MENSUAL` + MODELO `11_CAPACIDAD` | Sin "paradas históricas = 0" (cero falso) |
| 12_PRECIOS | OPERATIVA `01_FAMILIAS`; MODELO `12_PRECIOS` | Fuente única de las penalidades |
| 13_ELEGIBILIDAD | OPERATIVA `07_ELEGIBILIDAD` | Tipos codificados; naturaleza por fila |
| 14_FALLAS_ESC | SIMULACION `04_EVENTOS_SIM` | tipo_evento FALLA / MANTENIMIENTO_PLANIFICADO; fin por fórmula |
| 15_RECUPERACION | SIMULACION `06_RECUPERACION_SIM` | Columna `ambito` en lugar de pseudoproductos; piezas como entero o vacío |
| 16_PROGRAMA_BASE | SIMULACION `09_PROGRAMA_FIFO_REF`; MODELO `16_PROGRAMA_BASE` | Sin columnas constantes |
| 17_ESTADO_PLANTA | — | Eliminada (Python la recalcula para cualquier evento) |
| 18_ESCENARIOS | SIMULACION `05_ESCENARIOS_SIM` | Política A/B o vacía; momento y duración derivados de los eventos |
| 19_PARAMETROS | OPERATIVA `11_PARAMETROS` + SIMULACION `08_CONFIG_MODELO`; MODELO `19_PARAMETROS` | Tipado (valor_num/valor_txt), unidad, naturaleza y uso en Python; texto del solver actualizado; duplicados y obsoletos fuera |
| 20_COSTOS | MODELO `20_COSTOS` | Tarifa por recurso; valor, margen e indicador de costo completo |
| 21_INCIDENCIAS_REAL / 22_CALIDAD_REAL | OPERATIVA `13_REG_PARADAS` / `14_REG_CALIDAD` | Plantillas con validaciones; se añaden `15_REG_TIEMPOS` y `16_REG_HABILIDADES` |
| 21B_PARADAS_ARCHIVO_ORIG | Auditoría `5F` | Archivada: equipo inexistente en SAGAPI |
| 23_ORIGEN_DATOS / 26_REGISTRO_CAMBIOS | Auditoría `5B` / `5C` | Archivadas |
| 24_VALIDACIONES | MODELO `24_VALIDACIONES` | 15 controles vivos (10 OK, 4 alertas INFO, 1 externo); se corrigen 2 controles rotos |
| 25_CAPACIDAD_CON_FALLAS | MODELO `25_PERDIDA_CAPACIDAD_ESC` | Reemplazada: 612 `#VALUE!` → 0; ahora por escenario |
| 27_SENSIBILIDAD | SIMULACION `07_SENSIBILIDAD_SIM` | Sin cambios de contenido |
| 28–33 | — | Eliminadas (resultados, no entradas) |

El detalle columna por columna (58 filas) está en la hoja `3_MAPA_MIGRACION` del libro de auditoría.

## 3. Registros: sin pérdidas

Comprobado por el verificador (V10):

| Entidad | v1.2 | v2.0 |
|---|---|---|
| Productos / materiales / líneas de despiece | 50 / 41 / 224 | 50 / 41 / 224 |
| Recursos / pasos de ruta / filas de elegibilidad | 17 / 406 / 473 | 17 / 406 / 473 |
| Trabajadores / días de calendario | 25 / 396 | 25 / 396 |
| Pedidos / operaciones de carga / FIFO | 96 / 1 152 / 1 152 | 96 / 1 152 / 1 152 |
| Eventos / escenarios / reglas de recuperación | 21 / 40 / 62 | 21 / 40 / 62 |

## 4. Valores modificados (todos intencionados y documentados)

| Cambio | Celdas | Efecto | Motivo |
|---|---|---|---|
| Texto de relleno → vacío ("No aplica", "Según especificación") | 44 + 114 + 437 | Ninguno en cálculos | Campos numéricos sin texto (E-012, E-018, E-025) |
| Costo de herrajes calculado (piezas × 0,90) | 53 | Costo de materiales anual +18 266 S/ (402 248 → 420 515) | Dato calculable que estaba vacío (E-027) |
| Planchas equivalentes × piezas | 70 | Corrige una subestimación (p. ej. bandeja del minirack de 0,25 a 1,00) | Error de fórmula (E-029) |
| Costo de máquinas con tarifa por recurso | 96 pedidos | 103 351 → 137 085 S/ | Coherencia con 04 (E-061) |
| Escenario S20A: momento y duración derivados de los eventos | 2 | Ninguno (Python no los usa) | Definición uniforme (E-073) |
| Ruido de coma flotante en tiempos de ruta | 60 operaciones | Diferencia < 1e-13 min; p_om idéntico | Limpieza (redondeo a 10 decimales) |
| Textos de naturaleza, clasificación y política normalizados | — | Ninguno | Vocabulario controlado |

**Valores que NO cambian** (comprobado en V09, a nivel de los parámetros del MILP):

- r_j, d_j, w_j, P_j, q_j y lote de los 96 pedidos;
- los 1 284 tiempos p_om y los conjuntos M_o;
- las 21 ventanas de indisponibilidad en horas productivas;
- calendario, reglas de recuperación, habilidades, parámetros leídos, masa de chapa y FIFO de referencia.

Por eso las salidas del programa son **idénticas** con ambas bases (Entregable 5).

## 5. Decisiones que cambian el significado de los datos (documentadas)

1. **Naturaleza del dato:** se reclasificó todo con 7 códigos. Se añadieron `REFERENCIA` (dato público verificable: feriados, densidad del acero, UIT), `CONFIGURACION` (ajuste del modelo, no dato de planta) y `PENDIENTE` (falta a propósito) a los 4 pedidos (REAL, CALCULADO, ESTIMADO, SIMULADO), para no forzar como "real" o "estimado" algo que no lo es.
2. **Tiempos de ruta:** pasan a `ESTIMADO`. "Valor heredado sin cronometraje" no es un dato real.
3. **Inventario de máquinas:** `ESTIMADO` con `inventario_verificado = 0`, porque la v1.2 lo declaraba "no certificado".
4. **Reglas de recuperación A/B:** `ESTIMADO` (hipótesis técnica), ubicadas en la base de simulación por ser alternativas de escenario.
5. **Feriados:** **no** se activaron, porque la práctica de SAGAPI es desconocida (PV-05). El interruptor y las fórmulas quedan listos (261 → 249 días productivos si se activan).
6. **Registro de la "roladora":** retirado de la base porque no es atribuible a SAGAPI; se conserva en la auditoría.
