"""Procedimiento de solución único: optimización lexicográfica con verificación independiente.

Para las fases (f_1, f_2, ..., f_K) de `ModeloMILP.fases()`:
    fase k:  min f_k   s.a.  restricciones del modelo  y  f_i ≤ f_i* (1 + τ) + ε  para i < k
Cada fase se resuelve con HiGHS (API pública de SciPy). El valor f_k* que se fija es el de la solución
obtenida (óptima demostrada o incumbente al límite de tiempo); el estado global solo es ÓPTIMO si TODAS
las fases lo son. Una solución de regla verificada (EDD o reacción convencional) sirve de respaldo si HiGHS
no devuelve solución o devuelve una peor; en ese caso el estado es HEURISTICA_VERIFICADA, nunca ÓPTIMO.

Reemplaza las tres implementaciones de v1.4 (optimizacion.lexicografico, rodante_personal.resolver_lex y
la función interna del programa principal).
"""
from __future__ import annotations

import math

from . import reglas
from .modelo.milp import ModeloMILP
from .solver import INF, Estado, solve, validar_vector
from .verificacion import verificar_subproblema

EPS_CAP = 1e-4


def _valor(terms, xv):
    return float(sum(c * xv[v] for v, c in terms))


def mejor_heuristica(sub, clave):
    """Mejor solución de regla factible (CONV / EDD) según la función `clave(sol)` (menor es mejor)."""
    cands = []
    for nombre, f in (("CONV", reglas.convencional), ("EDD", reglas.edd)):
        try:
            s = f(sub)
        except (RuntimeError, ValueError):
            continue
        if not verificar_subproblema(sub, s):
            cands.append((clave(s), nombre, s))
    cands.sort(key=lambda c: c[0])
    return (cands[0][2], cands[0][1]) if cands else (None, None)


def resolver_lexicografico(mdl, tl=60.0, gap=1e-5, tau=1e-6, respaldo=None, presolve=True):
    M = mdl.M
    fases = mdl.fases()
    pasos, xv, origen = [], None, None
    vec_resp = None
    if respaldo is not None:
        v = mdl.encode(respaldo)
        if not validar_vector(M, v):
            vec_resp = v
    for k, (nombre, terms) in enumerate(fases):
        M.set_objective(terms)
        r = solve(M, time_limit=tl, rel_gap=gap, presolve=presolve)
        estado, x = r["estado"], r["x"]
        obj = r["obj"]
        if vec_resp is not None:
            obj_r = _valor(terms, vec_resp)
            if x is None or obj_r < obj - 1e-6 * max(1.0, abs(obj_r)):
                x, obj, estado = vec_resp, obj_r, Estado.HEURISTICA   # nunca se certifica una solución de regla
        pasos.append(dict(fase=nombre, estado=estado, objetivo=obj, cota=r.get("bound"), brecha=r.get("gap"),
                          tiempo_s=r["time"], nodos=r.get("nodes"), variables=r["nvar"], restricciones=r["nrow"],
                          enteras=r["nbin"]))
        if x is None:
            break
        xv = x
        cap = obj * (1 + tau) + EPS_CAP if obj >= 0 else obj + EPS_CAP
        M.row(terms, -INF, cap)
        if vec_resp is not None and _valor(terms, vec_resp) > cap:
            vec_resp = None                    # el respaldo ya no cumple la cota de esta fase
    if xv is None:
        primero = pasos[0]["estado"] if pasos else Estado.ERROR
        return dict(sol=None, pasos=pasos, estado_global=primero, certificado=False, tamano=mdl.tamano())
    sol = mdl.decode(xv)
    estados = [p["estado"] for p in pasos]
    if len(pasos) < len(fases):
        global_ = Estado.FACTIBLE_LIMITE
    elif all(e == Estado.OPTIMO for e in estados):
        global_ = Estado.OPTIMO
    elif any(e == Estado.HEURISTICA for e in estados):
        global_ = Estado.HEURISTICA
    else:
        global_ = Estado.FACTIBLE_LIMITE
    return dict(sol=sol, pasos=pasos, estado_global=global_, certificado=global_ == Estado.OPTIMO, tamano=mdl.tamano(),
                xv=xv)


def optimizar(sub, beta=8.0, regla_objetivo="TARDANZA_PONDERADA", tl=60.0, gap=1e-5, tau=1e-6, estabilidad=True,
              compactar=None, horas_dia=8.0, personal=None, presolve=True):
    """Construye el MILP del subproblema, lo resuelve lexicográficamente y post-procesa sin empeorar objetivos.

    compactar: True → programa semiactivo (adelanta sin cambiar secuencias; no empeora objetivos regulares);
               por defecto se compacta solo cuando no hay programa vigente (pedidos nuevos).
    personal:  EstadoPersonal cuando NO hay certificado de cobertura laboral; el programa del solver se repara
               (mismas asignaciones y secuencias, solo retrasos) hasta que haya trabajadores habilitados libres.
               Si la reparación cambia algún objetivo, el estado final es HEURISTICA_VERIFICADA (no óptimo).
    """
    mdl = ModeloMILP(sub, beta=beta, regla_objetivo=regla_objetivo, estabilidad=estabilidad, horas_dia=horas_dia)
    primera = mdl.fases()[0][1]

    def clave(s):
        return _valor(primera, mdl.encode(s))

    respaldo, nombre_resp = mejor_heuristica(sub, clave)
    out = resolver_lexicografico(mdl, tl=tl, gap=gap, tau=tau, respaldo=respaldo, presolve=presolve)
    out["mdl"] = mdl
    out["respaldo"] = nombre_resp
    out["reparacion_laboral"] = False
    if out["sol"] is None:
        return out
    if compactar is None:
        compactar = not sub.S0
    if personal is not None:
        sol_m = reglas.semiactivo(sub, out["sol"]) if compactar else reglas.reparar(sub, out["sol"])
        sol = reglas.semiactivo(sub, out["sol"], personal) if compactar else reglas.reparar(sub, out["sol"], personal)
        v_fin, v_m = mdl.encode(sol), mdl.encode(sol_m)
        cambia = any(abs(_valor(t, v_fin) - _valor(t, v_m)) > 1e-6 * max(1.0, abs(_valor(t, v_m))) + 1e-6
                     for _, t in mdl.fases())
        out["reparacion_laboral"] = cambia
        out["coherente"] = True
        if cambia:
            out["estado_maquinas"] = out["estado_global"]
            out["estado_global"] = Estado.HEURISTICA
            out["certificado"] = False
    else:
        sol = reglas.semiactivo(sub, out["sol"]) if compactar else reglas.reparar(sub, out["sol"])
        # coherencia lexicográfica: el post-proceso no debe empeorar ninguna fase
        v_fin = mdl.encode(sol)
        v_opt = out["xv"]
        coherente = all(_valor(t, v_fin) <= _valor(t, v_opt) * (1 + 1e-6) + 1e-3 for _, t in mdl.fases())
        if not coherente:          # nunca debería ocurrir; se conserva la solución del solver tal cual
            sol = out["sol"]
        out["coherente"] = coherente
    out["sol"] = sol
    out["objetivos"] = {n: _valor(t, mdl.encode(sol)) for n, t in mdl.fases()}
    if "P3_estabilidad" in out["objetivos"]:
        out["objetivos"]["P3_estabilidad"] += mdl.f_estabilidad_const()
    return out
