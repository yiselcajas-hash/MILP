# SAGAPI MILP 1.2.1-beta — Auditoría independiente de operarios

## Estado y alcance

Esta versión extiende **SAGAPI 1.2.0-beta**, pero **NO reemplaza la reserva conservadora R11 por una asignación laboral integrada en el MILP**. La novedad es una **auditoría explícita, independiente y trazable de asignaciones** para los programas anuales: se identifica qué perfil simulado atiende cada operación en cada tramo de jornada.

**Confirmados por el usuario:** 25 trabajadores reales en producción; 1 turno de 8 horas; rotación entre áreas de producción según carga. **No confirmados:** habilidades individuales, pausas individuales adicionales, ausencias, exacto número de operarios por actividad. Los identificadores OP-01 a OP-25 y sus competencias en `06B_HABILIDADES` **son simulados**. Las órdenes y penalidades también incluyen supuestos de simulación.

## Archivos y verificación

- Nuevo `sagapi/auditoria_personal.py`: asignación bipartita por intervalo, tratando de conservar al mismo trabajador durante una operación; asegura un operario por operación activa y que ningún perfil atienda dos operaciones al mismo tiempo; verifica competencias, máquina y total de horas de cada operación.
- Nuevo comando `auditar-personal`: evalúa dos políticas anuales en S20A o S00 y exporta CSV con detalle y resumen.
- Nuevo `tests/test_auditoria_personal.py`: casos de cobertura simultánea, descanso, escasez de personal y máquina sobreocupada.
- La auditoría divide intervalos en el refrigerio y el final de cada jornada según el calendario existente. No asume trabajo continuo durante esos descansos.
- El modelo matemático R11 original se conserva. Por tanto, **no debe afirmarse que este paquete contiene una formulación de asignación dinámica de operarios dentro del MILP**; eso requiere una siguiente fase y pruebas de escalabilidad.

## Preparación en Windows (nueva carpeta)

Abra CMD en esta carpeta:

```cmd
py -3.11 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe Optimizacion_MILP_SAGAPI.py validar
.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" -v
.venv\Scripts\python.exe -m tests.test_enumeracion 40
```

## Comando nuevo para la auditoría anual

```cmd
.venv\Scripts\python.exe Optimizacion_MILP_SAGAPI.py auditar-personal --escenario S20A --tl 60 --salida auditoria_v121
```

El comando **vuelve a calcular** FIFO+CONV y MILP+MILP con las 12 fallas del escenario anual; puede tardar. Crea dos archivos en `auditoria_v121`:

1. `auditoria_personal_S20A_resumen.csv`: operaciones cubiertas, trabajadores del escenario utilizados, horas de conflicto, descansos implícitos en el calendario, relevos y horas-hombre simuladas.
2. `auditoria_personal_S20A_detalle.csv`: escenario, combinación, pedido, familia, operación, máquina, perfil de operario, inicios y finales en horas productivas y reloj, y la advertencia de habilidades simuladas. Varias filas por operación si atraviesa descansos u otros cortes.

Para el escenario **sin fallas** cambiar `S20A` por `S00`.

### Criterios de aceptación

- `operaciones_programadas == operaciones_con_cobertura == 1152`.
- `conflictos_h == 0` y `operaciones_sin_cobertura == 0`.
- `horas_hombre_asignadas` coincide con `horas_productivas_de_operaciones`, con pequeñas tolerancias de redondeo.
- Todo perfil es compatible **con la matriz simulada**, NO con habilidades realmente certificadas.

## Pruebas de desarrollo

- 13/13 pruebas unitarias, incluidas las 4 nuevas de auditoría.
- Escenario S20A con `--tl 5` ejecutado en entorno de desarrollo: 1152/1152 operaciones cubiertas para FIFO+CONV y MILP+MILP, sin conflictos bajo los perfiles simulados. El límite de 5 segundos es **solo una prueba de ejecución**, no la corrida definitiva para resultados del paper.
- La siguiente versión debería integrar la asignación por operación a la optimización MILP (variable trabajador–operación, habilidad, exclusión de solapes), agregar auditoría global del horizonte rodante y analizar tiempos computacionales. Requiere datos adicionales para sostener factibilidad real.

**Nunca eliminar ni reemplazar** la carpeta SAGAPI MILP 1.1.0 ni los resultados de 1.2.0-beta. Guardar toda corrida en carpetas independientes.
