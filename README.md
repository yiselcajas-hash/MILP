# SAGAPI MILP

Programación y reprogramación reactiva multiobjetivo (MILP, HiGHS) para la planta metalmecánica SAGAPI.

- **Proyecto entregado (v1.4.0):** `Optimizacion_MILP_SAGAPI.py`, `sagapi/`, `tests/`, `herramientas/`, `EVIDENCIA_FINAL/`, `LEEME_ENTREGA_FINAL.md` y la base `Base_Datos_SAGAPI_25_TRABAJADORES_SIMULADOS_v1_2.xlsx` (se conserva sin cambios).
- **Auditoría integral y base de datos v2.0:** ver [`entrega_v2_0/LEEME_ENTREGA_V2_0.md`](entrega_v2_0/LEEME_ENTREGA_V2_0.md).

```bash
python -m pip install -r requirements.txt
python Optimizacion_MILP_SAGAPI.py validar --excel entrega_v2_0/base_datos/SAGAPI_BD_MODELO_v2_0.xlsx
python -m unittest discover -s tests -p "test_*.py"
python herramientas/verificar_bd_v2.py --pruebas-python
```
