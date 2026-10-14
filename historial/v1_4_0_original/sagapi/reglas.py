"""Reglas de programación usadas como comparadores y cálculo de tiempos dados asignación y secuencias.

- FIFO (programación convencional): pedidos por fecha de liberación y código; cada operación en su
  máquina principal, al final de la cola de la máquina (sin intercalar). Reproduce exactamente la
  hoja 16_PROGRAMA_BASE (prueba tests/test_fifo.py).
- CONVENCIONAL ante avería (práctica actual descrita en 19_PARAMETROS): se conserva la máquina y el
  orden de cada cola; la operación interrumpida espera la reparación y todo lo que sigue se desplaza
  (desplazamiento a la derecha). Nada se adelanta respecto del programa vigente.
- EDD: despacho por fecha comprometida más próxima con elección de la máquina elegible que termina
  antes (permite reasignar); comparador clásico de la literatura (Zambrano-Rey et al., 2024).
"""
from __future__ import annotations
from collections import defaultdict

EPS = 1e-9


def _empujar_ventanas(S, p, m, ventanas):
    """Retrasa S hasta que [S, S+p) no se cruce con ninguna ventana (m, a, b)."""
    cambio = True
    while cambio:
        cambio = False
        for (mw, a, b) in ventanas:
            if mw == m and S < b - EPS and S + p > a + EPS:
                S = b
                cambio = True
    return S


def cronograma(sub, asign, secuencias, modo="semiactivo", ref=None):
    """Tiempos de inicio dados asignación {o: m} y secuencias {m: [o...]} (orden de proceso).

    modo='semiactivo'  : cada operación inicia lo antes posible respetando secuencias (compacta el programa).
    modo='no_antes'    : además S_o ≥ ref[o] (nada se adelanta; desplazamiento a la derecha).
    modo='reparar'     : S_o ≥ ref[o] con ref = inicio entregado por el solucionador (sólo elimina residuos numéricos).
    """
    inst = sub.inst
    pos = {}
    for m, seq in secuencias.items():
        for k, o in enumerate(seq):
            pos[o] = (m, k)
    C = {}
    S = {}
    pendientes = set(asign)
    avail = dict(sub.mavail)
    hechos_m = defaultdict(int)
    while pendientes:
        avance = False
        for m, seq in secuencias.items():
            k = hechos_m[m]
            if k >= len(seq):
                continue
            o = seq[k]
            pr = inst.pred(o)
            if pr is not None and pr in pendientes:
                continue
            lb = sub.lbR[o]
            if pr is not None and pr in C:
                lb = max(lb, C[pr])
            elif pr is not None and pr in sub.fixed:
                lb = max(lb, sub.fixed[pr][2])
            lb = max(lb, avail.get(m, sub.t0))
            if modo in ("no_antes", "reparar") and ref is not None and o in ref:
                lb = max(lb, ref[o])
            p = sub.pR[(o, m)]
            s = _empujar_ventanas(lb, p, m, sub.all_windows)
            S[o] = s
            C[o] = s + p
            avail[m] = C[o]
            hechos_m[m] += 1
            pendientes.discard(o)
            avance = True
        if not avance:
            raise RuntimeError("cronograma: secuencias incompatibles con la precedencia (ciclo)")
    return {o: (asign[o], S[o]) for o in asign}


def secuencias_de(sol):
    sec = defaultdict(list)
    for o, (m, S) in sorted(sol.items(), key=lambda kv: (kv[1][1], kv[0])):
        sec[m].append(o)
    return dict(sec)


def reparar(sub, sol):
    """Elimina residuos numéricos del solucionador sin cambiar asignaciones ni secuencias (sólo retrasa)."""
    return cronograma(sub, {o: m for o, (m, S) in sol.items()}, secuencias_de(sol), "reparar",
                      {o: S for o, (m, S) in sol.items()})


def semiactivo(sub, sol):
    """Adelanta cada operación al primer instante factible sin alterar asignaciones ni secuencias."""
    return cronograma(sub, {o: m for o, (m, S) in sol.items()}, secuencias_de(sol), "semiactivo")


# ---------------------------------------------------------------------------------------------
def fifo_plan(inst, jobs, avail=None, t_min=0.0, ventanas=()):
    """Programación convencional por orden de llegada (append) para los pedidos 'jobs'.

    avail: {m: instante en que termina la cola actual de m}. Devuelve {o: (m, S, C)} y el avail actualizado.
    """
    avail = defaultdict(float, avail or {})
    out = {}
    orden = sorted(jobs, key=lambda j: (inst.jobs[j]["r"], inst.jobs[j]["id"]))
    for j in orden:
        t = max(inst.jobs[j]["r"], t_min)
        for o in inst.job_ops[j]:
            m = inst.ops[o]["principal"]
            p = inst.p[(o, m)]
            S = _empujar_ventanas(max(t, avail[m]), p, m, ventanas)
            out[o] = (m, S, S + p)
            avail[m] = S + p
            t = S + p
    return out, dict(avail)


def convencional(sub):
    """Reacción convencional: misma máquina y mismo orden de cola; la interrumpida espera la reparación;
    pedidos sin programa previo se agregan al final de las colas por orden de llegada."""
    asign, ref = {}, {}
    for o in sub.free:
        if o in sub.m0:
            asign[o] = sub.m0[o]
            ref[o] = sub.S0[o]
    nuevos = [o for o in sub.free if o not in sub.m0]
    sec = defaultdict(list)
    for o in sorted(asign, key=lambda o: (ref[o], o)):
        sec[asign[o]].append(o)
    inst = sub.inst
    for o in sorted(nuevos, key=lambda o: (inst.jobs[inst.ops[o]["job"]]["r"], inst.jobs[inst.ops[o]["job"]]["id"], o)):
        m = inst.ops[o]["principal"] if inst.ops[o]["principal"] in sub.eligR[o] else sub.eligR[o][0]
        asign[o] = m
        sec[m].append(o)
    return cronograma(sub, asign, dict(sec), "no_antes", ref)


def edd(sub):
    """Despacho por fecha comprometida (EDD) con elección de la máquina que termina antes."""
    inst = sub.inst
    C = {}
    avail = dict(sub.mavail)
    sol = {}
    restantes = set(sub.free)

    def listo(o):
        pr = inst.pred(o)
        return pr is None or pr not in restantes

    while restantes:
        cand = [o for o in restantes if listo(o)]

        def lb(o):
            pr = inst.pred(o)
            t = sub.lbR[o]
            if pr is not None and pr in C:
                t = max(t, C[pr])
            return t
        o = min(cand, key=lambda o: (inst.jobs[inst.ops[o]["job"]]["d"], lb(o), o))
        mejor = None
        for m in sub.eligR[o]:
            p = sub.pR[(o, m)]
            s = _empujar_ventanas(max(lb(o), avail.get(m, sub.t0)), p, m, sub.all_windows)
            key = (s + p, 0 if m == sub.m0.get(o, inst.ops[o]["principal"]) else 1)
            if mejor is None or key < mejor[0]:
                mejor = (key, m, s)
        _, m, s = mejor
        sol[o] = (m, s)
        C[o] = s + sub.pR[(o, m)]
        avail[m] = C[o]
        restantes.discard(o)
    return sol
