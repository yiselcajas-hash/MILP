# SAGAPI — Auditoría integral y base de datos v2.0

Esta carpeta contiene la auditoría del proyecto SAGAPI MILP 1.4.0 y la base de datos reconstruida. **El Excel original y el código no se modificaron**: todo lo nuevo está aquí y en `herramientas/*_v2.py`.

## Entregables

| N.º | Entregable | Archivo |
|---|---|---|
| 1 | Informe de auditoría integral (Excel hoja por hoja, celdas vacías, realismo industrial, MILP, mapa Excel–Python) | `informes/E1_Informe_Auditoria_Integral.md` |
| 2 | Matriz de errores del Excel (84 hallazgos con hoja, rango, evidencia, corrección o motivo) + 18 pendientes de validación + mapa de migración + dependencias de Python + procedencia archivada | `auditoria/SAGAPI_AUDITORIA_DATOS_v2_0.xlsx` (y los CSV equivalentes) |
| 3 | Excel corregido: base **operativa**, base de **simulación** y libro **MODELO** compatible con Python 1.4.0 | `base_datos/SAGAPI_BD_OPERATIVA_v2_0.xlsx`, `SAGAPI_BD_SIMULACION_v2_0.xlsx`, `SAGAPI_BD_MODELO_v2_0.xlsx` |
| 4 | Informe de cambios v1.2 → v2.0 | `informes/E4_Informe_Cambios.md` |
| 5 | Resultados de las verificaciones (11 comprobaciones de datos + 8 ejecuciones del programa, original frente a v2.0) | `informes/E5_Resultados_Verificacion.md`, `verificacion/` |
| 6 | Diagnóstico del código y del MILP (25 hallazgos con evidencia) | `informes/E6_Diagnostico_Codigo.md` |
| 7 | Plan maestro de mejoras (matriz P0–P3 y hoja de ruta de 24 pasos) | `informes/E7_Plan_Maestro_Mejoras.md` |

## Uso rápido

```bash
# Ejecutar el programa actual con la base v2.0 (sin cambiar el código)
python Optimizacion_MILP_SAGAPI.py validar --excel entrega_v2_0/base_datos/SAGAPI_BD_MODELO_v2_0.xlsx

# Tras editar OPERATIVA o SIMULACION: regenerar, recalcular y verificar
python herramientas/construir_bd_v2.py --paso modelo
python herramientas/recalcular_bd_v2.py entrega_v2_0/base_datos/*.xlsx      # requiere LibreOffice; si no, abrir y guardar en Excel
python herramientas/verificar_bd_v2.py --pruebas-python

# Reconstruir todo desde el Excel v1.2 original (reproducible)
python herramientas/construir_bd_v2.py --paso todo
python herramientas/generar_auditoria_v2.py
```

## Convenciones de la base v2.0

- **Naturaleza del dato** (columna `naturaleza` y diccionario):

  | Código | Significado |
  |---|---|
  | `REAL` | Declarado por la empresa |
  | `REFERENCIA` | Público y verificable |
  | `CALCULADO` | Fórmula reproducible |
  | `ESTIMADO` | Aproximación que requiere validación |
  | `SIMULADO` | Artificial, para probar el modelo |
  | `CONFIGURACION` | Ajuste del modelo |
  | `PENDIENTE` | Falta a propósito |

- Texto **azul** = dato introducido; texto **negro** = fórmula. Fechas en `AAAA-MM-DD`. Moneda `S/` con 2 decimales. Fracciones con formato `%`.
- Cada libro trae `00_DICCIONARIO` (hoja, columna, tipo, unidad, obligatorio, naturaleza, uso en Python) y `00_CODIGOS`.
- El libro **MODELO** se genera: no se edita a mano.

## Lo que la base v2.0 no puede resolver

Los tiempos de ruta, los pedidos, las habilidades y las fallas siguen siendo **estimados o simulados**, porque no hay datos de SAGAPI que los sustenten. Están listados en `auditoria/…/2_PENDIENTES_VALIDACION` (prioridad P0: tiempos, habilidades, pedidos reales y la brecha de horas-hombre). La base trae plantillas de captura (`12_REG_ENTREGAS` a `16_REG_HABILIDADES`) para reemplazarlos.
