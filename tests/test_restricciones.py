"""Una prueba por restricción: el MILP la respeta y el verificador independiente detecta su violación."""
import math
from types import SimpleNamespace

import numpy as np
import pytest

from sagapi import estado, optimizacion as opt, reglas
from sagapi.calendario import Calendario
from sagapi.instancia import Instancia
from sagapi.modelo.milp import ModeloMILP
from sagapi.verificacion import programa_completo, verificar_programa, verificar_subproblema


def _inst(ops_spec, jobs_spec, unidades, L=4.0):
    """ops_spec: [(job, principal, {unidad: p}, interrumpible)] en orden de ruta por pedido."""
    jobs, ops, job_ops, elig, p = [], [], {}, {}, {}
    for j, (r, d, w, P) in enumerate(jobs_spec):
        jobs.append(dict(idx=j, id=f"J{j}", familia="F", producto="X", q=1, r=r, d=d, w=w, P=P, pdia=10.0, valor=100.0,
                         tope=50.0))
        job_ops[j] = []
    for (j, principal, ps, interr) in ops_spec:
        o = len(ops)
        ops.append(dict(idx=o, job=j, pos=len(job_ops[j]), paso=len(job_ops[j]) + 1, operacion="op", principal=principal,
                        trato="POR_UNIDAD", setup_min=0.0, min_unidad=1.0, lote=1, q=1, crew=1, interrumpible=interr))
        job_ops[j].append(o)
        elig[o] = list(ps)
        for m, v in ps.items():
            p[(o, m)] = v
    datos = SimpleNamespace(recuperacion=[], maquinas={}, masa_chapa={})
    maqs = sorted({u for us in unidades.values() for u in us})
    return Instancia(datos, jobs, ops, job_ops, elig, p, maqs, {}, unidades, L), datos


def _resolver(sub, regla="TARDANZA_PONDERADA"):
    r = opt.optimizar(sub, regla_objetivo=regla, tl=30)
    assert r["estado_global"] == "OPTIMO"
    assert not verificar_subproblema(sub, r["sol"])
    return r["sol"], programa_completo(sub, r["sol"])


def test_R1_R2_asignacion_y_alternativa():
    # A tiene una ventana actual [0, 5): la operación debe ir a la alternativa B (factor 1.5)
    inst, d = _inst([(0, "A", {"A": 2.0, "B": 3.0}, True)], [(0, 4.0, 1, 100)], {"A": ["A"], "B": ["B"]})
    sub = estado.subproblema_inicial(inst)
    sub.mavail["A"] = 5.0
    sol, full = _resolver(sub)
    assert sol[0][0] == "B" and sol[0][1] == pytest.approx(0.0)
    assert verificar_subproblema(sub, {0: ("C", 0.0)})            # unidad no elegible
    assert verificar_subproblema(sub, {0: ("A", 1.0)})            # A aún no disponible


def test_R3_precedencia_y_liberacion():
    inst, d = _inst([(0, "A", {"A": 2.0}, True), (0, "B", {"B": 1.0}, True)], [(1.0, 10.0, 1, 100)],
                    {"A": ["A"], "B": ["B"]})
    sub = estado.subproblema_inicial(inst)
    sol, full = _resolver(sub)
    assert full[0][1] >= 1.0 - 1e-9 and full[1][1] >= full[0][2] - 1e-9
    assert any("R3" in v for v in verificar_subproblema(sub, {0: ("A", 1.0), 1: ("B", 2.5)}))
    assert any("R2" in v or "R3" in v for v in verificar_subproblema(sub, {0: ("A", 0.0), 1: ("B", 3.0)}))


def test_R4_R5_capacidad_unidad_y_dos_unidades():
    # tres operaciones de 2 h en un recurso de 2 unidades: Cmax óptimo = 4 h (no 6 h ni 2 h)
    inst, d = _inst([(j, "R", {"R#1": 2.0, "R#2": 2.0}, True) for j in range(3)], [(0, 0.0, 1, 100)] * 3,
                    {"R": ["R#1", "R#2"]})
    sub = estado.subproblema_inicial(inst)
    sol, full = _resolver(sub)
    assert max(C for (_, _, C) in full.values()) == pytest.approx(4.0)
    malo = {0: ("R#1", 0.0), 1: ("R#1", 1.0), 2: ("R#2", 0.0)}
    assert any("R4-R5" in v for v in verificar_subproblema(sub, malo))


