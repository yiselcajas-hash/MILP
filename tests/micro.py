"""Microinstancias aleatorias para validar el MILP por enumeración exhaustiva.

Cada microinstancia tiene 3 pedidos con 2–3 operaciones, dos máquinas simples (M1, M2) y un recurso con DOS
unidades idénticas (R#1, R#2), flexibilidad de rutas, operaciones no interrumpibles (R12, tramos de L = 4 h) y
averías actuales o futuras. La enumeración recorre todas las asignaciones y todas las secuencias por unidad;
para objetivos regulares (tardanza ponderada, penalidad) basta con programas semiactivos. La estabilidad (P3,
no regular) se obtiene con un PL de tiempos por asignación/secuencia/patrón de atraso.
"""
from __future__ import annotations

import itertools
import random
from types import SimpleNamespace

import numpy as np
from scipy.optimize import linprog

from sagapi import estado, reglas
from sagapi.indicadores import kpis_subproblema
from sagapi.instancia import Instancia
from sagapi.verificacion import verificar_subproblema

RECURSOS = {"M1": ["M1"], "M2": ["M2"], "R": ["R#1", "R#2"]}
UNIDADES = ["M1", "M2", "R#1", "R#2"]


def micro(seed, L=4.0):
    rnd = random.Random(seed)
    jobs, ops, job_ops, elig, p = [], [], {}, {}, {}
    for j in range(3):
        r = rnd.choice([0.0, 0.0, 1.0, 2.0])
        nops = rnd.choice([2, 2, 3])
        tot = 0
        job_ops[j] = []
        for k in range(nops):
            o = len(ops)
            principal = rnd.choice(list(RECURSOS))
            alt = [m for m in RECURSOS if m != principal and rnd.random() < 0.3]
            q = rnd.choice([2, 3, 4])
            u = rnd.choice([20, 30, 45])
            no_int = rnd.random() < 0.3
            ops.append(dict(idx=o, job=j, pos=k, paso=k + 1, operacion=f"op{k}", principal=principal, trato="POR_UNIDAD",
                            setup_min=6.0, min_unidad=u, lote=10, q=q, crew=1, interrumpible=not no_int))
            job_ops[j].append(o)
            elig[o] = []
            for m in [principal] + alt:
                for un in RECURSOS[m]:
                    elig[o].append(un)
                    p[(o, un)] = round((6 + q * u) / 60 * (1.0 if m == principal else 1.1), 4)
            tot += p[(o, RECURSOS[principal][0])]
        d = r + tot * rnd.uniform(1.0, 2.0)
        w = rnd.choice([0.6, 1.0, 1.5])
        jobs.append(dict(idx=j, id=f"J{j}", familia="F", producto="X", q=1, r=r, d=round(d, 3), w=w, P=round(1000 * w, 1),
                         pdia=50.0 * w, valor=10000 * w, tope=1000 * w))
    datos = SimpleNamespace(recuperacion=[], maquinas={}, masa_chapa={})
    inst = Instancia(datos, jobs, ops, job_ops, elig, p, list(UNIDADES), {}, dict(RECURSOS), L)
    return inst, datos, rnd


def escenario(seed):
    """Subproblema reactivo: avería en t_b sobre el plan FIFO (actual, simultánea o con ventana futura)."""
    inst, datos, rnd = micro(seed)
    plan, _ = reglas.fifo_plan(inst, range(3))
    horizonte = max(C for (_, _, C) in plan.values())
    tb = round(rnd.uniform(0.2, 0.6) * horizonte, 3)
    mstar = rnd.choice(UNIDADES)
    ventanas = [(mstar, tb, tb + rnd.choice([1.0, 2.0, 3.5]))]
    if seed % 3 == 2:      # mantenimiento futuro anunciado en otra unidad (R6)
        otra = rnd.choice([m for m in UNIDADES if m != mstar])
        a = tb + rnd.uniform(0.5, 3.0)
        ventanas.append((otra, round(a, 3), round(a + rnd.choice([1.0, 2.0]), 3)))
    if seed % 3 == 1:      # dos unidades caídas a la vez
        otra = rnd.choice([m for m in UNIDADES if m != mstar])
        ventanas.append((otra, tb, tb + rnd.choice([1.0, 2.5])))
    jobs = [j for j in range(3) if inst.jobs[j]["r"] <= tb and plan[inst.job_ops[j][-1]][2] > tb]
    return estado.particionar(datos, inst, plan, tb, jobs, ventanas, rnd.choice("AB"))


