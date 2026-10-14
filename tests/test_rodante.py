"""Horizonte rodante: estado entre periodos, decisiones congeladas, sin producción duplicada, KPI del sistema."""
import pytest

from sagapi import estado, indicadores as K, reglas, simulacion as sim
from sagapi.verificacion import verificar_programa


def _ventanas(datos, inst, evs):
    return estado.ventanas_unidades(inst, [(m, a, b) for (_, m, a, b) in sim.ventanas_de(datos, evs)])


def test_particion_clasifica_operaciones(datos, inst):
    plan, _ = reglas.fifo_plan(inst, list(range(len(inst.jobs))))
    wu = _ventanas(datos, inst, ["F06"])
    t0 = wu[0][1]
    jobs = [j for j in range(len(inst.jobs)) if inst.jobs[j]["r"] <= t0 and plan[inst.job_ops[j][-1]][2] > t0]
    for H in (0.0, 8.0):
        sub = estado.particionar(datos, inst, plan, t0, jobs, wu, "A", congelar_h=H)
        for o in sub.free:
            m, S, C = plan[o]
            assert S >= t0 - 1e-9 or o in sub.interrupted, "nada iniciado se reprograma salvo lo interrumpido"
        for o, (m, S, C) in sub.fixed.items():
            assert (m, S, C) == plan[o]
        assert len(sub.interrupted) == 1
        o = sub.interrupted[0]
        assert plan[o][0] == "PLE-01" and plan[o][1] < t0 < plan[o][2]
        if H > 0:
            assert sub.congeladas, "con H = 8 h hay operaciones congeladas"
            for o in sub.congeladas:
                assert plan[o][1] < t0 + H


def test_politica_A_conserva_y_B_reinicia(datos, inst):
    plan, _ = reglas.fifo_plan(inst, list(range(len(inst.jobs))))
    wu = _ventanas(datos, inst, ["F06"])
    t0 = wu[0][1]
    jobs = [j for j in range(len(inst.jobs)) if inst.jobs[j]["r"] <= t0 and plan[inst.job_ops[j][-1]][2] > t0]
    sA = estado.particionar(datos, inst, plan, t0, jobs, wu, "A")
    sB = estado.particionar(datos, inst, plan, t0, jobs, wu, "B")
    o = sA.interrupted[0]
    m = plan[o][0]
    assert sA.pR[(o, m)] < inst.p[(o, m)]
    assert sB.pR[(o, m)] == pytest.approx(inst.p[(o, m)])


@pytest.mark.parametrize("plan,reac", [("FIFO", "CONV"), ("EDD", "EDD"), ("FIFO", "MILP")])
def test_anio_con_averias_sin_duplicados(datos, inst, plan, reac):
    evs = ["F01", "F02", "F14", "F06"]
    res = sim.simular(datos, inst, plan, reac, evs, politica="A", tl=60)
    assert res.verificacion["total"] == 0, res.detalle_violaciones
    assert set(res.programa) == set(range(len(inst.ops))), "cada operación exactamente una vez"
    interrumpidas = sum(f["interrumpidas"] for f in res.registro if f["tipo"] == "FALLA")
    assert len(res.parciales) == interrumpidas
    for (o, m, S, C) in res.parciales:
        assert res.programa[o][1] >= C - 1e-9, "el resto se procesa después del tramo interrumpido"
    # el verificador es independiente: repetirlo desde afuera da el mismo resultado
    r = verificar_programa(inst, res.programa, res.ventanas, parciales=res.parciales, duraciones=res.duraciones)
    assert sum(len(v) for v in r.values()) == 0


def test_horizonte_congelado_se_respeta(datos, inst):
    res0 = sim.simular(datos, inst, "FIFO", "MILP", ["F06"], congelar_h=0.0, tl=60)
    res8 = sim.simular(datos, inst, "FIFO", "MILP", ["F06"], congelar_h=8.0, tl=60)
    assert res0.verificacion["total"] == 0 and res8.verificacion["total"] == 0
    f8 = [f for f in res8.registro if f["tipo"] == "FALLA"][0]
    f0 = [f for f in res0.registro if f["tipo"] == "FALLA"][0]
    assert f8["congeladas"] > 0 and f0["congeladas"] == 0
    assert f8["ops_libres"] < f0["ops_libres"]


def test_mantenimiento_planificado_es_anunciado(datos, inst):
    res = sim.simular(datos, inst, "FIFO", "CONV", ["F21"])
    assert not any(f["tipo"] == "FALLA" for f in res.registro)
    assert res.ventanas and res.verificacion["total"] == 0


def test_kpis_coherentes(datos, inst):
    res = sim.simular(datos, inst, "EDD", "EDD", [])
    k = K.kpis_programa(inst, res.programa, datos, registro=res.registro)
    tab = K.tabla_pedidos(inst, res.programa)
    assert k["pedidos"] == len(tab) == 96 and k["completados"] == 96
    assert k["atrasados"] == sum(r["atrasado"] for r in tab)
    assert k["otd_pct"] == pytest.approx(100 * (1 - k["atrasados"] / 96))
    assert k["tardanza_total_h"] == pytest.approx(sum(r["tardanza_h"] for r in tab))
    assert k["penalidad_estimada"] == pytest.approx(sum(r["penalidad"] for r in tab))
    assert k["horas_reproceso"] == pytest.approx(0.0, abs=1e-6)
    lb = K.cota_inferior_tardanza(inst)
    for r, j in zip(tab, range(len(inst.jobs))):
        assert r["tardanza_h"] >= lb[j] - 1e-6, "ningún programa puede bajar de la tardanza inevitable"
