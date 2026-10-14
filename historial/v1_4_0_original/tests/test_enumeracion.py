"""Verificación del MILP por enumeración exhaustiva en microinstancias aleatorias.

Para cada microinstancia (3 pedidos, 2–3 operaciones, 3 máquinas con flexibilidad, una avería) se
enumeran todas las asignaciones y secuencias por máquina:
  - f1* y f1b* se obtienen con programas semiactivos (óptimos para objetivos regulares);
  - f2* se obtiene resolviendo, para cada asignación/secuencia y cada patrón de pedidos atrasados
    compatible con f1 ≤ f1*, un PL de tiempos (scipy.optimize.linprog) con f1b ≤ f1b*.
El MILP debe reproducir los tres valores. Ejecutar: python -m tests.test_enumeracion
"""
import itertools
import os
import random
import sys
from types import SimpleNamespace

import numpy as np
from scipy.optimize import linprog

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sagapi.instancia import Instancia                      # noqa: E402
from sagapi import estado, optimizacion as opt, reglas      # noqa: E402
from sagapi.indicadores import evaluar                      # noqa: E402
from sagapi.verificacion import verificar                   # noqa: E402

MAQ = ["M1", "M2", "M3"]


def micro(seed):
    rnd = random.Random(seed)
    jobs, ops, job_ops, elig, p = [], [], {}, {}, {}
    for j in range(3):
        r = rnd.choice([0.0, 0.0, 1.0, 2.0])
        nops = rnd.choice([2, 2, 3])
        tot = 0
        job_ops[j] = []
        for k in range(nops):
            o = len(ops)
            principal = rnd.choice(MAQ)
            alt = [m for m in MAQ if m != principal and rnd.random() < 0.35]
            ops.append(dict(idx=o, job=j, paso=k + 1, operacion=f"op{k}", principal=principal, trato="POR_UNIDAD",
                            setup_min=6.0, min_unidad=rnd.choice([30, 45, 60, 90]), lote=10, q=rnd.choice([2, 3, 4])))
            job_ops[j].append(o)
            elig[o] = [principal] + alt
            for m in elig[o]:
                p[(o, m)] = round((6 + ops[o]["q"] * ops[o]["min_unidad"]) / 60 * (1.0 if m == principal else 1.1), 4)
            tot += p[(o, principal)]
        d = r + tot * rnd.uniform(1.0, 2.2)
        w = rnd.choice([0.6, 1.0, 1.5])
        jobs.append(dict(idx=j, id=f"J{j}", familia="F", producto="X", q=1, r=r, d=round(d, 3), w=w, P=round(1000 * w, 1),
                         pdia=50.0 * w, valor=10000 * w))
    datos = SimpleNamespace(recuperacion=[], maquinas={}, masa_chapa={})
    return Instancia(datos, jobs, ops, job_ops, elig, p, MAQ), datos, rnd


def escenario(seed):
    I, datos, rnd = micro(seed)
    plan, _ = reglas.fifo_plan(I, range(3))
    horizon = max(C for (_, _, C) in plan.values())
    tb = round(rnd.uniform(0.2, 0.6) * horizon, 3)
    mstar = rnd.choice(MAQ)
    dur = rnd.choice([1.0, 2.0, 3.5])
    jobs = [j for j in range(3) if I.jobs[j]["r"] <= tb and plan[I.job_ops[j][-1]][2] > tb]
    ventanas = [(mstar, tb, tb + dur)]
    if seed % 3 == 2:   # ventana futura en otra máquina (mantenimiento anunciado): prueba (R6)
        otra = rnd.choice([m for m in MAQ if m != mstar])
        a = tb + rnd.uniform(0.5, 3.0)
        ventanas.append((otra, round(a, 3), round(a + rnd.choice([1.0, 2.0]), 3)))
    if seed % 3 == 1:   # falla simultánea de dos máquinas
        otra = rnd.choice([m for m in MAQ if m != mstar])
        ventanas.append((otra, tb, tb + rnd.choice([1.0, 2.5])))
    sub = estado.particionar(datos, I, plan, tb, jobs, ventanas, rnd.choice("AB"))
    return sub


def enumerar(sub, beta=8.0):
    inst = sub.inst
    free = sub.free
    mejores = []
    for asign in itertools.product(*[sub.eligR[o] for o in free]):
        A = dict(zip(free, asign))
        porm = {}
        for o, m in A.items():
            porm.setdefault(m, []).append(o)
        maqs = list(porm)
        for perms in itertools.product(*[itertools.permutations(porm[m]) for m in maqs]):
            sec = {m: list(pm) for m, pm in zip(maqs, perms)}
            try:
                sol = reglas.cronograma(sub, A, sec, "semiactivo")
            except RuntimeError:
                continue
            if verificar(sub, sol):
                continue
            k = evaluar(sub, sol, beta=beta)
            mejores.append((k["penalidad"], k["tard_pond"], A, sec))
    f1 = min(m[0] for m in mejores)
    f1b = min(m[1] for m in mejores if m[0] <= f1 + 1e-6)
    # f2 por PL sobre cada asignación/secuencia y patrón de atraso
    f2 = np.inf
    if sub.windows:          # con ventanas futuras la estabilidad no se comprueba por PL (requiere elegir antes/después)
        return f1, f1b, None
    jobs = sub.jobs_free()
    # constantes de pedidos cuyo último paso ya está fijo (no dependen de la decisión)
    c_pen = c_tp = 0.0
    for j in sub.jobs:
        if j not in jobs:
            last = inst.job_ops[j][-1]
            T = max(0.0, sub.fixed[last][2] - inst.jobs[j]["d"])
            c_pen += inst.jobs[j]["P"] if T > 1e-6 else 0.0
            c_tp += inst.jobs[j]["w"] * T
    for pen, tp, A, sec in mejores:
        if pen > f1 + 1e-6:
            continue
        for U in itertools.product([0, 1], repeat=len(jobs)):
            if c_pen + sum(inst.jobs[j]["P"] * u for j, u in zip(jobs, U)) > f1 + 1e-6:
                continue
            val = pl_f2(sub, A, sec, dict(zip(jobs, U)), f1b - c_tp, beta)
            f2 = min(f2, val)
    return f1, f1b, f2


