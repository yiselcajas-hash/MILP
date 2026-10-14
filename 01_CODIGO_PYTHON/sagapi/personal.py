"""Personal: dotación, certificado de cobertura, reparación laboral y asignación de trabajadores.

La dotación agregada (25 trabajadores, un turno de 8 h) es un dato de la empresa; las HABILIDADES individuales
son SIMULADAS (22_HABILIDADES_SIM) mientras no se cargue la matriz real (16_REG_HABILIDADES con
fuente_habilidades = REAL). Ningún resultado de este módulo debe leerse como verificación en planta.

Tres piezas, en orden de uso:

1. ``certificado_cobertura`` — condición SUFICIENTE (no necesaria) de factibilidad laboral. Se busca, mediante un
   flujo máximo, asignar a cada unidad de recurso m un equipo fijo de b_m trabajadores distintos y habilitados
   (b_m = mayor dotación c_o requerida en m). Si existe, todo programa que respete la capacidad de las unidades
   (a lo sumo una operación por unidad a la vez) es atendible: el equipo de m nunca está en dos sitios, y como el
   eje de tiempo solo contiene horas de jornada, ningún trabajador supera 8 h por día. En ese caso las
   restricciones laborales son redundantes y no se agregan al MILP (reducción de tamaño demostrable).
2. ``EstadoPersonal`` — si el certificado falla (p. ej. escenario con ausencias), las reglas y la reparación del
   programa MILP reservan trabajadores intervalo a intervalo (``primer_inicio`` / ``reservar``). El resultado es
   factible por construcción pero HEURÍSTICO (no se declara óptimo).
3. ``asignar_trabajadores`` — dado un programa factible, MILP de asignación q_ow ∈ {0,1}:
       Σ_{w ∈ W_o} q_ow = c_o                         (L1 dotación de cada intervalo)
       Σ_{o ∈ K} q_ow ≤ 1   ∀ w, ∀ clique maximal K de intervalos solapados elegibles para w   (L3 sin solape)
       H_w = Σ_o p_o q_ow ≤ H_max ;  H_w ≥ H_min           (carga total por trabajador)
   Fases lexicográficas: min H_max; luego max H_min (equilibrio). Las cliques maximales de un grafo de
   intervalos se obtienen con un barrido, de modo que L3 es exacta (no una relajación).
"""
from __future__ import annotations

import bisect
from collections import defaultdict, deque
from dataclasses import dataclass, field

from .instancia import recurso_base
from .solver import INF, Estado, LinModel, solve
from .verificacion import TOL, intervalos_trabajo, verificar_personal


@dataclass
class Dotacion:
    trabajadores: list
    habilidades: dict                 # trabajador -> {recurso base}
    ausentes: set = field(default_factory=set)
    fuente: str = "SIMULADA"

    def disponibles(self):
        return [w for w in self.trabajadores if w not in self.ausentes]

    def habilitados(self, recurso):
        rb = recurso_base(recurso)
        return [w for w in self.disponibles() if rb in self.habilidades.get(w, ())]


def dotacion(datos, ausentes=()):
    fuente = str(datos.parametros.get("fuente_habilidades") or "SIMULADA")
    return Dotacion(list(datos.operarios), {w: set(s) for w, s in datos.habilidades.items()}, set(ausentes), fuente)


# ------------------------------------------------------------------------------------------ 1. certificado
def _flujo_maximo(cap, s, t):
    """Edmonds–Karp sobre un diccionario de capacidades {u: {v: c}}; devuelve (valor, flujo)."""
    flujo = defaultdict(lambda: defaultdict(int))
    valor = 0
    while True:
        padre = {s: None}
        q = deque([s])
        while q and t not in padre:
            u = q.popleft()
            for v, c in cap[u].items():
                if v not in padre and c - flujo[u][v] > 0:
                    padre[v] = u
                    q.append(v)
        if t not in padre:
            return valor, flujo
        v, f = t, INF
        while padre[v] is not None:
            u = padre[v]
            f = min(f, cap[u][v] - flujo[u][v])
            v = u
        v = t
        while padre[v] is not None:
            u = padre[v]
            flujo[u][v] += f
            flujo[v][u] -= f
            v = u
        valor += f


