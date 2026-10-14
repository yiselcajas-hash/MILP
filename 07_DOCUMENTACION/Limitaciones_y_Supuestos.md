# Limitaciones y supuestos — SAGAPI v2.0

Este documento acompaña a todos los resultados. Un programa **matemáticamente factible y verificado** cumple las restricciones del modelo; **no** está validado en planta.

## 1. Naturaleza de los datos

| Dato | Naturaleza | Consecuencia |
|---|---|---|
| 96 pedidos de 2025 (cantidades, fechas de recepción, liberación y compromiso) | SIMULADO (reparte las unidades vendidas reales por familia) | Los KPI no son historial de SAGAPI. Las diferencias entre métodos muestran el comportamiento del método, **no ahorros de la empresa** |
| Averías F01–F20 y mantenimiento F21 | SIMULADO | El impacto de las averías es ilustrativo; no hay historial de paradas (PV-07) |
| Matriz de habilidades de los 25 trabajadores | SIMULADO | El certificado de cobertura y la asignación dependen de ella; se reemplaza con `16_REG_HABILIDADES` (Manual §7) |
| Tiempos de preparación y por unidad (406 filas de ruta) | ESTIMADO (215 heredados sin cronometraje, 191 hipótesis técnicas) | Todas las duraciones $p_{om}$ son aproximadas, incluida la carga de la plegadora |
| Factor de tiempo en recursos alternativos | ESTIMADO | Afecta el beneficio de reasignar (sensibilidad E4) |
| Penalidad por familia (fracción del valor) y precio medio por familia | ESTIMADO | Los montos en S/ son órdenes de magnitud, no costos contractuales |
| Costos horarios, tarifa eléctrica, potencias | ESTIMADO | Los costos y la energía son referenciales |
| 25 trabajadores, 1 turno, 8 h netas por día | REAL (declarado) | Parámetros de capacidad laboral |
| Jornada 08:00–12:00 y 13:00–17:00 | ESTIMADO (horario no confirmado) | Define el eje de tiempo y los tramos de R12 |
| Feriados (`aplicar_feriados = 0`) | CONFIGURACIÓN pendiente de confirmar | Sensibilidad E4: con feriados, el desempeño empeora en todos los métodos |

## 2. Supuestos del modelo

1. **Determinismo entre eventos:** el programa se ejecuta tal como se planificó hasta el evento siguiente.
2. **Avería con duración conocida al ocurrir**; los mantenimientos planificados se conocen desde el inicio del año.
3. **Precedencia lineal sin lotes de transferencia:** una operación inicia cuando termina todo el lote anterior. Es conservador; requiere datos de flujo real (C-06).
4. **Una persona por operación** (`trabajadores_requeridos = 1`, supuesto heredado de v1.4). El código admite cualquier valor $c_o$.
5. **Operaciones interrumpibles** en refrigerio y cierre, salvo el curado (POR_LOTE), que no puede cruzar el tramo continuo (R12, `lote_no_cruza = TRAMO`).
6. **Recuperación tras avería** según `25_RECUPERACION_SIM` (política A conserva piezas; B reinicia el lote).
7. **Sin materiales en el modelo:** no hay datos confiables de inventario ni de plazos de compra. No se agregó ninguna restricción de materiales, para no inventar datos.
8. **Sin setups dependientes de la secuencia:** la preparación forma parte del tiempo de cada lote (no hay matriz de cambios).
9. **Capacidad de áreas y puestos manuales = 1** (cantidad declarada en `05_RECURSOS`); la capacidad simultánea real está pendiente (E-033).

## 3. Límites del método

* **Horizonte rodante:** el óptimo se demuestra **por evento** (subproblema). La secuencia de decisiones óptimas no garantiza el óptimo anual (miopía inherente a la reprogramación por eventos).
* **Certificado laboral suficiente, no necesario.** Sin certificado, el tratamiento del personal es heurístico (reparación) y se rotula así.
* **Jerarquía de objetivos:** minimizar la tardanza ponderada puede atrasar **más pedidos** que EDD (resultado desfavorable informado en E1). Con `PENALIDAD_FIJA` ocurre lo contrario. La elección es de la empresa.
* **Tiempos de cómputo** medidos en un solo equipo (contenedor Linux, un hilo de HiGHS). Varían con el hardware.
* **Microinstancias de enumeración:** demuestran la corrección de la formulación en casos pequeños, no el desempeño en instancias grandes.
* **Escenarios operativos** (E3) derivados por transformación de los pedidos simulados (factor de cantidad y de plazo). No son pronósticos de demanda.

## 4. Lo que falta para validar en planta (prioridad)

PV-01 tiempos cronometrados (empezando por la plegadora) · PV-02 matriz real de habilidades y personas por operación · PV-03 pedidos reales con fechas y precios · PV-04 distribución real del tiempo del personal (5 742 h de proceso frente a 52 200 h disponibles) · PV-07 historial de paradas · confirmación de jornada, feriados y penalidades contractuales. Lista completa en `06_AUDITORIA_Y_VALIDACION/Matriz_Errores.xlsx` (filas PV).
