"""Verificación independiente de programas (no reutiliza el modelo MILP ni sus variables).

Dos niveles:
  verificar_subproblema(sub, sol)   solución {o: (m, S)} de un subproblema O^R frente a sus datos (t0, fijas,
                                    ventanas, disponibilidad de unidades, continuidad R12).
  verificar_programa(inst, ...)     programa completo ejecutado {o: (m, S, C)} más los tramos parciales de
                                    operaciones interrumpidas, con verificación opcional del personal asignado.

Cada comprobación devuelve mensajes legibles; una lista vacía significa «sin violaciones». Las comprobaciones
corresponden una a una con las restricciones del modelo (R1–R12) y con las reglas laborales (L1–L5):
  L1 cada operación tiene exactamente c_o trabajadores           L2 cada trabajador está habilitado para el recurso
  L3 un trabajador no atiende dos intervalos solapados           L4 carga diaria ≤ h_dia (turno único de 8 h)
  L5 los trabajadores asignados existen y están disponibles (no ausentes en el escenario)
"""
from __future__ import annotations

from collections import defaultdict

from .instancia import recurso_base

TOL = 1e-6


def programa_completo(sub, sol):
    out = dict(sub.fixed)
    for o, (m, S) in sol.items():
        out[o] = (m, S, S + sub.pR[(o, m)])
    return out


def _solapes(intervalos, tol):
    """intervalos: [(S, C, etiqueta)] de un mismo recurso o trabajador → pares solapados."""
    lst = sorted(intervalos)
    out = []
    fin_max, etiq_max = None, None
    for S, C, e in lst:
        if fin_max is not None and S < fin_max - tol:
            out.append((etiq_max, e))
        if fin_max is None or C > fin_max:
            fin_max, etiq_max = C, e
    return out


