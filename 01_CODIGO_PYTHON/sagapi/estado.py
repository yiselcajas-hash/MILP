"""Estado productivo en un instante de decisión y subproblema de (re)programación.

En el instante t0 (llegada de pedidos o avería) cada operación del programa vigente queda en:
  O^C completada (C <= t0)                         -> se excluye
  O^E en ejecución en una máquina disponible        -> se fija (no se interrumpe)
  O^I interrumpida (en ejecución en la máquina que falla en t0) -> libre, con tiempo restante según política
  O^P pendiente (S >= t0)                           -> libre
O^R = O^P ∪ O^I son las operaciones que decide el MILP.
"""
from __future__ import annotations
import math
from dataclasses import dataclass, field

EPS = 1e-6


@dataclass
class Subproblema:
    inst: object
    t0: float
    free: list
    eligR: dict                 # o -> [m]
    pR: dict                    # (o, m) -> h
    lbR: dict                   # o -> cota inferior de inicio
    mavail: dict                # m -> instante desde el que m está libre (ops fijas y averías en curso)
    fixed: dict                 # o -> (m, S, C)
    windows: list = field(default_factory=list)      # ventanas futuras (m, a, b) con a > t0
    all_windows: list = field(default_factory=list)  # todas las ventanas consideradas (para verificar)
    S0: dict = field(default_factory=dict)
    m0: dict = field(default_factory=dict)
    pending: list = field(default_factory=list)
    interrupted: list = field(default_factory=list)
    info: dict = field(default_factory=dict)
    jobs: list = field(default_factory=list)          # pedidos cuyo cumplimiento se evalúa
    congeladas: list = field(default_factory=list)    # operaciones pendientes fijadas por el horizonte congelado

    def jobs_free(self):
        return sorted({self.inst.ops[o]["job"] for o in self.free})

    def upper_bound_time(self):
        base = max([self.t0] + list(self.mavail.values()) + list(self.lbR.values()) + [b for (_, _, b) in self.windows])
        ub = base + sum(max(self.pR[(o, m)] for m in self.eligR[o]) for o in self.free)
        ub += sum(b - a for (_, a, b) in self.windows)
        L = getattr(self.inst, "L_segmento", 0.0) or 0.0
        ub += sum(L for o in self.free if not self.inst.ops[o].get("interrumpible", True))   # holgura por continuidad (R12)
        if self.S0:
            ub = max(ub, max(self.S0.values()) + max(self.pR.values()) + 1.0)
        return ub


def regla_recuperacion(datos, inst, o, m_star, politica):
    """Regla de 25_RECUPERACION_SIM aplicable: específica (producto, paso) o genérica según el tratamiento del tiempo."""
    op = inst.ops[o]
    prod = inst.jobs[op["job"]]["producto"]
    ambito_gen = "GENERICO_POR_LOTE" if op["trato"] == "POR_LOTE" else "GENERICO_POR_UNIDAD"
    gen = None
    for r in datos.recuperacion:
        if r["politica"] != politica:
            continue
        if r["ambito"] == "PRODUCTO_PASO" and r["producto"] == prod and r["paso"] == op["paso"]:
            return r
        if r["ambito"] == ambito_gen and gen is None:
            gen = r
    if gen is not None:
        return gen
    # regla por defecto documentada: A conserva piezas sin repetir preparación; B reinicia todo
    return dict(politica=politica, conserva=1 if politica == "A" else 0, reinicia=0 if politica == "A" else 1,
                repite_setup=0 if politica == "A" else 1, repetir=0, verif_min=0.0)


def p_principal(inst, o):
    """Tiempo de la operación en (la primera unidad de) su recurso principal."""
    op = inst.ops[o]
    us = inst.unidades.get(op["principal"], [op["principal"]]) if getattr(inst, "unidades", None) else [op["principal"]]
    return inst.p[(o, us[0])]


def ventanas_unidades(inst, ventanas):
    """Convierte ventanas (recurso, a, b) en ventanas por unidad (un evento de recurso afecta a todas sus unidades)."""
    out = []
    for (m, a, b) in ventanas:
        us = getattr(inst, "unidades", {}).get(m) if "#" not in str(m) else [m]
        for u in (us or [m]):
            out.append((u, a, b))
    return out