def inicial(seed):
    """Subproblema de programación de pedidos nuevos (sin programa vigente) con una ventana futura."""
    inst, datos, rnd = micro(seed)
    sub = estado.subproblema_inicial(inst)
    a = round(rnd.uniform(0.5, 4.0), 3)
    w = (rnd.choice(UNIDADES), a, a + rnd.choice([1.0, 2.0]))
    sub.windows = [w]
    sub.all_windows = [w]
    return sub


def semiactivos(sub):
    """Todos los programas semiactivos factibles: [(sol, A, sec)]."""
    free = sub.free
    out = []
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
            except (RuntimeError, ValueError):
                continue
            if verificar_subproblema(sub, sol):
                continue
            out.append((sol, A, sec))
    return out


def optimo_enumerado(sub, regla="TARDANZA_PONDERADA", beta=8.0):
    """(f_P1*, f_P2*, f_P3* o None) por enumeración; f_P3 solo sin ventanas futuras ni operaciones R12."""
    progs = semiactivos(sub)
    vals = []
    for sol, A, sec in progs:
        k = kpis_subproblema(sub, sol, beta=beta)
        vals.append((k["tardanza_ponderada"], k["penalidad_estimada"], A, sec))
    if regla == "TARDANZA_PONDERADA":
        p1 = min(v[0] for v in vals)
        p2 = min(v[1] for v in vals if v[0] <= p1 + 1e-6)
    else:
        p1 = min(v[1] for v in vals)
        p2 = min(v[0] for v in vals if v[1] <= p1 + 1e-6)
    hay_r12 = any(not sub.inst.ops[o]["interrumpible"] for o in sub.free)
    if not sub.S0 or sub.windows or hay_r12:
        return p1, p2, None, len(progs)
    inst = sub.inst
    jobs = sub.jobs_free()
    c_pen = c_tp = 0.0
    for j in sub.jobs:
        if j not in jobs:
            T = max(0.0, sub.fixed[inst.job_ops[j][-1]][2] - inst.jobs[j]["d"])
            c_pen += inst.jobs[j]["P"] if T > 1e-6 else 0.0
            c_tp += inst.jobs[j]["w"] * T
    cap_tp, cap_pen = (p1, p2) if regla == "TARDANZA_PONDERADA" else (p2, p1)
    f3 = np.inf
    vistos = set()
    for tp, pen, A, sec in vals:
        clave = (tuple(sorted(A.items())), tuple((m, tuple(s)) for m, s in sorted(sec.items())))
        if clave in vistos:
            continue
        vistos.add(clave)
        for U in itertools.product([0, 1], repeat=len(jobs)):
            if c_pen + sum(inst.jobs[j]["P"] * u for j, u in zip(jobs, U)) > cap_pen + 1e-6:
                continue
            f3 = min(f3, _pl_estabilidad(sub, A, sec, dict(zip(jobs, U)), cap_tp - c_tp, beta))
    return p1, p2, f3, len(progs)


def _pl_estabilidad(sub, A, sec, U, cap_tp, beta):
    inst = sub.inst
    free = sub.free
    idx = {o: k for k, o in enumerate(free)}
    nS = len(free)
    pend = list(sub.pending)
    jobs = sub.jobs_free()
    nv = nS + 2 * len(pend) + len(jobs)
    c = np.zeros(nv)
    for k in range(len(pend)):
        c[nS + 2 * k] = 1
        c[nS + 2 * k + 1] = 1
    Aub, bub, Aeq, beq = [], [], [], []
    bounds = [(sub.lbR[o], None) for o in free] + [(0, None)] * (2 * len(pend) + len(jobs))
    for o in free:
        row = np.zeros(nv); row[idx[o]] = -1; Aub.append(row); bub.append(-sub.mavail.get(A[o], sub.t0))
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
    Aub.append(capT); bub.append(cap_tp + 1e-6)
    res = linprog(c, A_ub=np.array(Aub), b_ub=np.array(bub), A_eq=np.array(Aeq) if Aeq else None,
                  b_eq=np.array(beq) if beq else None, bounds=bounds, method="highs")
    if res.status != 0:
        return np.inf
    R = sum(1 for o in free if o in sub.m0 and A[o] != sub.m0[o])
    return res.fun + beta * R
