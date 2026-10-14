# SAGAPI 1.3.0 — Piloto de asignación integrada trabajador–operación

**Estado:** prototipo metodológico controlado; NO validado para todo el horizonte anual ni para competencias reales del personal.

## Qué cambia con respecto a 1.2.1

Se añade `sagapi/personal_integrado.py` y el comando **`integrar-personal`**, que crea y resuelve un MILP donde se elige simultáneamente:

- Máquina para la operación (`x[o,m]`).
- Trabajador para cada operación libre (`q[o,w]`).
- Precedencia entre operaciones de pedidos diferentes que podrían compartir operario (`r[a,b]`).
- Compatibilidad `q[o,w] <= sum(x[o,m] para máquinas que w puede atender)`.
- Exclusión del trabajo simultáneo de un mismo operario en máquinas diferentes.
- Ocupación de trabajadores por operaciones **ya fijadas y en curso** al momento de la perturbación.

Se supone **un trabajador por operación**, sin relevos intraproceso y con el mismo trabajador asignado a la operación si ésta atraviesa un descanso del calendario. Son supuestos para estudiar el algoritmo, no hechos confirmados por SAGAPI. Todas las habilidades OP-01...OP-25 son **simuladas**.

**Crítico:** el nuevo comando se aplica exclusivamente al subconjunto de pedidos activos elegido mediante `--pedidos`; las demás operaciones anuales no entran en el subproblema integrado. **No es una validación de 96 pedidos**, y no debe presentarse como tal. Por diseño se limita a un máximo inicial de **24 operaciones libres**. Las funciones `anual`, `escenarios`, `montecarlo`, `pareto`, `sensibilidad` siguen usando la formulación heredada 1.2.1 (reserva conservadora por máquina), no la integrada. No mezclar resultados de ambos enfoques en un mismo informe como si fueran un modelo único.

Los objetivos P1, P2 y P3 conservan las tres prioridades anteriores. El piloto evita reparaciones horarias ex post que podrían invalidar la asignación de trabajadores y verifica la solución MILP y los intervalos laborales por separado.

## Instalación en Windows 10/11

Abra CMD desde esta carpeta:

```cmd
py -3.11 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -X utf8 Optimizacion_MILP_SAGAPI.py validar
.venv\Scripts\python.exe -X utf8 -m unittest discover -s tests -p "test_*.py" -v
.venv\Scripts\python.exe -X utf8 -m tests.test_enumeracion 40
```

### Primer piloto integrado (incluye una operación interrumpida en el subconjunto)

```cmd
.venv\Scripts\python.exe -X utf8 Optimizacion_MILP_SAGAPI.py integrar-personal --escenario S13A --pedidos 2 --tl 30 --salida resultados_piloto
```

Crea en `resultados_piloto`:

- `personal_milp_S13A_2pedidos.csv`: operario simulado, máquina, paso, tiempos y estado fijo/libre.
- `personal_milp_S13A_2pedidos_resumen.json`: fases, certificación del solucionador, objetivo modelado, asignaciones, errores y tamaño del problema.

**Aceptación:** `errores: []`, asignaciones para todas las operaciones libres y fijas activas, y `certificado_lexicografico_completo: true`. Si aparece `Feasible` y no `Optimal`, no afirmar optimalidad certificada. Cada fase tiene su propio límite `--tl`.

## Qué se probó en desarrollo

- 17 pruebas unitarias (13 heredadas + 4 nuevas sobre trabajador compartido, fijas y habilidades).
- Enumeración f1/f1b/f2: 40/40 en cada objetivo; 0 violaciones.
- S08A 2 y 3 pedidos, S13A 2 pedidos: resolución P1/P2/P3 con estado Optimal y verificador independiente sin errores, *sólo para los pedidos incluidos*.
- Contraejemplo de **un trabajador capaz de atender dos máquinas**: la reserva permanente 1.2.1 declara la instancia inviable; el MILP integrado encuentra una secuencia factible sin solapamientos.

Estas pruebas no garantizan escalabilidad a los 96 pedidos ni condiciones de planta.

## Datos pendientes y riesgos

1. **Calendario:** la hoja 07_CALENDARIO marca como productivos, entre otros, 2025-01-01, 2025-07-28, 2025-07-29, 2025-12-08, 2025-12-25 y 2026-01-01. **No modificamos estas marcas** por falta de confirmación de la empresa. Confirmar si efectivamente se trabaja esos días y las reglas de feriados.
2. **Habilidades:** falta matriz certificada de los 25 trabajadores, necesidades reales de dotación por operación, actividades indirectas y ausencias.
3. **Escalabilidad:** aumentar gradualmente el número de operaciones; el modelo usa disyunciones por parejas y puede crecer rápidamente. El límite inicial de 24 es deliberado.
4. **Cobertura global:** el modo piloto considera los pedidos elegidos y las operaciones fijadas en su subproblema; no comprueba conflictos con todas las órdenes excluidas que también puedan estar trabajando en planta.
5. **Penalidades:** supuestos de modelado; no pagos reales verificados.

El siguiente hito NO es repetir todo Monte Carlo: es resolver la escalabilidad y la cobertura del programa completo antes de nuevas conclusiones del paper.

**Mantener intactas las carpetas 1.1.0, 1.2.0 y 1.2.1 y sus resultados.**