def tiempo_restante(datos, inst, o, m_star, transcurrido, politica, m_dest):
    """Tiempo restante (h) de la operación interrumpida o si se reanuda en m_dest.

    Devuelve (horas, unidades_terminadas, unidades_a_reprocesar).
    Lotes de tamaño L: cada lote = preparación s + n_l·u. k = unidades completas al fallar.
    A (conserva piezas): (q - k + rep_extra)·u·f + verificación + preparaciones de lotes no iniciados
        (+ preparación del lote en curso si 'Repite setup' = 1 o si cambia de máquina).
    B (reinicia lote): tiempo completo de la operación en m_dest; se reprocesan las k unidades.
    """
    op = inst.ops[o]
    q, L = op["q"], op["lote"]
    s = op["setup_min"] / 60.0
    u_star = op["min_unidad"] / 60.0
    pp = p_principal(inst, o)
    fac = inst.p[(o, m_dest)] / pp if pp > 0 else 1.0
    regla = regla_recuperacion(datos, inst, o, m_star, politica)
    nl = math.ceil(q / L)
    # unidades terminadas al fallar (recorriendo los lotes)
    t, k, lote_actual, en_setup = transcurrido, 0, 0, True
    for l in range(nl):
        n = min(L, q - l * L)
        lote_actual = l
        if t < s - 1e-12:
            en_setup = True
            break
        t -= s
        if u_star <= 0:          # POR_LOTE: el ciclo es la preparación fija; el lote no se completa a medias
            k += n if t >= 0 and l < nl - 1 else 0
            en_setup = False
            if l == nl - 1:
                break
            continue
        hechas = min(n, int(math.floor(t / u_star + 1e-9)))
        if hechas < n:
            k += hechas
            en_setup = False
            break
        k += n
        t -= n * u_star
    k = min(k, q - 1) if q > 0 else 0
    if regla["reinicia"] == 1 or regla["conserva"] == 0 or op["trato"] == "POR_LOTE":
        return round(inst.p[(o, m_dest)], 6), k, k
    rep = regla["repetir"]
    try:
        rep_extra = int(rep)
    except (TypeError, ValueError):
        rep_extra = 0
    rest_units = q - k                      # incluye la pieza en curso, que se repite completa
    lotes_pend = nl - lote_actual - 1        # lotes aún no iniciados
    setup_rep = 1 if (regla["repite_setup"] == 1 or m_dest != m_star or en_setup) else 0
    h = (rest_units * u_star + (lotes_pend + setup_rep) * s) * fac + regla["verif_min"] / 60.0
    piezas_reproc = (1 if (not en_setup and rep_extra >= 1) else 0)
    return round(h, 6), k, piezas_reproc


def subproblema_inicial(inst, jobs=None):
    jobs = list(range(len(inst.jobs))) if jobs is None else jobs
    free = [o for j in jobs for o in inst.job_ops[j]]
    lb = {o: inst.jobs[inst.ops[o]["job"]]["r"] for o in free}
    return Subproblema(inst=inst, t0=0.0, free=free, eligR={o: list(inst.elig[o]) for o in free},
                       pR={(o, m): inst.p[(o, m)] for o in free for m in inst.elig[o]}, lbR=lb,
                       mavail={m: 0.0 for m in inst.machines}, fixed={}, pending=list(free), jobs=list(jobs))


