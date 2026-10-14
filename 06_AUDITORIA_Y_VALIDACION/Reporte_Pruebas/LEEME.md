# Reporte de pruebas — SAGAPI v2.0

| Archivo | Contenido |
|---|---|
| `pytest_salida_zip_python312.txt`, `pytest_resultados_zip_python312.xml` | **Ejecución de referencia de la entrega.** Batería completa ejecutada desde el ZIP descomprimido, en un entorno virtual limpio de Python 3.12 con las versiones de `requirements.txt`. Incluye además `Programa_principal.py validar` |
| `pytest_salida_python313.txt`, `pytest_resultados_python313.xml` | Ejecución en el repositorio de desarrollo (Python 3.13) |
| `enumeracion_exhaustiva.csv` | Validación ampliada: 438 microinstancias comparadas con la enumeración exhaustiva (`herramientas/reporte_enumeracion.py 200`) |

## Resultado

* **118 pruebas aprobadas, 4 omitidas, 0 fallidas** en ambas ejecuciones.
* Las 4 omisiones son por diseño: microinstancias de programación inicial con más de 7 operaciones libres, cuya enumeración exhaustiva sería demasiado costosa. Se registran como `SKIPPED` con su motivo.
* Enumeración ampliada: **438/438** coincidencias entre el MILP y el óptimo lexicográfico enumerado. Cobertura: 317 casos con operaciones no interrumpibles (R12), 170 con ventanas futuras (R6), 66 con comparación de la estabilidad (P3) y recurso de 2 unidades.

## Pruebas que no pudieron ejecutarse

* **Python 3.11:** las versiones fijadas no se pueden instalar porque numpy 2.5.3 no publica paquetes para 3.11 (`pip` informa «No matching distribution found»). Por eso el programa se declara compatible con Python 3.12 y 3.13. No se rebajaron las versiones para forzar la compatibilidad.
* **Validación en planta:** no es una prueba automatizable. Requiere datos reales (ver `07_DOCUMENTACION/Limitaciones_y_Supuestos.md`).

## Cómo repetirlas

```bash
pip install -r 01_CODIGO_PYTHON/requirements.txt
python -m pytest tests -v
python 01_CODIGO_PYTHON/herramientas/reporte_enumeracion.py 200
```
