# SAGAPI MILP 1.3.4 — Horizonte rodante con auditoría reproducible

## Qué incorpora de nuevo

Esta versión es una **extensión experimental de la 1.3.3**. Mantiene el solucionador MILP con trabajador–operación integrado y las reservas de pedidos externos basadas en el programa FIFO simulado.

Las novedades específicas son:

1. **Reserva externa por ventana:** genera `rodante_<escenario>_reservas_externas_por_ventana.csv` con identificador de operación, máquina, trabajador simulado, inicio, final, ventana y tipo (futura FIFO o externa activa). Una misma reserva puede aparecer repetida en distintas ventanas; las repeticiones se auditan por identificador.
2. **Continuidad entre turnos:** genera `rodante_<escenario>_arrastres_entre_turnos.csv` para operaciones previamente comprometidas que siguen en ejecución al comenzar otra ventana. Comprueba que máquina, horario y trabajador sigan iguales.
3. **Auditoría acumulada de reservas y compromisos:** antes de confirmar cada ventana, comprueba que las operaciones comprometidas no se solapen con las reservas externas observadas hasta ese momento, ni cambien las reservas de ventanas previas.
4. **Comprobación independiente posterior:** `herramientas/auditar_rodante_csv.py` revisa los archivos CSV/JSON **sin ejecutar el solucionador**. Comprueba intervalos, trabajadores, continuidad, orígenes de los compromisos y el máximo de ocho horas/día dentro del calendario modelado.

## Alcance y datos reales frente a supuestos

**Confirmado con SAGAPI:** 25 trabajadores en producción, un único turno de ocho horas, asignación flexible por necesidades productivas.

**Simulado o no verificado con la empresa:** competencias individuales, disponibilidades reales, contenido y fecha de pedidos, cronogramas FIFO externos, penalidades contractuales, tareas indirectas y marcas de días feriados en `07_CALENDARIO`.

**No se ha demostrado factibilidad anual.** El piloto reoptimiza un subconjunto de pedidos mientras conserva solo una parte de los pedidos externos como reservas hipotéticas por un horizonte finito. No representa una optimización integrada de los 96 pedidos ni de las 1.152 operaciones. Las fases óptimas son óptimas **para cada subproblema**, no para toda SAGAPI.

## Instalación en Windows (Python 3.11)

Desde CMD abierto en esta carpeta:

```cmd
py -3.11 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -X utf8 Optimizacion_MILP_SAGAPI.py validar
.venv\Scripts\python.exe -X utf8 -m unittest discover -s tests -p "test_*.py" -v
.venv\Scripts\python.exe -X utf8 -m tests.test_enumeracion 40
```

## Ejemplo principal: S08A, tres ventanas

```cmd
.venv\Scripts\python.exe -X utf8 Optimizacion_MILP_SAGAPI.py rodante-personal --escenario S08A --pedidos 3 --ventanas 3 --paso-rodante 8 --max-operaciones 36 --horizonte-externos 120 --tl 60 --salida resultados_rodante_134
```

**Auditoría independiente a partir de los archivos exportados:**

```cmd
.venv\Scripts\python.exe -X utf8 herramientas\auditar_rodante_csv.py --carpeta resultados_rodante_134 --escenario S08A
```

Resultado: se crea `rodante_S08A_auditoria_independiente.json`. Si hay errores, el auditor termina con código distinto de cero y detalla los conflictos.

Para cinco ventanas, repetir el primer comando con `--ventanas 5` y otra carpeta de salida, por ejemplo `resultados_rodante_134_v5`.

## Archivos generados

- `rodante_S08A_resumen.json`: resultados y cobertura por ventana; **no es certificación anual**.
- `rodante_S08A_decisiones.csv`: planes por ventana, incluida la parte provisional que puede cambiar después.
- `rodante_S08A_compromisos.csv`: operaciones nuevas comprometidas (cada identificador una vez).
- `rodante_S08A_compromisos_jornadas.csv`: jornadas y horas de reloj modeladas para compromisos.
- `rodante_S08A_reservas_externas_por_ventana.csv`: instantáneas de reservas externas; contiene repeticiones entre ventanas deliberadamente.
- `rodante_S08A_arrastres_entre_turnos.csv`: transferencias de compromisos entre ventanas; un compromiso puede figurar en más de una apertura de turno.
- `rodante_S08A_auditoria_independiente.json`: auditoría de los CSV sin solver (se genera en el segundo comando).

## Resultados de desarrollo reproducidos

Con Python y SciPy HiGHS en ambiente de pruebas:

| Escenario | Ventanas | Pedidos relevantes | Compromisos distintos | Reservas externas únicas observadas | Filas de arrastre | Errores del auditor independiente |
|---|---:|---:|---:|---:|---:|---:|
| S08A | 3 | 4 | 17 | 52 | 7 | 0 |
| S08A | 5 | 4 | 23 | 56 | 11 | 0 |
| S13A | 3 | 2 | 2 | 54 | 1 | 0 |

- **45 pruebas unitarias aprobadas**, incluidas 9 pruebas nuevas sobre reservas, solapamientos, inmutabilidad y traspasos.
- **40/40 microinstancias** para cada una de las tres funciones objetivo (f1, f1b, f2), cero violaciones.
- El caso S08A de tres ventanas mantiene la penalidad *modelada* de S/ 3.612,81 en la primera ventana, sin cambiar respecto de la 1.3.3; no debe interpretarse como ahorro económico real.

## Pendientes científicos prioritarios

1. Crear una reprogramación global coordinada de todas las órdenes activas, no congelar indefinidamente FIFO externo.
2. Ejecutar casos de fallas y nuevas llegadas sucesivas con reoptimización de pedidos variables (además de los seleccionados al principio).
3. Validar habilidades, pausas y feriados con responsables de SAGAPI o evaluar sensibilidad de esos supuestos.
4. Repetir la batería anual, Monte Carlo y Pareto **solamente después** de comprobar la factibilidad del nuevo algoritmo en una base compartida con todos los recursos.