def particionar(datos, inst, programa, t0, jobs, ventanas, politica="A", pR_actual=None, congelar_h=0.0):
    """Construye el subproblema en t0.

    congelar_h: horizonte congelado H. Una operación pendiente que empieza antes de t0 + H se mantiene fija
    (decisión congelada) si su recurso no tiene indisponibilidad que la cruce y su predecesora también es fija.

    programa: {o: (m, S, C)} programa vigente de las operaciones de 'jobs' ya programadas.
    ventanas: lista (m, a, b) de indisponibilidad; una ventana con a <= t0 < b vuelve 'interrumpida'
              la operación que se procesaba en m en t0 y hace m disponible recién en b.
    pR_actual: {(o,m): h} tiempos vigentes (p. ej. restantes de interrupciones anteriores).
    Las operaciones de 'jobs' sin programa (pedidos recién llegados) entran como pendientes sin S0.
    """
    pR_actual = pR_actual or {}
    activas = [(m, a, b) for (m, a, b) in ventanas if b > t0 + EPS]
    caidas = {m: b for (m, a, b) in activas if a <= t0 + EPS}
    # Una ventana futura (mantenimiento anunciado) no interrumpe la operación que ya está en curso en esa máquina:
    # se posterga hasta que esa operación termine (misma duración). Así ninguna operación fija se cruza con ella.
    ajustadas = []
    for (m, a, b) in activas:
        if a > t0 + EPS:
            fin_curso = max([C for j in jobs for o in inst.job_ops[j] if o in programa
                             for (mm, S, C) in [programa[o]] if mm == m and S < t0 - EPS and C > t0 + EPS] + [a])
            if fin_curso > a + EPS:
                b, a = b + (fin_curso - a), fin_curso
        ajustadas.append((m, a, b))
    activas = ajustadas
    futuras = [(m, a, b) for (m, a, b) in activas if a > t0 + EPS]
    fixed, free, pending, interrupted = {}, [], [], []
    info = {}
    for j in jobs:
        for o in inst.job_ops[j]:
            if o not in programa:
                free.append(o); pending.append(o)
                continue
            m, S, C = programa[o]
            if C <= t0 + EPS:
                fixed[o] = (m, S, C)
            elif S < t0 - EPS:
                if m in caidas:
                    free.append(o); interrupted.append(o)
                    info[o] = dict(transcurrido=t0 - S, S_orig=S, C_orig=C, m_star=m)
                else:
                    fixed[o] = (m, S, C)
            else:
                pr = inst.pred(o)
                congelable = (congelar_h > EPS and S < t0 + congelar_h - EPS and m not in caidas
                              and (pr is None or pr in fixed)
                              and not any(mm == m and a < C - EPS and S < b - EPS for (mm, a, b) in activas))
                if congelable:
                    fixed[o] = (m, S, C)
                    info.setdefault("_congeladas", []).append(o)
                else:
                    free.append(o); pending.append(o)
    congeladas = info.pop("_congeladas", [])
    eligR, pR, lbR, unidades = {}, {}, {}, {}
    for o in free:
        eligR[o] = list(inst.elig[o])
        for m in eligR[o]:
            if o in info:
                # tiempo restante: se descuenta lo ya procesado en la máquina caída
                base_p = pR_actual.get((o, info[o]["m_star"]), inst.p[(o, info[o]["m_star"])])
                h, k, rep = tiempo_restante(datos, inst, o, info[o]["m_star"],
                                            info[o]["transcurrido"] + (inst.p[(o, info[o]["m_star"])] - base_p),
                                            politica, m)
                pR[(o, m)] = h
                unidades[o] = (k, rep)
            else:
                pR[(o, m)] = pR_actual.get((o, m), inst.p[(o, m)])
    for o in free:
        j = inst.ops[o]["job"]
        lb = max(t0, inst.jobs[j]["r"])
        pr = inst.pred(o)
        if pr is not None and pr in fixed:
            lb = max(lb, fixed[pr][2])
        lbR[o] = lb
    mavail = {}
    for m in inst.machines:
        a = t0
        for o, (mm, S, C) in fixed.items():
            if mm == m and C > a:
                a = C
        if m in caidas:
            a = max(a, caidas[m])
        mavail[m] = a
    # máquinas ocupadas por operaciones fijas de pedidos fuera del subproblema se pasan vía 'externos'
    S0 = {o: programa[o][1] for o in free if o in programa}
    m0 = {o: programa[o][0] for o in free if o in programa}
    for o in info:
        info[o]["unidades"] = unidades.get(o)
    return Subproblema(inst=inst, t0=t0, free=sorted(free), eligR=eligR, pR=pR, lbR=lbR, mavail=mavail, fixed=fixed,
                       windows=futuras, all_windows=activas, S0=S0, m0=m0, congeladas=congeladas,
                       pending=[o for o in pending if o in S0], interrupted=interrupted, info=info, jobs=list(jobs))


def ocupar_externos(sub, ocupacion):
    """Añade a mavail la ocupación de máquinas por operaciones fijas ajenas al subproblema {m: fin}."""
    for m, c in ocupacion.items():
        if c > sub.mavail.get(m, sub.t0):
            sub.mavail[m] = c
    return sub
