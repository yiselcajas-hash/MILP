"""Verificador independiente de factibilidad (no reutiliza el modelo MILP) y control de personal."""
from __future__ import annotations
from collections import defaultdict


def programa_completo(sub, sol):
    out = dict(sub.fixed)
    for o, (m, S) in sol.items():
        out[o] = (m, S, S + sub.pR[(o, m)])
    return out


def verificar(sub, sol, tol=1e-6):
    """Devuelve la lista de violaciones (vacía si la solución es factible)."""
    inst = sub.inst
    v = []
    if set(sol) != set(sub.free):
        return ["el conjunto de operaciones decididas no coincide con O^R"]
    full = programa_completo(sub, sol)
    for o, (m, S) in sol.items():
        if m not in sub.eligR[o]:
            v.append(f"{inst.op_label(o)} en máquina no elegible {m}")
        if S < sub.t0 - tol:
            v.append(f"{inst.op_label(o)} inicia antes del instante de decisión")
        if S < sub.lbR[o] - tol:
            v.append(f"{inst.op_label(o)} viola liberación o fin del predecesor fijo")
    for j in sub.jobs:
        seq = inst.job_ops[j]
        for a, b in zip(seq[:-1], seq[1:]):
            if a in full and b in full and full[b][1] < full[a][2] - tol:
                v.append(f"precedencia {inst.op_label(a)} -> {inst.op_label(b)} violada")
        if seq[0] in full and full[seq[0]][1] < inst.jobs[j]["r"] - tol:
            v.append(f"liberación del pedido {inst.jobs[j]['id']} violada")
    bym = defaultdict(list)
    for o, (m, S, C) in full.items():
        bym[m].append((S, C, o))
    for m, lst in bym.items():
        lst.sort()
        for (S1, C1, o1), (S2, C2, o2) in zip(lst[:-1], lst[1:]):
            if S2 < C1 - tol:
                v.append(f"solapamiento en {m}: {inst.op_label(o1)} y {inst.op_label(o2)}")
    # ocupación de máquinas por operaciones fijas fuera del subproblema
    for o, (m, S) in sol.items():
        if S < sub.mavail.get(m, sub.t0) - tol:
            v.append(f"{inst.op_label(o)} inicia antes de que {m} quede disponible")
    for (mw, a, b) in sub.all_windows:
        for o, (m, S) in sol.items():
            C = S + sub.pR[(o, m)]
            if m == mw and S < b - tol and C > a + tol:
                v.append(f"{inst.op_label(o)} se procesa durante la indisponibilidad de {mw}")
    return v


def control_personal(datos, programa, desde=None, hasta=None):
    """Comprueba en cada intervalo elemental que las máquinas ocupadas puedan atenderse con operarios
    distintos y habilitados (06B_HABILIDADES), mediante emparejamiento bipartito máximo.
    Devuelve (n_intervalos_con_conflicto, horas_con_conflicto, carga_por_operario_h)."""
    hab = datos.habilidades
    if not hab:
        return None
    puntos = set()
    for o, (m, S, C) in programa.items():
        if desde is not None and C <= desde:
            continue
        if hasta is not None and S >= hasta:
            continue
        puntos.add(S); puntos.add(C)
    puntos = sorted(puntos)
    ops_m = defaultdict(list)
    for o, (m, S, C) in programa.items():
        ops_m[m].append((S, C))
    conflictos, horas = 0, 0.0
    carga = defaultdict(float)
    for a, b in zip(puntos[:-1], puntos[1:]):
        if b - a < 1e-9:
            continue
        mid = (a + b) / 2
        ocupadas = [m for m, lst in ops_m.items() if any(S <= mid < C for S, C in lst)]
        # emparejamiento máquina -> operario
        asign = {}

        def aumentar(m, vistos):
            for w, ms in hab.items():
                if m in ms and w not in vistos:
                    vistos.add(w)
                    if w not in asign or aumentar(asign[w], vistos):
                        asign[w] = m
                        return True
            return False
        ok = sum(1 for m in ocupadas if aumentar(m, set()))
        if ok < len(ocupadas):
            conflictos += 1
            horas += b - a
        for w, m in asign.items():
            carga[w] += b - a
    return conflictos, horas, dict(carga)
