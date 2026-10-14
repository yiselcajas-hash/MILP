# SAGAPI MILP 1.3.2 — Piloto con reservas futuras externas

**Estado: PILOTO ACOTADO, NO VALIDADO COMO PROGRAMACIÓN ANUAL.**

## Qué representa

- **Confirmado por SAGAPI:** 25 trabajadores de producción; un único turno de ocho horas; rotación de personal entre áreas según carga de trabajo.
- **Supuesto NO verificado:** perfiles y habilidades individuales en `06B_HABILIDADES`, un trabajador por operación sin relevo intraproceso, horas productivas y calendario del Excel. Las penalidades monetarias son modeladas/simuladas, no desembolsos reales demostrados.
- La base Excel **no se ha modificado** con respecto a 1.3.1.

## Avance frente a 1.3.1

1. Se conservan las operaciones que ya estaban activas y los pedidos interrumpidos en la falla; si es necesario, el pedido ajeno se incorpora automáticamente (ejemplo S08A añade P071).
2. **NUEVO — máquinas externas futuras:** durante un horizonte experimental de **96 horas productivas desde la falla**, las operaciones futuras excluidas del MILP mantienen horarios y máquinas del programa FIFO de referencia como *reservas rígidas*. El MILP no puede usar esas máquinas en intervalos reservados.
3. **NUEVO — trabajadores externos futuros:** las operaciones excluidas en ese horizonte reciben una asignación determinista basada en habilidades SIMULADAS, que se congela. El MILP no puede asignar ese trabajador a operaciones superpuestas, aunque sean en otra máquina. Tampoco puede asignarlo a una operación ya activa que se prolongue dentro de la reserva externa.
4. **NUEVO — auditoría explícita:** se exporta el CSV `_externos_reservados.csv` junto con la tabla de asignaciones del subproblema, segmentos laborales y resumen JSON. El verificador independiente contrasta máquinas, personas y reservas.
5. **NUEVO — alcance honesto:** el JSON distingue reservas protegidas, operaciones fuera del horizonte, posibles choques del plan externo con la avería y cruces fuera de la protección.

**Limitación fundamental:** las reservas externas son el calendario FIFO congelado como escenario *hipotético*. NO se optimizan conjuntamente ni se demuestra que el FIFO externo siga siendo viable después de la falla. Por eso un piloto con cero cruces en las reservas NO certifica un plan de toda SAGAPI, ni la plena coordinación de los 96 pedidos.

Los comandos heredados `anual`, `escenarios`, `montecarlo`, `pareto`, `sensibilidad` no utilizan aún esta formulación de personal integrado. No reutilizar sus resultados como validación de v1.3.2.

## Cómo instalar en Windows

Dentro de la carpeta descomprimida, escribe `cmd` en la barra de direcciones del Explorador y pulsa Enter.

```cmd
py -3.11 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -X utf8 Optimizacion_MILP_SAGAPI.py validar
.venv\Scripts\python.exe -X utf8 -m unittest discover -s tests -p "test_*.py" -v
.venv\Scripts\python.exe -X utf8 -m tests.test_enumeracion 40
```

Ejecutar caso recomendado (sin modificar 1.3.1 ni sus archivos):

```cmd
.venv\Scripts\python.exe -X utf8 Optimizacion_MILP_SAGAPI.py integrar-personal --escenario S08A --pedidos 3 --max-operaciones 36 --horizonte-externos 96 --tl 60 --salida resultados_piloto_132
```

Otra prueba (operación externa activa en t0):

```cmd
.venv\Scripts\python.exe -X utf8 Optimizacion_MILP_SAGAPI.py integrar-personal --escenario S05A --pedidos 2 --horizonte-externos 96 --tl 60 --salida resultados_piloto_132
```

## Resultados de desarrollo medidos (Python 3.11+ / SciPy HiGHS)

- **28/28 pruebas unitarias**, incluidas cuatro nuevas de reservas de máquinas y trabajadores y verificador adversarial.
- **40/40** pruebas de enumeración para cada objetivo f1, f1b y f2; cero violaciones.
- S08A: solicita 3 pedidos, añade P071; **4 pedidos, 32 operaciones libres**. Reserva **30 operaciones externas** en 96 horas productivas; **301 operaciones futuras externas** quedan fuera. Las 3 fases fueron óptimas certificadas, 35 asignaciones de personal, cero errores del verificador, cero cruces en el horizonte protegido y cero cruces observados con el FIFO restante en ese experimento; **f1= S/ 3.612,81** (penalidad modelada, solo pedidos del piloto).
- S05A: 2 pedidos, 12 operaciones libres y 1 operación externa activa en t0; **39 reservas futuras externas**, 423 futuras fuera. Tres fases óptimas, sin errores del verificador.

Los indicadores de S08A **no son directamente comparables** con la versión 1.3.1 como un beneficio puro de optimización, porque la formulación está más restringida; se mantienen las mismas órdenes de piloto, pero el calendario externo cambia de hipótesis. 

## Próximas correcciones antes de escribir el paper

1. Sustituir el calendario externo hipotético por un proceso de **reprogramación coordinada** del conjunto de pedidos relevantes con capacidad global, incluyendo efectos en cascada.
2. Pruebas de escalabilidad con horizontes rodantes mayores, límites de tiempo y memoria; evitar ampliar arbitrariamente el número de operaciones.
3. Verificar con SAGAPI habilidades, ausencias, tareas indirectas, descansos y si se trabaja en feriados marcados como productivos. No usar certificados matemáticos como prueba de esos datos.
4. Evaluación de penalidad, tardanza, estabilidad, y equidad entre familias únicamente después de definir alcance y bases homogéneas.

**Conservar las versiones 1.1.0, 1.2.x, 1.3.0 y 1.3.1** para reproducibilidad.
