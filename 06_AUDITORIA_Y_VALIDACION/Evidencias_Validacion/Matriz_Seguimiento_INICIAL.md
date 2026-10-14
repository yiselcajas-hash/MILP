# Matriz de seguimiento — estado INICIAL (antes de modificar el código)

**Fecha:** 2026-10-14. Esta es una fotografía del estado de la etapa 1 (commit `5691d6b`, etiqueta `v2.0-etapa1-auditoria`), tomada antes de tocar el código.

**Evidencia revisada:**

| Elemento | Detalle |
|---|---|
| Informes E1, E4, E5, E6, E7 | Carpeta `historial/etapa1_auditoria_v2_0/informes` |
| Matriz de 84 errores del Excel | Archivo de auditoría |
| Bases v2.0 (hash SHA-256) | OPERATIVA `0bf5ec02…`, SIMULACION `09a9cfa7…`, MODELO `0e2a2411…` |
| Excel v1.2 original | `8f75befc…` (sin cambios) |
| Verificación estática repetida hoy (`verificar_bd_v2.py`) | 11 PASA, 1 ALERTA (igual que en la etapa 1) |
| Recursos productivos | 15 (13 principales + PER-02 + SOL-02); 17 filas en total en `05_RECURSOS` (SAL-PIN sin rutas y PIN-EXT externo) |
| Pedidos y operaciones | 96 pedidos, 1 152 operaciones |

**Estados posibles:** Pendiente · Parcialmente corregido · Corregido y validado · No verificable (requiere datos de la empresa).

| ID | Problema identificado | Archivo afectado | Prioridad | Estado | Acción requerida |
|---|---|---|---|---|---|
| C-01 | R11 no restringe la programación (sin variables S o x) | `sagapi/modelo.py` | P0 | Pendiente | Sacarla del MILP; certificado de cobertura + asignación explícita verificada |
| C-04 | Curado (POR_LOTE) partido entre jornadas: físicamente imposible | `modelo.py`, `reglas.py`, `verificacion.py` | P0 | Pendiente | Restricción de lote no partible en el MILP, en las reglas y en el verificador |
| C-16 | Lectura silenciosa de fórmulas (`data_only=False`) | `sagapi/datos.py` | P0 | Pendiente | Lector estricto con error ante fórmulas en columnas de entrada |
| C-17 | Esquema implícito y frágil | `sagapi/datos.py` | P0 | Pendiente | Esquema declarado + controles de calidad que bloquean |
| C-19 | Los reportes sobrescriben el Excel de entrada | `sagapi/reportes.py` | P0 | Pendiente | Libro de resultados separado |
| C-02 | Personal integrado solo en un piloto (2 % / 0,17 %) | `personal_integrado.py`, `rodante_personal.py` | P1 | Pendiente | Asignación de los 25 trabajadores para todas las operaciones |
| C-03 | Capacidad unitaria de todo recurso | `modelo.py`, `instancia.py`, `verificacion.py` | P1 | Pendiente | Unidades paralelas según `cantidad` |
| C-05 | El objetivo de penalidad fija sacrifica la tardanza | `modelo.py`, `optimizacion.py` | P1 | Pendiente | Jerarquía de objetivos sustentada y configurable |
| C-07 | Big-M de R6 incorrecto si a < p | `modelo.py:113` | P1 | Pendiente | M = UB + p − a |
| C-08 | Miopía de `evento_unico` | `experimentos.py` | P1 | Pendiente | Escenarios evaluados sobre el sistema completo |
| C-11 | Comparador FIFO débil; efectos no separados | `experimentos.py` | P1 | Pendiente | Referencias FIFO y EDD con las mismas restricciones; separar secuenciación y reprogramación |
| C-12 | Selección del piloto por índice | `Optimizacion_MILP_SAGAPI.py` | P1 | Pendiente | El horizonte rodante cubre todos los pedidos activos |
| C-18 | Feriados leídos de dos formas | `datos.py`, `experimentos.py` | P1 | Pendiente | Una sola lectura del calendario |
| C-09 | Horas de liberación y vencimiento fijas en el código | `instancia.py` | P2 | Pendiente | Leerlas de los parámetros |
| C-10 | MILP monolítico inviable (54 000 binarias) | Arquitectura | P2 | Pendiente | Descomposición por eventos (horizonte rodante) documentada y medida |
| C-13 | Wilcoxon sobre escenarios dependientes | `reportes.py` | P2 | Pendiente | Retirar; reportar diferencias por escenario |
| C-15 | La sensibilidad ignora el Excel | `experimentos.py` | P2 | Pendiente | Leer los niveles de la base |
| C-21 | Tres implementaciones del lexicográfico | `optimizacion.py`, `rodante_personal.py`, programa principal | P2 | Pendiente | Unificar |
| C-22 | Programa principal monolítico | Programa principal | P2 | Pendiente | Arquitectura por capas |
| C-23 | Dependencias sin fijar | `requirements.txt` | P2 | Pendiente | Fijar versiones |
| C-24 | Pruebas sin cobertura de riesgos | `tests/` | P2 | Pendiente | Una prueba por restricción, regresión y equivalencia |
| C-25 | Indicadores incompletos | `indicadores.py` | P2 | Pendiente | Módulo de KPI con fórmulas |
| C-06 | Precedencia lineal sin lotes de transferencia | Datos y modelo | P2 | No verificable | Requiere datos de flujo real (PV) |
| C-14 | Monte Carlo circular sobre fallas sintéticas | `experimentos.py` | P3 | No verificable | Requiere historial de paradas (PV-07) |
| C-20 | El generador de datos no reproducía la base | `herramientas/` | P2 | Corregido y validado | Etapa 1: V11 regeneración sin diferencias |
| E-001…E-084 | Errores del Excel (84) | Base v1.2 | P0–P3 | Corregido y validado (57: corregidos, reconstruidos, separados, reubicados, eliminados o reemplazados); No verificable (14, pendientes de datos); Documentado sin corrección posible (13) | Ver `Matriz_Errores.xlsx` |
| PV-01…PV-18 | Datos de la empresa: tiempos, habilidades, pedidos, brecha de horas, feriados, paradas, etc. | — | P0–P3 | No verificable | Solicitar a SAGAPI; plantillas de registro en la base |