def certificado_cobertura(dot, inst, unidades=None):
    """Asignación fija unidad → equipo de b_m trabajadores distintos y habilitados (flujo máximo).

    Devuelve dict(ok, equipos {unidad: [trabajadores]}, demanda, cubierto, deficit {unidad: n}, sin_personal).
    """
    usadas = sorted({m for o in range(len(inst.ops)) for m in inst.elig[o]}) if unidades is None else sorted(unidades)
    b = defaultdict(int)
    for o, op in enumerate(inst.ops):
        for m in inst.elig[o]:
            if m in usadas:
                b[m] = max(b[m], int(op.get("crew", 1)))
    cap = defaultdict(dict)
    S, T = "__s__", "__t__"
    for m in usadas:
        cap[S][("U", m)] = b[m]
        for w in dot.habilitados(m):
            cap[("U", m)][("W", w)] = 1
            cap[("W", w)].setdefault(T, 1)
            cap[("W", w)].setdefault(("U", m), 0)
        cap[("U", m)].setdefault(S, 0)
    for w in dot.disponibles():
        cap[T].setdefault(("W", w), 0)
    valor, flujo = _flujo_maximo(cap, S, T)
    equipos = {m: sorted(v[1] for v in cap[("U", m)] if isinstance(v, tuple) and v[0] == "W"
                         and flujo[("U", m)][v] > 0) for m in usadas}
    deficit = {m: b[m] - len(equipos[m]) for m in usadas if len(equipos[m]) < b[m]}
    demanda = sum(b[m] for m in usadas)
    return dict(ok=valor == demanda, equipos=equipos, demanda=demanda, cubierto=valor, deficit=deficit,
                sin_personal=[m for m in usadas if not dot.habilitados(m)], trabajadores_disponibles=len(dot.disponibles()),
                fuente_habilidades=dot.fuente)


# ------------------------------------------------------------------------------------------ 2. reparación
class EstadoPersonal:
    """Reservas de trabajadores por intervalos (para reglas y reparación cuando no hay certificado).

    Elige, entre los habilitados libres, a los de menor carga acumulada (equilibrio heurístico).
    """

    def __init__(self, dot, horas_dia=8.0):
        self.dot = dot
        self.h_dia = horas_dia
        self.ocupado = defaultdict(list)       # w -> lista ordenada de (S, C)
        self.carga = defaultdict(float)
        self.asignacion = {}                   # o -> [w]

    def copia(self):
        n = EstadoPersonal(self.dot, self.h_dia)
        n.ocupado = defaultdict(list, {w: list(v) for w, v in self.ocupado.items()})
        n.carga = defaultdict(float, self.carga)
        n.asignacion = {o: list(v) for o, v in self.asignacion.items()}
        return n

    def _libre(self, w, S, C):
        lst = self.ocupado[w]
        i = bisect.bisect_left(lst, (S, -INF))
        if i > 0 and lst[i - 1][1] > S + TOL:
            return False
        return not (i < len(lst) and lst[i][0] < C - TOL)

    def libres(self, S, C, m):
        return [w for w in self.dot.habilitados(m) if self._libre(w, S, C)]

    def primer_inicio(self, t, p, m, crew=1):
        """Menor s ≥ t con al menos `crew` trabajadores habilitados para m libres en [s, s + p)."""
        hab = self.dot.habilitados(m)
        if len(hab) < crew:
            raise RuntimeError(f"no hay {crew} trabajador(es) habilitado(s) y disponible(s) para {recurso_base(m)}")
        cands = {t}
        for w in hab:
            for (S, C) in self.ocupado[w]:
                if C > t:
                    cands.add(C)
        for s in sorted(cands):
            if sum(1 for w in hab if self._libre(w, s, s + p)) >= crew:
                return s
        raise RuntimeError("primer_inicio: no se encontró hueco (no debería ocurrir)")

    def reservar(self, o, S, C, m, crew=1, trabajadores=None):
        ws = trabajadores or sorted(self.libres(S, C, m), key=lambda w: (self.carga[w], w))[:crew]
        if len(ws) < crew:
            raise RuntimeError(f"reservar: personal insuficiente para la operación {o} en [{S:.2f}, {C:.2f})")
        for w in ws:
            bisect.insort(self.ocupado[w], (S, C))
            self.carga[w] += C - S
        self.asignacion[o] = list(ws)
        return ws