def pl_f2(sub, A, sec, U, cap_f1b, beta):
    inst = sub.inst
    free = sub.free
    idx = {o: k for k, o in enumerate(free)}
    nS = len(free)
    pend = [o for o in sub.pending]
    jobs = sub.jobs_free()
    nv = nS + 2 * len(pend) + len(jobs)          # S, dp, dm, T
    c = np.zeros(nv)
    for k in range(len(pend)):
        c[nS + 2 * k] = 1; c[nS + 2 * k + 1] = 1
    Aub, bub, Aeq, beq = [], [], [], []
    bounds = [(sub.lbR[o], None) for o in free] + [(0, None)] * (2 * len(pend)) + [(0, None)] * len(jobs)
    for o in free:   # disponibilidad
        m = A[o]
        row = np.zeros(nv); row[idx[o]] = -1; Aub.append(row); bub.append(-sub.mavail.get(m, sub.t0))
        for (mw, a, b) in sub.all_windows:
            if mw == m:
                row = np.zeros(nv); row[idx[o]] = -1; Aub.append(row); bub.append(-b)
    for j, seq in inst.job_ops.items():
        for a, b in zip(seq[:-1], seq[1:]):
            if a in idx and b in idx:
                row = np.zeros(nv); row[idx[a]] = 1; row[idx[b]] = -1; Aub.append(row); bub.append(-sub.pR[(a, A[a])])
    for m, s in sec.items():
        for a, b in zip(s[:-1], s[1:]):
            row = np.zeros(nv); row[idx[a]] = 1; row[idx[b]] = -1; Aub.append(row); bub.append(-sub.pR[(a, A[a])])
    for k, o in enumerate(pend):
        row = np.zeros(nv); row[idx[o]] = 1; row[nS + 2 * k] = -1; row[nS + 2 * k + 1] = 1
        Aeq.append(row); beq.append(sub.S0[o])
    capT = np.zeros(nv)
    for k, j in enumerate(jobs):
        last = inst.job_ops[j][-1]
        tcol = nS + 2 * len(pend) + k
        row = np.zeros(nv); row[idx[last]] = 1; row[tcol] = -1; Aub.append(row); bub.append(inst.jobs[j]["d"] - sub.pR[(last, A[last])])
        if U[j] == 0:
            row = np.zeros(nv); row[idx[last]] = 1; Aub.append(row); bub.append(inst.jobs[j]["d"] - sub.pR[(last, A[last])])
        capT[tcol] = inst.jobs[j]["w"]
    Aub.append(capT); bub.append(cap_f1b + 1e-6)
    res = linprog(c, A_ub=np.array(Aub), b_ub=np.array(bub), A_eq=np.array(Aeq) if Aeq else None,
                  b_eq=np.array(beq) if beq else None, bounds=bounds, method="highs")
    if res.status != 0:
        return np.inf
    R = sum(1 for o in free if o in sub.m0 and A[o] != sub.m0[o])
    return res.fun + beta * R


def main(n=120):
    ok1 = ok2 = ok3 = tot = 0
    filas = []
    for seed in range(n):
        sub = escenario(seed)
        if not sub.free:
            continue
        f1, f1b, f2 = enumerar(sub)
        r = opt.lexicografico(sub, tl=(30, 30, 30))
        k = evaluar(sub, r["sol"])
        v = verificar(sub, r["sol"])
        g1 = abs(k["penalidad"] - f1) < 1e-4
        g2 = abs(k["tard_pond"] - f1b) < 1e-3
        g3 = True if f2 is None else abs(k["f2"] - f2) < 1e-3 * max(1, f2)
        tot += 1; ok1 += g1; ok2 += g2; ok3 += g3
        filas.append((seed, len(sub.free), f1, k["penalidad"], f1b, k["tard_pond"], f2, k["f2"], len(v)))
        if not (g1 and g2 and g3) or v:
            print("DIFERENCIA", filas[-1])
    print(f"f1 {ok1}/{tot}  f1b {ok2}/{tot}  f2 {ok3}/{tot}  violaciones {sum(f[-1] for f in filas)}")
    out = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "resultados", "verificacion_enumeracion.csv")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    import csv
    with open(out, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["semilla", "ops_libres", "f1_enum", "f1_milp", "f1b_enum", "f1b_milp", "f2_enum", "f2_milp", "violaciones"])
        w.writerows(filas)
    return ok1 == ok2 == ok3 == tot


if __name__ == "__main__":
    sys.exit(0 if main(int(sys.argv[1]) if len(sys.argv) > 1 else 120) else 1)
