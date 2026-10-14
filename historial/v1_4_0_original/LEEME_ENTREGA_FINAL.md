# SAGAPI MILP — Entrega académica final (v1.4.0)

**Este es el paquete para entregar.** Se conserva el solucionador y el mecanismo rodante de la versión 1.3.4, con una nueva auditoría de ensamblaje global referencial y una ejecución reproducible de extremo a extremo.

## 1. Qué contiene

- `Optimizacion_MILP_SAGAPI.py`: optimización y reprogramación MILP con personal integrado **para subproblemas**.
- `sagapi/`: código fuente. Nuevo: `diagnostico_global.py` para identificar conflictos de máquina, precedencia y averías al combinar compromisos y FIFO externo.
- `herramientas/generar_entrega_final.py`: validación automática, 50 tests unitarios, 40 microinstancias por objetivo, dos escenarios de Rolling Horizon, auditoría independiente y resumen final.
- `Base_Datos_SAGAPI_25_TRABAJADORES_SIMULADOS_v1_2.xlsx`: base del estudio; se conserva intacta.
- `tests/`: 50 pruebas unitarias, incluyendo cinco pruebas nuevas para el diagnóstico global.
- `EVIDENCIA_FINAL/`: reportes CSV y JSON, gráficos, logs y manifiesto SHA256 de la ejecución efectuada antes de entregar el ZIP.
- `INFORME_FINAL_SAGAPI_1_4_0.pdf`: informe breve de resultados y limitaciones para anexar a la entrega.

## 2. Ejecutar en Windows (solo una vez)

En la carpeta donde está `Optimizacion_MILP_SAGAPI.py`, hacer clic en la barra de direcciones, escribir `cmd` y presionar Enter. Luego ejecutar:

```cmd
py -3.11 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -X utf8 herramientas\generar_entrega_final.py --tl 60
```

Los resultados aparecerán en `EVIDENCIA_FINAL`. El ZIP incluye una ejecución previamente comprobada; **no necesitas volver a ejecutarla si debes entregar ahora**. La ejecución adjunta se hizo en Python 3.13 / Linux, por lo que repetir los comandos en Python 3.11 / Windows constituye una prueba adicional de portabilidad, aún no realizada para esta compilación.

## 3. Indicadores probados en la ejecución incluida

- Validación de datos: 96 pedidos, 1.152 operaciones, 15 máquinas, 4 familias.
- 50/50 pruebas unitarias correctas y 40/40 microinstancias por objetivo.
- S08A: 5 ventanas de ocho horas; 4 pedidos coordinados; 23 operaciones comprometidas; 56 reservas externas únicas exportadas; sin errores en la auditoría independiente.
- S13A: 3 ventanas; 2 pedidos; 2 operaciones comprometidas; 54 reservas externas únicas; sin errores en la auditoría independiente.
- Diagnóstico de ensamblaje global FIFO+MILP: **0 incidencias** en S08A y **1 cruce con avería** en S13A. Estos diagnósticos son sobre una fusión hipotética, no sobre una optimización anual real.

## 4. Afirmaciones que NO debes hacer en tu artículo

**NO** afirmar que el Rolling Horizon completo resolvió o validó los 96 pedidos. **NO** presentar las penalidades de ventanas sucesivas como ahorros acumulados. **NO** declarar competencias reales verificadas para los 25 trabajadores. **NO** afirmar que todas las fechas feriadas fueron validadas o que hubo ahorros reales comprobados. El nuevo diagnóstico global no acredita factibilidad real: informa los conflictos de un programa FIFO hipotético ensamblado con los compromisos del piloto.

## 5. Texto para la memoria científica

> Se implementó y verificó computacionalmente un prototipo de optimización predictivo-reactiva basado en programación lineal entera mixta (MILP), con prioridades lexicográficas de penalidad, tardanza e inestabilidad, restricciones de asignación de trabajadores y reprogramación por horizonte rodante. Las pruebas piloto S08A y S13A superaron auditorías independientes de intervalos comprometidos, recursos y jornada laboral modelada. Las habilidades individuales y parte de los datos de producción son simulados; se requiere validación operativa adicional para extender los resultados al conjunto anual de 96 pedidos.

**La nota técnica específica y los resultados exactos están en `EVIDENCIA_FINAL/INFORME_TECNICO_ENTREGA.md` y en el PDF.**
