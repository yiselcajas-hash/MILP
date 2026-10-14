"""Capa de datos: esquema declarado, lectura estricta, controles de calidad y modelo de datos."""
from .carga import Datos, Maquina, cargar_base, recalcular_pesos  # noqa: F401
from .problemas import ErrorDatos, InformeCalidad, Problema  # noqa: F401
