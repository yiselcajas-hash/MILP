# SAGAPI MILP 1.3.1 — Piloto con cobertura de operaciones activas y auditoría de turnos

**Estado: PROTOTIPO CONTROLADO — NO VALIDADO COMO PROGRAMA ANUAL NI COMO PLANTILLA DE HABILIDADES REALES.**

Se conserva sin modificar el archivo `Base_Datos_SAGAPI_25_TRABAJADORES_SIMULADOS_v1_2.xlsx`: son **25 trabajadores reales en un turno de ocho horas** según la empresa, pero sus **habilidades individuales se simularon**. La asignación de **un operario por operación, sin relevo intraproceso** es un supuesto de la formulación, no una confirmación de planta.

## Cambios respecto a 1.3.0

1. **Protección de operaciones ya iniciadas en otros pedidos.** Si la máquina que falla está ocupada por un pedido excluido, el pedido afectado se incorpora automáticamente al MILP. No permite congelar una operación que acaba de ser interrumpida.
2. **Otras máquinas ocupadas en t0.** La operación ajena que estaba trabajando en una máquina sana queda congelada hasta su finalización; consume máquina y trabajador habilitado dentro del MILP. La comprobación independiente verifica ambos recursos.
3. **Turnos y descansos auditables.** Cada operación con personal se divide en tramos productivos reales de `07_CALENDARIO` y se exporta un segundo CSV con fecha, entrada, salida y horas. No se suman almuerzos, noches ni días marcados como no productivos. Se comprueba el límite de 8 horas productivas por trabajador y día *dentro del piloto*.
4. **Límite experimental de escalabilidad:** máximo predeterminado de 36 operaciones libres, frente a 24 en la versión anterior. No es prueba de escalabilidad a 96 pedidos ni a 1.152 operaciones.
5. **Advertencia explícita sobre las operaciones futuras de otros pedidos.** Permanecen fuera del MILP. Se calcula el número de cruces de máquina con su cronograma FIFO de referencia, **solo como diagnóstico**, sin ocultar que la cobertura global no está demostrada.

**Los comandos `anual`, `escenarios`, `montecarlo`, `pareto` y `sensibilidad` mantienen el modelo heredado, no ejecutan la nueva integración laboral. No publicarlos como resultados del MILP integrado 1.3.1.**

## Ejecutar en Windows

En el Explorador abre la carpeta de este paquete, escribe `cmd` en la barra de direcciones y pulsa Enter.

```cmd
py -3.11 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -X utf8 Optimizacion_MILP_SAGAPI.py validar
.venv\Scripts\python.exe -X utf8 -m unittest discover -s tests -p "test_*.py" -v
.venv\Scripts\python.exe -X utf8 -m tests.test_enumeracion 40
```

### Prueba recomendada: un pedido externo que también sufre la avería

```cmd
.venv\Scripts\python.exe -X utf8 Optimizacion_MILP_SAGAPI.py integrar-personal --escenario S08A --pedidos 3 --max-operaciones 36 --tl 60 --salida resultados_piloto_131
```

**Es esperable que el programa incluya 4 pedidos, no 3.** Detecta y añade el pedido `P071` que en el programa base estaba trabajando en la plegadora cuando sucede la falla. Esto genera 32 operaciones libres en el subproblema analizado. Las cifras y el objetivo cambian respecto a 1.3.0 porque **se está optimizando un conjunto distinto de pedidos**.

### Prueba alternativa: una operación externa en una máquina que sigue funcionando

```cmd
.venv\Scripts\python.exe -X utf8 Optimizacion_MILP_SAGAPI.py integrar-personal --escenario S05A --pedidos 2 --tl 60 --salida resultados_piloto_131
```

**Salidas** para cada caso `personal_milp_<escenario>_<N>pedidos`:

- `.csv`: una asignación trabajador–operación por operación libre o en curso, incluyendo externas en t0.
- `_segmentos.csv`: cortes por mañana/tarde y por día, con fecha y horas reales.
- `_resumen.json`: estado y certificación por fase, fallas de verificación, pedidos incorporados automáticamente, ocupación externa en t0, conteo de pedidos futuros sin integrar y cruces con el programa FIFO futuro.

**Criterio de aceptación local:** las tres fases deben figurar `Optimal` y certificadas; `errores` debe ser lista vacía; comprobar la auditoría de turnos. Esto NO convierte al plan local en un plan anual factible.

## Pruebas de desarrollo ejecutadas

- 24 pruebas unitarias (17 heredadas + 7 nuevas de ocupación externa y calendario), aprobadas.
- 40/40 en f1, f1b y f2, con 0 violaciones de enumeración.
- S13A: 2 pedidos, 17 operaciones libres, 3 fases óptimas, 0 errores locales.
- S08A: solicita 3 pedidos, añade P071, resuelve 4 pedidos y 32 operaciones libres, 3 fases óptimas, 0 errores locales. **Se identificaron 3 cruces de máquina con operaciones FUTURAS excluidas del MILP** en su programación FIFO de referencia.
- S05A: 2 pedidos, se congela 1 operación externa en curso y se le asigna personal, 3 fases óptimas, 0 errores locales. **Se identificaron 4 cruces con operaciones FUTURAS excluidas** en el FIFO de referencia.

No usar la penalidad cero de la antigua prueba S08A de 3 pedidos como si continuara vigente al incorporar el cuarto pedido.

## Pendientes antes del artículo científico

1. **Cobertura futura completa:** incluir y reprogramar las operaciones de todos los pedidos activos y futuros relevantes, no solo las activas en t0. Los cruces informados respecto del plan FIFO evidencian la limitación actual, no necesariamente errores de un programa de planta que todavía no se ha construido.
2. **Escalabilidad:** probar gradualmente más operaciones y mayores horizontes con límites de tiempo y validación independiente.
3. **Feriados 2025–2026:** `07_CALENDARIO` tiene algunos feriados marcados como productivos; **no se modificó** el Excel ni se confirmó si SAGAPI trabajó esas fechas.
4. **Habilidades reales, asistencia, dotación por proceso, turnos especiales, actividades indirectas y descansos individuales:** pendientes de confirmar en la empresa.
5. **Proyección al manuscrito:** recalcular experimentos solo después de implementar un modelo anual integral; las penalidades del estudio son simuladas/modeladas y no desembolsos contractuales demostrados.

**Conservar las versiones 1.1.0, 1.2.x y 1.3.0, con sus resultados, para trazabilidad.**