def _cruza_tramo(S, C, L, tol):
    """True si [S, C) no cabe en un único tramo continuo [kL, (k+1)L)."""
    if L <= 0 or C - S <= tol:
        return False
    k = int((S + tol) // L)
    return C > (k + 1) * L + tol


def verificar_subproblema(sub, sol, tol=TOL):
    """Lista de violaciones de una solución {o: (m, S)} del subproblema (vacía si es factible)."""
    inst = sub.inst
    v = []
    if set(sol) != set(sub.free):
        return ["R1: el conjunto de operaciones decididas no coincide con O^R"]
    no_eleg = [f"R1: {inst.op_label(o)} en unidad no elegible {m}" for o, (m, S) in sol.items() if m not in sub.eligR[o]]
    if no_eleg:            # sin unidad elegible no hay duración definida: se informa y no se sigue evaluando
        return no_eleg
    full = programa_completo(sub, sol)
    for o, (m, S) in sol.items():
        if S < sub.t0 - tol:
            v.append(f"R2: {inst.op_label(o)} inicia antes del instante de decisión")
        if S < sub.lbR[o] - tol:
            v.append(f"R2/R3: {inst.op_label(o)} viola liberación o fin del predecesor fijo")
        if S < sub.mavail.get(m, sub.t0) - tol:
            v.append(f"R2: {inst.op_label(o)} inicia antes de que {m} quede disponible")
    for j in sub.jobs:
        seq = inst.job_ops[j]
        for a, b in zip(seq[:-1], seq[1:]):
            if a in full and b in full and full[b][1] < full[a][2] - tol:
                v.append(f"R3: precedencia {inst.op_label(a)} -> {inst.op_label(b)} violada")
        if seq[0] in full and full[seq[0]][1] < inst.jobs[j]["r"] - tol:
            v.append(f"R3: liberación del pedido {inst.jobs[j]['id']} violada")
    bym = defaultdict(list)
    for o, (m, S, C) in full.items():
        bym[m].append((S, C, o))
    for m, lst in bym.items():
        for o1, o2 in _solapes(lst, tol):
            v.append(f"R4-R5: solapamiento en {m}: {inst.op_label(o1)} y {inst.op_label(o2)}")
    for (mw, a, b) in sub.all_windows:
        for o, (m, S) in sol.items():
            C = S + sub.pR[(o, m)]
            if m == mw and S < b - tol and C > a + tol:
                v.append(f"R6: {inst.op_label(o)} se procesa durante la indisponibilidad de {mw} [{a:.2f}, {b:.2f})")
    L = float(getattr(inst, "L_segmento", 0.0) or 0.0)
    for o, (m, S) in sol.items():
        if not inst.ops[o].get("interrumpible", True) and _cruza_tramo(S, S + sub.pR[(o, m)], L, tol):
            v.append(f"R12: {inst.op_label(o)} (no interrumpible) cruza una pausa o el cierre")
    return v


# alias de compatibilidad con v1.4
verificar = verificar_subproblema


def verificar_programa(inst, programa, ventanas=(), jobs=None, parciales=(), duraciones=None, asignacion=None,
                       habilidades=None, ausentes=(), horas_dia=None, tol=TOL):
    """Verificación integral de un programa ejecutado.

    programa:    {o: (m, S, C)} intervalo final (completo) de cada operación.
    ventanas:    [(unidad, a, b)] indisponibilidades (averías, mantenimientos) en unidades de recurso.
    jobs:        pedidos que deben estar completos (por defecto, todos los de la instancia).
    parciales:   [(o, m, S, C)] tramos ejecutados y luego interrumpidos por una avería (ocupan la unidad).
    duraciones:  {o: h} duración esperada del intervalo final cuando difiere de p_om (tiempo restante).
    asignacion:  {clave: [trabajadores]} con clave = ('F', o) para el intervalo final y ('P', i) para parciales[i].
    habilidades: {trabajador: {recursos}}; ausentes: trabajadores no disponibles en el escenario.
    Devuelve {categoría: [mensajes]} (todas las listas vacías ⇔ programa factible).
    """
    jobs = list(range(len(inst.jobs))) if jobs is None else list(jobs)
    duraciones = duraciones or {}
    L = float(getattr(inst, "L_segmento", 0.0) or 0.0)
    r = {k: [] for k in ("completitud", "elegibilidad", "duracion", "liberacion", "precedencia", "capacidad",
                         "ventanas", "continuidad", "personal")}
    esperadas = {o for j in jobs for o in inst.job_ops[j]}
    faltan = sorted(esperadas - set(programa))
    sobran = sorted(set(programa) - esperadas)
    for o in faltan:
        r["completitud"].append(f"{inst.op_label(o)} no fue programada")
    for o in sobran:
        r["completitud"].append(f"{inst.op_label(o)} pertenece a un pedido fuera del alcance")
    for o, (m, S, C) in programa.items():
        if m not in inst.elig[o]:
            r["elegibilidad"].append(f"{inst.op_label(o)} en unidad no elegible {m}")
            continue
        esperada = duraciones.get(o, inst.p[(o, m)])
        if abs((C - S) - esperada) > max(tol, 1e-6 * esperada):
            r["duracion"].append(f"{inst.op_label(o)} dura {C - S:.4f} h y se esperaban {esperada:.4f} h")
    for j in jobs:
        seq = inst.job_ops[j]
        if seq[0] in programa and programa[seq[0]][1] < inst.jobs[j]["r"] - tol:
            r["liberacion"].append(f"pedido {inst.jobs[j]['id']} inicia antes de su liberación")
        for a, b in zip(seq[:-1], seq[1:]):
            if a in programa and b in programa and programa[b][1] < programa[a][2] - tol:
                r["precedencia"].append(f"{inst.op_label(a)} -> {inst.op_label(b)} violada")
    for i, (o, m, S, C) in enumerate(parciales):
        if o in programa and programa[o][1] < C - tol:
            r["precedencia"].append(f"{inst.op_label(o)} se reanuda antes de terminar su tramo interrumpido")
    por_unidad = defaultdict(list)
    for o, (m, S, C) in programa.items():
        por_unidad[m].append((S, C, inst.op_label(o)))
    for i, (o, m, S, C) in enumerate(parciales):
        por_unidad[m].append((S, C, inst.op_label(o) + "(parcial)"))
    for m, lst in por_unidad.items():
        for e1, e2 in _solapes(lst, tol):
            r["capacidad"].append(f"{m}: {e1} y {e2} se solapan")
    vent_u = defaultdict(list)
    for (u, a, b) in ventanas:
        vent_u[u].append((a, b))
    for m, lst in por_unidad.items():
        for (S, C, e) in lst:
            for (a, b) in vent_u.get(m, ()):
                if S < b - tol and C > a + tol:
                    r["ventanas"].append(f"{e} se procesa en {m} durante la indisponibilidad [{a:.2f}, {b:.2f})")
    for o, (m, S, C) in programa.items():
        if not inst.ops[o].get("interrumpible", True) and _cruza_tramo(S, C, L, tol):
            r["continuidad"].append(f"{inst.op_label(o)} (no interrumpible) cruza una pausa o el cierre")
    if asignacion is not None:
        r["personal"] = verificar_personal(inst, programa, parciales, asignacion, habilidades or {}, ausentes,
                                           horas_dia or inst.datos.calendario.h_dia, tol)
    return r


def intervalos_trabajo(programa, parciales=()):
    """[(clave, o, m, S, C)] de todos los intervalos que ocupan una unidad (finales y parciales)."""
    out = [(("F", o), o, m, S, C) for o, (m, S, C) in programa.items() if C - S > TOL]
    out += [(("P", i), o, m, S, C) for i, (o, m, S, C) in enumerate(parciales) if C - S > TOL]
    return out


def verificar_personal(inst, programa, parciales, asignacion, habilidades, ausentes=(), horas_dia=8.0, tol=TOL):
    """Reglas L1–L5 sobre la asignación de trabajadores; devuelve la lista de violaciones."""
    v = []
    aus = set(ausentes)
    por_w = defaultdict(list)
    for clave, o, m, S, C in intervalos_trabajo(programa, parciales):
        ws = list(asignacion.get(clave, []))
        c = int(inst.ops[o].get("crew", 1))
        et = inst.op_label(o) + ("" if clave[0] == "F" else "(parcial)")
        if len(ws) != c or len(set(ws)) != len(ws):
            v.append(f"L1: {et} requiere {c} trabajador(es) distintos y tiene {len(set(ws))}")
        for w in ws:
            if w not in habilidades:
                v.append(f"L5: {et} asignada a {w}, que no figura en la dotación")
                continue
            if w in aus:
                v.append(f"L5: {et} asignada a {w}, ausente en el escenario")
            if recurso_base(m) not in habilidades[w]:
                v.append(f"L2: {w} no está habilitado para {recurso_base(m)} ({et})")
            por_w[w].append((S, C, et))
    for w, lst in por_w.items():
        for e1, e2 in _solapes(lst, tol):
            v.append(f"L3: {w} asignado simultáneamente a {e1} y {e2}")
        carga = defaultdict(float)
        for S, C, _ in lst:
            k = int((S + tol) // horas_dia)
            while k * horas_dia < C - tol:
                ini, fin = max(S, k * horas_dia), min(C, (k + 1) * horas_dia)
                if fin > ini:
                    carga[k] += fin - ini
                k += 1
        for k, h in carga.items():
            if h > horas_dia + tol:
                v.append(f"L4: {w} acumula {h:.2f} h en el día productivo {k} (límite {horas_dia:.1f} h)")
    return v


def resumen(resultado):
    """{categoría: número de violaciones} y total."""
    cuenta = {k: len(x) for k, x in resultado.items()}
    cuenta["total"] = sum(cuenta.values())
    return cuenta
