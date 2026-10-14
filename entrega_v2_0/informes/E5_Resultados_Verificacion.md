# Entregable 5 — Resultados de las verificaciones

**Ejecución:** 2026-10-14 · Python 3.13.16 · SciPy 1.18.1 (HiGHS) · NumPy 2.5.3 · openpyxl 3.1.5 · LibreOffice (recálculo).

**Evidencia:**

- `entrega_v2_0/verificacion/verificacion_bd_v2.json` (resultado estructurado) y `verificacion_bd_v2.log`.
- `logs/` (salida completa de cada comando, con el original y con la v2.0).
- `anual_E1/` (corrida `anual`).
- `evidencia_diagnostico_codigo.json`.

**Para repetirlo:**

```
python herramientas/verificar_bd_v2.py --pruebas-python --tl 60
```

El script copia el programa a carpetas temporales, ejecuta cada comando con el libro original y con el MODELO v2.0 y compara las salidas.

**Integridad del original:** SHA-256 del Excel v1.2 antes y después de todo el trabajo: `8f75befcf29a4628c1e737999bb1c4ad37b25ce81fb9cf5cad0c50917b7fffb3`. Coincide con `EVIDENCIA_FINAL/MANIFIESTO_SHA256.csv`, así que **no se modificó**.

## 1. Comprobaciones de la base (las 10 exigidas + reproducibilidad)

| # | Comprobación exigida | Prueba | Resultado | Detalle |
|---|---|---|---|---|
| 1 | Identificadores y claves | V01 | **PASA** | 19 tablas, 3 296 claves sin duplicados ni nulos; nombres de producto, recurso y material únicos |
| 2 | Campos obligatorios | V02 | **PASA** | Todos los campos con `obligatorio_1_0 = 1` en `00_DICCIONARIO` tienen valor |
| 3 | Duplicados | V03 | **PASA** | Ninguna hoja de los tres libros tiene filas idénticas |
| 4 | Formatos numéricos | V04 | **PASA** | Sin texto en campos numéricos; enteros enteros; binarios en {0, 1}; sin negativos; fechas y horas tipadas; 0 errores de fórmula |
| 5 | Unidades y fórmulas | V05 + recálculo | **PASA** | Recálculo independiente en Python de área, masa (7 850 kg/m³), costo, planchas, precio, calendario, capacidad, jornada (8 h), plazo, fin de evento, p_om (= `sagapi.datos.duracion_h`), carga mensual y valor/penalidad: coinciden con tolerancia 1e-6. LibreOffice recalculó 21 750 fórmulas con **0 errores** |
| 6 | Integridad referencial | V06 | **PASA** | 18 relaciones sin códigos huérfanos; todo producto con pedido tiene ruta y despiece |
| 7 | Tiempos, rutas y capacidades | V07 | **PASA** | Pasos correlativos con predecesor lineal; principal de elegibilidad = recurso de ruta; ningún recurso usado con cantidad 0; 25 trabajadores; calendario continuo; fechas ordenadas; eventos sin solapes dentro de cada escenario; **carga ≤ capacidad en los 204 recurso-mes** (máximo 81 %, plegadora en junio) |
| 7b | Alertas de realismo | V07b | **ALERTA** | 3 pedidos con ruta mayor que su ventana (P049, P050, P058); 43 pedidos con fecha en fin de semana. No bloquean: requieren datos reales |
| 8 | Compatibilidad con la lectura de Python | V08 | **PASA** | `sagapi.datos.leer` + `validar` sobre el MODELO: 96 pedidos, 406 pasos, 17 recursos, 21 eventos, 40 escenarios |
| 9 | Parámetros del MILP | V09 | **PASA** | **Idénticos al original:** r_j, d_j, w_j, P_j, q_j, lote, M_o, 1 284 tiempos p_om, 21 ventanas (a, b), calendario, recuperación, habilidades, parámetros leídos, masa de chapa y FIFO |
| 10 | Comparación con el original | V10 | **PASA** | 0 registros perdidos en 14 entidades; solo cambios intencionados: 437 textos de relleno → vacío, 53 costos de herrajes calculados, 70 planchas corregidas |
| 11 | Reproducibilidad | V11 | **PASA** | El MODELO regenerado desde OPERATIVA + SIMULACION coincide celda a celda (58 920 celdas, 0 diferencias) |

