# SAGAPI v2.0 — Programación y reprogramación MILP de un taller metalmecánico

Sistema de programación de la producción con **MILP (HiGHS vía SciPy)**:

* averías y reprogramación reactiva en un **horizonte rodante** por eventos;
* asignación verificada de los **25 trabajadores** (turno único de 8 h);
* comparación justa con **FIFO** (práctica actual) y **EDD**;
* KPI, gráficos y pruebas automáticas.

> **Naturaleza de los datos.** Los pedidos, las averías y las habilidades del personal son **SIMULADOS**; los tiempos de ruta son **ESTIMADOS**. Los resultados muestran el comportamiento de los métodos bajo esos datos: **no son resultados históricos ni ahorros verificados de la empresa**. Un programa factible para el modelo no está validado en planta. Ver `07_DOCUMENTACION/Limitaciones_y_Supuestos.md`.

## Inicio rápido

```bash
pip install -r 01_CODIGO_PYTHON/requirements.txt
cd 01_CODIGO_PYTHON
python Programa_principal.py validar                                            # controles de calidad de la base
python Programa_principal.py programar --plan MILP --reaccion MILP --escenario S20A
python Programa_principal.py caso --escenario S06A                               # CONV vs EDD vs MILP ante una avería
python Programa_principal.py todo                                                # experimentos E0–E5 + gráficos + libro
cd .. && python -m pytest tests -q                                               # pruebas
```

## Contenido

| Carpeta | Contenido |
|---|---|
| `01_CODIGO_PYTHON/` | `Programa_principal.py`, paquete `sagapi/` (datos, instancia, modelo, solver, optimización, simulación, reglas, personal, verificación, indicadores, reportes, CLI), `herramientas/`, `requirements.txt` |
| `02_BASE_DATOS/` | `SAGAPI_BASE_CORREGIDA_FINAL.xlsx`, `Diccionario_de_datos.xlsx`, versiones anteriores |
| `03_MODELO_MATEMATICO/` | `Formulacion_MILP_Actualizada.pdf` |
| `04_RESULTADOS/` | `Resultados_MILP/`, `Comparacion_MILP_FIFO/`, `Indicadores_KPI/` (con `Informe_KPI.pdf`), `Escenarios/`, `Resultados_SAGAPI_v2.xlsx`, `Informe_Resultados_Computacionales.pdf`, registro de ejecución |
| `05_GRAFICOS/` | `Diagramas_Gantt/`, `Utilizacion_Recursos/`, `Comparaciones/`, `Analisis_Sensibilidad/` |
| `06_AUDITORIA_Y_VALIDACION/` | `Informe_Correcciones.pdf`, `Matriz_Errores.xlsx`, `Reporte_Pruebas/`, `Evidencias_Validacion/` (incluye la versión inicial v1.4.0 y la auditoría de la etapa 1) |
| `07_DOCUMENTACION/` | `Manual_Ejecucion.pdf`, `Informe_Tecnico_Final.pdf`, `Registro_Cambios.md`, `Limitaciones_y_Supuestos.md`, `fuentes/` (Markdown de los PDF) |
| `tests/` | pruebas pytest: enumeración exhaustiva, restricciones, datos, personal, horizonte rodante, regresión v1.4, estados del solucionador, CLI |

Detalles de uso en `07_DOCUMENTACION/Manual_Ejecucion.pdf`; formulación en `03_MODELO_MATEMATICO/`; resultados y su lectura en `07_DOCUMENTACION/Informe_Tecnico_Final.pdf`.

## Versiones anteriores

La versión inicial v1.4.0 (código, pruebas y Excel v1.2) se conserva sin cambios. En el ZIP está en `06_AUDITORIA_Y_VALIDACION/Evidencias_Validacion/version_inicial_v1_4_0/`; en el repositorio, en `historial/v1_4_0_original/`. Los entregables de la auditoría de la etapa 1 (base v2.0 y matriz de 84 errores del Excel) están en `Evidencias_Validacion/etapa1_auditoria/` (repositorio: `historial/etapa1_auditoria_v2_0/`).