def estado_desde_programa(dot, inst, programa, asignacion=None, horas_dia=8.0, parciales=()):
    """Reconstruye las reservas de las operaciones ya fijadas (con su asignación si se conoce)."""
    est = EstadoPersonal(dot, horas_dia)
    asignacion = asignacion or {}
    for clave, o, m, S, C in sorted(intervalos_trabajo(programa, parciales), key=lambda x: (x[3], x[1])):
        ws = asignacion.get(clave) or asignacion.get(o)
        est.reservar(clave if clave[0] == "P" else o, S, C, m, int(inst.ops[o].get("crew", 1)), trabajadores=ws)
    return est


# ------------------------------------------------------------------------------------------ 3. asignación MILP
def _cliques_maximales(intervalos):
    """intervalos [(S, C, i)] → lista de cliques maximales (conjuntos de i) del grafo de intervalos (barrido)."""
    ev = []
    for S, C, i in intervalos:
        ev.append((S, 1, i))
        ev.append((C, 0, i))          # a igual instante, los finales se procesan antes que los inicios
    ev.sort(key=lambda e: (e[0], e[1]))
    activos, cliques, crecio = set(), [], False
    k = 0
    while k < len(ev):
        t = ev[k][0]
        # procesar todos los finales en t (con tolerancia) y luego todos los inicios en t
        fin_grupo = k
        while fin_grupo < len(ev) and ev[fin_grupo][0] <= t + TOL:
            fin_grupo += 1
        finales = [e for e in ev[k:fin_grupo] if e[1] == 0]
        inicios = [e for e in ev[k:fin_grupo] if e[1] == 1]
        if finales:
            if crecio and len(activos) > 1:
                cliques.append(frozenset(activos))
            crecio = False
            for _, _, i in finales:
                activos.discard(i)
        for _, _, i in inicios:
            activos.add(i)
            crecio = True
        k = fin_grupo
    if crecio and len(activos) > 1:
        cliques.append(frozenset(activos))
    return cliques


