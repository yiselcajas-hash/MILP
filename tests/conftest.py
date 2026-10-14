"""Configuración común de las pruebas: añade 01_CODIGO_PYTHON al camino de importación y comparte la base."""
import os
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
CODIGO = RAIZ / "01_CODIGO_PYTHON"
sys.path.insert(0, str(CODIGO))
BASE = RAIZ / "02_BASE_DATOS" / "SAGAPI_BASE_CORREGIDA_FINAL.xlsx"
HIST = RAIZ / "historial" / "etapa1_auditoria_v2_0"


@pytest.fixture(scope="session")
def base():
    return BASE


@pytest.fixture(scope="session")
def datos():
    from sagapi.datos import cargar_base
    d, inf = cargar_base(BASE)
    return d


@pytest.fixture(scope="session")
def inst(datos):
    from sagapi import instancia
    return instancia.construir(datos)


@pytest.fixture(scope="session")
def inst_v14(datos):
    """Instancia con la configuración de v1.4 (sin continuidad R12) para pruebas de regresión."""
    from sagapi import instancia
    return instancia.construir(datos, regla_continuidad="NINGUNA")


def pytest_configure(config):
    config.addinivalue_line("markers", "lento: prueba de más de ~30 s (año completo con MILP)")
    os.environ.setdefault("PYTHONHASHSEED", "0")