## 2. Pruebas automáticas y ejecución del programa (código 1.4.0 sin cambios)

| Comando | Original v1.2 | MODELO v2.0 | Salidas |
|---|---|---|---|
| `validar` | OK (2,9 s) | OK (2,1 s) | `validacion_datos.json` idéntico (FIFO reproduce 16_PROGRAMA_BASE, dif. máx. 1,7e-6 h) |
| `python -m unittest` (50 pruebas) | **50/50 OK** | **50/50 OK** | — |
| `python -m tests.test_enumeracion 40` | f1 40/40, f1b 40/40, f2 40/40, 0 violaciones | ídem | — |
| `rodante-personal S08A` (3 pedidos, 5 ventanas) | OK: 23 compromisos, 56 reservas, 0 errores | ídem | compromisos y decisiones **idénticos** |
| `rodante-personal S13A` (2 pedidos, 3 ventanas) | OK: 2 compromisos, 54 reservas, 0 errores | ídem | **idénticos** |
| `integrar-personal S13A` | OK: 18 asignaciones, 5 trabajadores, 0 errores | ídem | **idénticos** |
| `caso S06A` (CONV, EDD, MILP-MONO, MILP-LEX) | OK (10,5 s) | OK (9,9 s) | programa y cambios **idénticos** |
| `anual` (S00 y S20A, 8 combinaciones) | OK (62 s) | OK (61 s) | `E1_anual.csv` idéntico salvo los tiempos de cómputo; 96 decisiones MILP, todas ÓPTIMO |

**No ejecutados** (por duración; no hay indicios de incompatibilidad, ya que V09 prueba que los parámetros de entrada son idénticos): `escenarios`, `montecarlo`, `pareto`, `sensibilidad`, `todo` y `herramientas/generar_entrega_final.py` (que repite pruebas ya cubiertas arriba).

`reportes --escribir-excel` no se ejecutó a propósito, porque sobrescribe el Excel de entrada (C-19). El MODELO v2.0 incluye la hoja `24_VALIDACIONES` con la fila que ese comando actualiza, de modo que seguiría funcionando.

## 3. Nivel real de compatibilidad con Python

- **Compatibilidad funcional total con el código 1.4.0 sin modificaciones** usando `SAGAPI_BD_MODELO_v2_0.xlsx`: misma lectura, mismos parámetros MILP, mismas salidas en todos los comandos ejecutados.
- Las bases fuente (OPERATIVA y SIMULACION) **no** las lee directamente el código 1.4.0. Su lectura directa es el Paso 3 del plan (M-02); mientras tanto el MODELO se regenera con `construir_bd_v2.py --paso modelo`.
- Que las pruebas pasen **no** valida el sistema industrialmente. Las pruebas comprueban coherencia matemática y de datos, no que tiempos, pedidos, habilidades o fallas correspondan a la planta (Entregable 1, §1).

## 4. Errores pendientes y su naturaleza

| Pendiente | Tipo | Dónde se resuelve |
|---|---|---|
| Rutas que exceden la ventana; fechas en fin de semana | Supuesto problemático (datos simulados) | PV-03 (pedidos reales) |
| Tiempos no cronometrados; habilidades simuladas; brecha de horas-hombre | Supuesto problemático | PV-01, PV-02, PV-04 |
| Curado partido entre jornadas; R11 que no restringe; capacidad 1 | **Error o defecto del código**, no del Excel | Plan M-05, M-04, M-08 |
| Unidad del precio del perfil; espesores; precios faltantes | Defecto del Excel no resoluble sin la empresa | PV-11 a PV-13 |

Ninguna prueba falló. Las alertas listadas son propiedades de los **datos simulados** o **limitaciones del código**, no defectos de la base v2.0.
