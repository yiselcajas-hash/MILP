"""El MILP reproduce el óptimo lexicográfico obtenido por enumeración exhaustiva (P1, P2 y P3).

Cubre: dos jerarquías de objetivo, recurso con 2 unidades idénticas, operaciones no interrumpibles (R12),
averías actuales y simultáneas, ventanas futuras (R6), políticas de recuperación A y B y programación inicial.
Una diferencia indica un error de formulación (p. ej. un big-M que recorta soluciones factibles).
"""
import pytest

from micro import escenario, inicial, optimo_enumerado
from sagapi import optimizacion as opt
from sagapi.indicadores import kpis_subproblema
from sagapi.solver import Estado
from sagapi.verificacion import verificar_subproblema

SEMILLAS = list(range(40))


def _comparar(sub, regla):
    e1, e2, e3, n = optimo_enumerado(sub, regla)
    r = opt.optimizar(sub, regla_objetivo=regla, tl=60)
    assert r["estado_global"] == Estado.OPTIMO, r["pasos"]
    assert not verificar_subproblema(sub, r["sol"])
    k = kpis_subproblema(sub, r["sol"])
    tp, pen = k["tardanza_ponderada"], k["penalidad_estimada"]
    m1, m2 = (tp, pen) if regla == "TARDANZA_PONDERADA" else (pen, tp)
    assert m1 == pytest.approx(e1, abs=1e-3), (regla, "P1", m1, e1)
    assert m2 == pytest.approx(e2, abs=1e-3 * max(1, e2)), (regla, "P2", m2, e2)
    if e3 is not None:
        assert k["estabilidad_f3"] == pytest.approx(e3, abs=2e-3 * max(1, e3)), ("P3", k["estabilidad_f3"], e3)
    return n


@pytest.mark.parametrize("seed", SEMILLAS)
def test_reactivo_tardanza_ponderada(seed):
    sub = escenario(seed)
    if not sub.free:
        pytest.skip("la avería no afecta operaciones pendientes")
    _comparar(sub, "TARDANZA_PONDERADA")


@pytest.mark.parametrize("seed", SEMILLAS[:20])
def test_reactivo_penalidad_fija(seed):
    sub = escenario(seed)
    if not sub.free:
        pytest.skip("la avería no afecta operaciones pendientes")
    _comparar(sub, "PENALIDAD_FIJA")


@pytest.mark.parametrize("seed", range(100, 110))
def test_programacion_inicial_con_ventana_futura(seed):
    sub = inicial(seed)
    if len(sub.free) > 7:
        pytest.skip("microinstancia demasiado grande para enumerar")
    _comparar(sub, "TARDANZA_PONDERADA")