def test_R6_ventana_futura_y_bigM_valido():
    # ventana [1, 3) en A con a_w = 1 < p = 2.5: la operación no puede cruzarla
    inst, d = _inst([(0, "A", {"A": 2.5}, True)], [(0, 1.0, 1, 100)], {"A": ["A"]})
    sub = estado.subproblema_inicial(inst)
    sub.windows = [("A", 1.0, 3.0)]
    sub.all_windows = list(sub.windows)
    sol, full = _resolver(sub)
    assert full[0][1] == pytest.approx(3.0)
    assert any("R6" in v for v in verificar_subproblema(sub, {0: ("A", 0.0)}))
    # validez del big-M: con x = 0 y z = 0, S = UB debe satisfacer toda fila R6 (v1.4 usaba M = UB: inválido si a < p)
    inst2, _ = _inst([(0, "A", {"A": 2.5, "B": 2.5}, True)], [(0, 1.0, 1, 100)], {"A": ["A"], "B": ["B"]})
    sub2 = estado.subproblema_inicial(inst2)
    sub2.windows = [("A", 0.5, 3.0)]
    sub2.all_windows = list(sub2.windows)
    mdl = ModeloMILP(sub2)
    v = np.zeros(mdl.M.nvar)
    v[mdl.S[0]] = mdl.UB
    v[mdl.x[(0, "B")]] = 1.0
    a, b = mdl.bloques["R6"]
    for fila in range(a, b):
        act = sum(c * v[col] for r, col, c in zip(mdl.M.rows, mdl.M.cols, mdl.M.vals) if r == fila)
        assert mdl.M.rlo[fila] - 1e-9 <= act <= mdl.M.rhi[fila] + 1e-9


def test_R12_no_interrumpible_no_cruza_tramo():
    # p = 3 h, liberación en 2 h, tramos de 4 h: no puede iniciar en 2 (cruzaría 4); debe iniciar en 4
    inst, d = _inst([(0, "A", {"A": 3.0}, False)], [(2.0, 20.0, 1, 100)], {"A": ["A"]}, L=4.0)
    sub = estado.subproblema_inicial(inst)
    sol, full = _resolver(sub)
    assert full[0][1] == pytest.approx(4.0)
    assert any("R12" in v for v in verificar_subproblema(sub, {0: ("A", 2.0)}))
    # una operación interrumpible sí puede cruzar el tramo
    inst2, _ = _inst([(0, "A", {"A": 3.0}, True)], [(2.0, 20.0, 1, 100)], {"A": ["A"]}, L=4.0)
    sol2, full2 = _resolver(estado.subproblema_inicial(inst2))
    assert full2[0][1] == pytest.approx(2.0)


def test_R12_operacion_mas_larga_que_el_tramo_es_error_claro():
    with pytest.raises(ValueError, match="excede el tramo"):
        Calendario.ajustar_no_partible(0.0, 5.0, 4.0)


def test_R7_R8_tardanza_y_penalidad():
    # dos pedidos compiten por A; el de mayor peso debe ir primero con tardanza ponderada
    inst, d = _inst([(0, "A", {"A": 2.0}, True), (1, "A", {"A": 2.0}, True)], [(0, 2.0, 1.0, 100), (0, 2.0, 3.0, 50)],
                    {"A": ["A"]})
    sub = estado.subproblema_inicial(inst)
    sol, full = _resolver(sub, "TARDANZA_PONDERADA")
    assert full[1][1] == pytest.approx(0.0)
    sol, full = _resolver(sub, "PENALIDAD_FIJA")   # con penalidad fija conviene atrasar el de menor P
    assert full[0][1] == pytest.approx(0.0)


def test_R9_penalidad_diaria_con_tope():
    inst, d = _inst([(0, "A", {"A": 10.0}, True)], [(0, 2.0, 1.0, 100)], {"A": ["A"]})
    sub = estado.subproblema_inicial(inst)
    r = opt.optimizar(sub, regla_objetivo="PENALIDAD_DIARIA_CON_TOPE", tl=30)
    # T = 8 h; a = 10/8 por h → 10 S/ < tope 50
    assert r["objetivos"]["P1_penalidad_diaria_con_tope"] == pytest.approx(10.0, abs=1e-4)


def test_R10_estabilidad_minimiza_cambios():
    inst, d = _inst([(0, "A", {"A": 1.0, "B": 1.0}, True)], [(0, 10.0, 1, 100)], {"A": ["A"], "B": ["B"]})
    plan = {0: ("A", 5.0, 6.0)}
    sub = estado.particionar(d, inst, plan, 0.0, [0], [])
    r = opt.optimizar(sub, tl=30)
    assert r["sol"][0] == ("A", pytest.approx(5.0))       # sin motivo para moverla, se conserva


def test_verificador_programa_completo_detecta_duplicados_y_faltantes():
    inst, d = _inst([(0, "A", {"A": 1.0}, True), (0, "A", {"A": 1.0}, True)], [(0, 10.0, 1, 100)], {"A": ["A"]})
    r = verificar_programa(inst, {0: ("A", 0.0, 1.0)})
    assert r["completitud"]
    r = verificar_programa(inst, {0: ("A", 0.0, 1.0), 1: ("A", 0.5, 1.5)})
    assert r["capacidad"]
    r = verificar_programa(inst, {0: ("A", 0.0, 1.0), 1: ("A", 1.0, 1.5)})
    assert r["duracion"]
    r = verificar_programa(inst, {0: ("A", 0.0, 1.0), 1: ("A", 2.0, 3.0)}, ventanas=[("A", 2.5, 4.0)])
    assert r["ventanas"]