def asignar_trabajadores(inst, programa, dot, parciales=(), tl=120.0, gap=1e-4, equilibrar=True, respaldo=None,
                         horas_dia=8.0):
    """MILP de asignación de trabajadores sobre un programa fijo; devuelve dict con asignación, estado y cargas.

    respaldo: asignación factible conocida {clave: [w]} (p. ej. la de la reparación laboral) usada si HiGHS no
    devuelve solución en el límite de tiempo (estado HEURISTICA_VERIFICADA).
    """
    ints = intervalos_trabajo(programa, parciales)
    M = LinModel()
    q = {}
    dur = {}
    for clave, o, m, S, C in ints:
        dur[clave] = C - S
        hab = dot.habilitados(m)
        c = int(inst.ops[o].get("crew", 1))
        if len(hab) < c:
            return dict(estado=Estado.INFACTIBLE, asignacion=None, motivo=f"{inst.op_label(o)}: sin {c} trabajador(es) habilitado(s)",
                        cargas={}, pasos=[])
        for w in hab:
            q[(clave, w)] = M.var(f"q[{clave},{w}]", 0, 1, integer=True)
        M.row([(q[(clave, w)], 1.0) for w in hab], c, c)
    Hmax = M.var("Hmax", 0.0, INF)
    Hmin = M.var("Hmin", 0.0, INF)
    trab = dot.disponibles()
    por_w = defaultdict(list)
    for clave, o, m, S, C in ints:
        for w in dot.habilitados(m):
            por_w[w].append((S, C, clave))
    n_cliques = 0
    for w in trab:
        for K in _cliques_maximales(por_w[w]):
            M.row([(q[(k, w)], 1.0) for k in K], -INF, 1.0)
            n_cliques += 1
        terms = [(q[(k, w)], dur[k]) for (_, _, k) in por_w[w]]
        M.row(terms + [(Hmax, -1.0)], -INF, 0.0)
        if equilibrar:
            M.row(terms + [(Hmin, -1.0)], 0.0, INF)
    pasos = []
    fases = [("L_max_carga", [(Hmax, 1.0)])]
    if equilibrar:
        fases.append(("L_min_carga", [(Hmin, -1.0)]))
    x = None
    estados = []
    for nombre, terms in fases:
        M.set_objective(terms)
        r = solve(M, time_limit=tl, rel_gap=gap)
        pasos.append(dict(fase=nombre, estado=r["estado"], objetivo=r["obj"], brecha=r.get("gap"), tiempo_s=r["time"],
                          variables=r["nvar"], restricciones=r["nrow"], enteras=r["nbin"]))
        estados.append(r["estado"])
        if r["x"] is None:
            break
        x = r["x"]
        M.row(terms, -INF, r["obj"] + 1e-6 * max(1.0, abs(r["obj"])) + 1e-6)
    if x is None:
        if respaldo is not None:
            asign = respaldo
            estado = Estado.HEURISTICA
        else:
            return dict(estado=estados[0] if estados else Estado.ERROR, asignacion=None, cargas={}, pasos=pasos,
                        cliques=n_cliques)
    else:
        asign = defaultdict(list)
        for (clave, w), v in q.items():
            if x[v] > 0.5:
                asign[clave].append(w)
        asign = dict(asign)
        estado = Estado.OPTIMO if all(e == Estado.OPTIMO for e in estados) and len(estados) == len(fases) \
            else Estado.FACTIBLE_LIMITE
    viol = verificar_personal(inst, programa, parciales, asign, dot.habilidades, dot.ausentes, horas_dia)
    cargas = defaultdict(float)
    for clave, o, m, S, C in ints:
        for w in asign.get(clave, []):
            cargas[w] += C - S
    for w in trab:
        cargas.setdefault(w, 0.0)
    return dict(estado=estado, asignacion=asign, cargas=dict(cargas), pasos=pasos, cliques=n_cliques,
                violaciones=viol, variables=M.nvar, restricciones=M.nrow)


def asignacion_por_equipos(inst, programa, certificado, parciales=()):
    """Asignación trivial derivada del certificado (cada unidad con su equipo fijo); factible por construcción."""
    asign = {}
    for clave, o, m, S, C in intervalos_trabajo(programa, parciales):
        c = int(inst.ops[o].get("crew", 1))
        asign[clave] = certificado["equipos"][m][:c]
    return asign


def resumen_cargas(cargas, horas_disponibles):
    """Indicadores de carga laboral: total, máxima, mínima, coeficiente de variación y utilización media."""
    import statistics
    vals = list(cargas.values())
    if not vals:
        return {}
    media = statistics.fmean(vals)
    return dict(trabajadores=len(vals), horas_total=sum(vals), horas_max=max(vals), horas_min=min(vals),
                horas_media=media, cv=(statistics.pstdev(vals) / media) if media > 0 else 0.0,
                utilizacion_media_pct=100 * media / horas_disponibles if horas_disponibles > 0 else None,
                horas_disponibles_por_trabajador=horas_disponibles)
