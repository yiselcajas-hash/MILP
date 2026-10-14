# SAGAPI MILP 1.3.3 — Piloto de horizonte rodante (experimental)

## Qué incorpora

- El comando **`rodante-personal`** para reoptimizar los pedidos elegidos en ventanas consecutivas de horas productivas.
- Cada ventana compromete solamente las operaciones nuevas cuyo inicio cae antes del cierre del turno siguiente (8 horas por defecto). Las operaciones ya iniciadas **conservan máquina, trabajador y horario**; el plan provisional futuro puede cambiar.
- Se mantienen la inclusión automática de pedidos interrumpidos por una avería y las reservas de máquina y trabajadores simulados de pedidos externos durante un horizonte limitado.
- Se conservan, cuando es posible, los trabajadores simulados asignados a operaciones externas al pasar a otra ventana.
- La auditoría comprueba inmutabilidad, no solapamiento de compromisos y jornada del Excel; se detiene sin certificar las ventanas restantes si falla alguna comprobación.

## Alcance científico — imprescindible

**No constituye un simulador anual de horizonte rodante ni una planificación global óptima de 96 pedidos.** En este piloto se reoptimiza el mismo grupo de pedidos a lo largo de varias decisiones consecutivas, y los restantes siguen como **reservas de un programa FIFO de referencia** dentro de un horizonte finito. El historial de ventanas conserva planes *provisionales* para el futuro, y la auditoría da cuenta únicamente de las operaciones *comprometidas*.

La cifra **25 trabajadores**, un único **turno de 8 horas** y la **asignación variable según producción** proceden de información confirmada de SAGAPI. **Sus habilidades individuales, la asistencia, los roles fuera de máquina, los tiempos de las órdenes, los costos de penalidad y los feriados modelados NO han sido contrastados con la planta**: siguen siendo datos simulados o supuestos. No usar el piloto para afirmar ahorros reales, capacidad suficiente ni factibilidad anual completa.

El programa usa **horas productivas**: 8 horas corresponden a un turno, no a ocho horas continuas de reloj. El calendario del Excel es la autoridad *del modelo*, no un calendario laboral confirmado por la empresa. Una operación iniciada en un turno puede continuar en un turno posterior con el mismo trabajador simulado.

## Instalación en Windows

Desde CMD abierto dentro de esta carpeta:

```cmd
py -3.11 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -X utf8 Optimizacion_MILP_SAGAPI.py validar
.venv\Scripts\python.exe -X utf8 -m unittest discover -s tests -p "test_*.py" -v
.venv\Scripts\python.exe -X utf8 -m tests.test_enumeracion 40
```

## Primera prueba de ventanas rodantes

```cmd
.venv\Scripts\python.exe -X utf8 Optimizacion_MILP_SAGAPI.py rodante-personal --escenario S08A --pedidos 3 --ventanas 3 --paso-rodante 8 --max-operaciones 36 --horizonte-externos 120 --tl 60 --salida resultados_rodante_133
```

El comando exporta:

- `rodante_S08A_resumen.json`: estado de ejecución, número de ventanas, objetivos por ventana, reservas y advertencias de cobertura.
- `rodante_S08A_decisiones.csv`: horario planificado en cada ventana, **incluye operaciones aún no comprometidas** (pueden cambiar después).
- `rodante_S08A_compromisos.csv`: operaciones cuyos comienzos quedaron comprometidos en alguno de los turnos examinados.
- `rodante_S08A_compromisos_jornadas.csv`: descomposición por fecha, horario y persona simulada de los compromisos.

Para otro ejemplo, S13A con 2 pedidos: reemplazar `--escenario S08A --pedidos 3` por `--escenario S13A --pedidos 2`, y usar otra carpeta con `--salida` para no mezclar resultados.

## Pruebas realizadas por desarrollo

- `unittest`: **36 pruebas**, que incluyen las 28 anteriores y 8 pruebas nuevas de inmutabilidad/solapamientos de compromisos.
- Enumeración: **40/40 para f1, f1b y f2**, violaciones 0.
- Piloto S08A: tres ventanas de 8 horas resueltas, cuatro pedidos (incluido P071), 17 operaciones iniciadas y comprometidas, sin ruptura de compromisos; de forma ilustrativa, primera ventana con penalidad **S/ 3.612,81**.
- Piloto S13A: tres ventanas de 8 horas resueltas, dos pedidos, 2 operaciones comprometidas. En S13A algunas ventanas no inician nuevas operaciones; no es una prueba de toda la planta.

**No se vuelve a ejecutar el conjunto anual, Monte Carlo o Pareto con este comando**. El siguiente paso de investigación sería ensayar la expansión controlada del conjunto de pedidos reprogramables, registrar eventos sucesivos reales/simulados y comprobar la consistencia integral de las 1.152 operaciones. Antes de escalar, confirmar feriados y habilidades reales o hacer análisis de sensibilidad explícito.
