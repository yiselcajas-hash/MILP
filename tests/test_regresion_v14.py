"""Regresión: con la configuración de v1.4 (sin R12, penalidad fija primero) v2.0 reproduce sus resultados.

Valores de referencia: corridas de v1.4 sobre la base v2.0 (Evidencias_Validacion/etapa1_auditoria/verificacion).
"""
import pytest

from sagapi import estado, optimizacion as opt, reglas, simulacion as sim
from sagapi.indicadores import kpis_programa, kpis_subproblema


def test_caso_S06A(datos, inst_v14):
    inst = inst_v14
    base, _ = reglas.fifo_plan(inst, list(range(len(inst.jobs))))
    wu = estado.ventanas_unidades(inst, [(m, a, b) for (_, m, a, b) in sim.ventanas_de(datos, ["F06"])])
    tb = wu[0][1]
    jobs = [j for j in range(len(inst.jobs)) if inst.jobs[j]["r"] <= tb + 1e-6 and base[inst.job_ops[j][-1]][2] > tb + 1e-6]
    sub = estado.particionar(datos, inst, base, tb, jobs, wu, "A")
    assert len(jobs) == 8 and len(sub.free) == 73
    k = kpis_subproblema(sub, reglas.convencional(sub))
    assert (k["atrasados"], round(k["penalidad_estimada"])) == (7, 14834)
    assert k["tardanza_ponderada"] == pytest.approx(205.55, abs=0.01)
    k = kpis_subproblema(sub, reglas.edd(sub))
    assert (k["atrasados"], round(k["penalidad_estimada"])) == (6, 15299)
    r = opt.optimizar(sub, regla_objetivo="PENALIDAD_FIJA", tl=60)
    assert r["estado_global"] == "OPTIMO"
    k = kpis_subproblema(sub, r["sol"])
    assert k["atrasados"] == 4
    assert k["penalidad_estimada"] == pytest.approx(9066.34, abs=0.01)
    assert k["tardanza_ponderada"] == pytest.approx(249.18, abs=0.01)


@pytest.mark.parametrize("plan,reac,esperado", [
    ("FIFO", "CONV", (73, 127293.848, 1035.059)),
    ("EDD", "EDD", (27, 83231.192, 717.011)),
])
def test_anio_S00_reglas(datos, inst_v14, plan, reac, esperado):
    res = sim.simular(datos, inst_v14, plan, reac, [])
    k = kpis_programa(inst_v14, res.programa, datos)
    assert k["atrasados"] == esperado[0]
    assert k["penalidad_estimada"] == pytest.approx(esperado[1], abs=0.01)
    assert k["tardanza_ponderada"] == pytest.approx(esperado[2], abs=0.01)


@pytest.mark.lento
def test_anio_S20A_FIFO_CONV(datos, inst_v14):
    evs = [f"F{k:02d}" for k in range(1, 13)]
    res = sim.simular(datos, inst_v14, "FIFO", "CONV", evs)
    k = kpis_programa(inst_v14, res.programa, datos)
    assert (k["atrasados"], round(k["penalidad_estimada"])) == (74, 130474)
