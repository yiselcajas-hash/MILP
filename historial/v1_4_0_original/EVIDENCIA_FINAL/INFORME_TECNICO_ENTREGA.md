# SAGAPI — Informe técnico final del prototipo MILP (v1.4.0)

**Estado:** ENTREGA ACADÉMICA DEL PROTOTIPO; **no** certifica factibilidad anual ni despliegue real.

## Alcance y datos

- 96 pedidos y 1.152 operaciones de base modelada, cuatro familias y 15 máquinas.
- Empresa: 25 trabajadores de producción y un turno de 8 h (declaración real).
- Matriz de habilidades, pedidos, penalidades y fallas: contienen supuestos/simulaciones.
- El MILP asigna trabajador–operación y reprograma subproblemas mediante ventanas de 8 h.
- Las reservas FIFO externas solo quedan protegidas dentro del horizonte definido (120 h).
- No se modificó el Excel original ni se asumió que SAGAPI trabaja en feriados.

## Resultados reproducidos

| Escenario | Ventanas | Pedidos piloto | Operaciones comprometidas / 1.152 | Reservas externas únicas | Errores de auditoría | Incidencias del ensamblaje FIFO hipotético |
|---|---:|---:|---:|---:|---:|---:|
| S08A | 5 | 4 | 23 / 1152 (1.997%) | 56 | 0 | 0 |
| S13A | 3 | 2 | 2 / 1152 (0.174%) | 54 | 0 | 1 |

**Interpretación:** La auditoría independiente no encontró errores en los compromisos y reservas exportados. El diagnóstico adicional inserta los compromisos en un FIFO anual **hipotético** y busca choques: no es un plan anual optimizado. Un resultado con cero choques tampoco certifica la disponibilidad laboral anual.

## Limitaciones que deben declararse

1. **Cobertura global anual NO VALIDADA.** No se reoptimizaron simultáneamente los 96 pedidos.
2. Las habilidades de los 25 trabajadores no han sido comprobadas con SAGAPI.
3. No se dispone de certificación del trabajo en feriados ni de tareas indirectas.
4. Penalidades y ahorros son resultados de supuestos modelados, **no beneficios económicos realizados**.
5. Diferentes ventanas tienen distintos conjuntos pendientes: sus penalidades P1 no son ahorros acumulativos.
6. Los horarios FIFO congelados y la fusión global son escenarios de referencia, no órdenes de producción autorizadas.

## Declaración académica sugerida

> Se desarrolló y verificó computacionalmente un prototipo MILP predictivo-reactivo con asignación integrada de operarios simulados y reprogramación mediante horizonte rodante. Los subproblemas evaluados alcanzaron soluciones certificadas por el solucionador y superaron auditorías independientes de compromisos, jornadas y reservas externas. Los resultados no constituyen una validación operativa anual de toda la planta y requieren verificación de competencias del personal y calendario productivo.

## Reproducibilidad

- Comando único: `.venv\Scripts\python.exe -X utf8 herramientas\generar_entrega_final.py --tl 60`
- Resultados individuales: `RODANTE_S08A/` y `RODANTE_S13A/`.
- Registros detallados de ejecución: `logs/`.
- Diagnóstico global y sus incidencias: `rodante_*_diagnostico_global_referencial.json` y `*_incidencias_globales.csv`.
- Resumen de verificación: `RESUMEN_COMPARATIVO.csv`.

## Criterio de aceptación

**APROBADO:** Pruebas unitarias, enumeración matemática, ventanas piloto y auditoría independiente.
**PENDIENTE:** Cobertura global de 96 pedidos, habilidades reales y calendario feriado.
