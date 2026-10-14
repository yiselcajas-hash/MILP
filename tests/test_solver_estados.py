"""El sistema distingue óptimo, factible al límite de tiempo, infactible, no acotado, heurística y error."""
from sagapi import estado, optimizacion as opt, reglas, simulacion as sim
from sagapi.solver import INF, Estado, LinModel, solve, validar_vector


def test_optimo():
    M = LinModel()
    x = M.var("x", 0, 10, integer=True)
    M.row([(x, 1.0)], 2.5, INF)
    M.set_objective([(x, 1.0)])
    r = solve(M)
    assert r["estado"] == Estado.OPTIMO and r["x"][x] == 3


def test_infactible():
    M = LinModel()
    x = M.var("x", 0, 1, integer=True)
    M.row([(x, 1.0)], 2.0, INF)
    M.set_objective([(x, 1.0)])
    r = solve(M)
    assert r["estado"] == Estado.INFACTIBLE and r["x"] is None


def test_no_acotado():
    M = LinModel()
    x = M.var("x", 0, INF, integer=True)
    M.set_objective([(x, -1.0)])
    r = solve(M)
    assert r["estado"] in (Estado.NO_ACOTADO, Estado.ERROR) and r["x"] is None


def test_verificacion_algebraica_independiente():
    M = LinModel()
    x = M.var("x", 0, 5, integer=True)
    M.row([(x, 1.0)], 1.0, 3.0)
    assert validar_vector(M, [2.0]) == []
    assert validar_vector(M, [4.0])
    assert validar_vector(M, [1.5])


def test_limite_de_tiempo_y_respaldo_heuristico(datos, inst):
    """Con un límite de tiempo ínfimo el resultado nunca se declara óptimo."""
    base, _ = reglas.fifo_plan(inst, list(range(len(inst.jobs))))
    wu = estado.ventanas_unidades(inst, [(m, a, b) for (_, m, a, b) in sim.ventanas_de(datos, ["F06"])])
    tb = wu[0][1]
    jobs = [j for j in range(len(inst.jobs)) if inst.jobs[j]["r"] <= tb and base[inst.job_ops[j][-1]][2] > tb]
    sub = estado.particionar(datos, inst, base, tb, jobs, wu, "A")
    r = opt.optimizar(sub, tl=0.01)
    assert r["sol"] is not None
    assert r["estado_global"] in (Estado.FACTIBLE_LIMITE, Estado.HEURISTICA)
    assert not r["certificado"]
