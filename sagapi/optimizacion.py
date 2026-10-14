"""Procedimiento de solución: optimización lexicográfica y ε-restricción aumentada.

Lexicográfico (P1 → P2 → P3):
  P1  min f1 (penalidad)
  P2  min f1b (tardanza ponderada)      s.a. f1 ≤ f1*
  P3  min f2 (inestabilidad)            s.a. f1 ≤ f1*, f1b ≤ f1b*·(1+τ)   (sólo en reprogramación)
En la programación de pedidos nuevos (sin programa previo) P3 se omite y el programa se compacta
(semiactivo), lo que no empeora f1 ni f1b.

ε-restricción aumentada (frente f1b–f2 con f1 = f1*):
  min f2 − ρ·(holgura normalizada)  ≡  min f2 + ρ·f1b/rango   s.a. f1 ≤ f1*, f1b ≤ ε_k
"""
from __future__ import annotations
import numpy as np
from .modelo import ModeloMILP
from .solver import solve, solve_robusto, validar_vector, INF
from . import reglas
from .verificacion import verificar


def _resolver(mdl, terms, tl, warm_sol=None, extra=(), gap=1e-5):
    """Fija el objetivo, añade filas temporales y resuelve. Control de consistencia: si existe una
    solución de arranque factible y HiGHS devuelve una solución peor o ninguna, se reintenta con la
    resolución sin arranque y, si persiste, se conserva la solución de arranque (se registra)."""
    M = mdl.M
    n_rows = M.nrow
    n_nz = len(M.rows)
    for t, lo, hi in extra:
        M.row(t, lo, hi)
    M.set_objective(terms)
    warm = None
    w_obj = None
    if warm_sol is not None:
        warm = mdl.encode(warm_sol)
        w_obj = float(sum(c * warm[v] for v, c in terms))
    res = solve_robusto(M, time_limit=tl, warm=warm, rel_gap=gap)
    tol = 1e-6 * max(1.0, abs(w_obj)) if w_obj is not None else 0
    if w_obj is not None and not validar_vector(M, warm) and (res["x"] is None or res["obj"] > w_obj + tol):
        # Una heurística puede ser factible sin ser óptima; nunca certificar este respaldo.
        res = dict(res, x=warm, obj=w_obj, status="Feasible (validated heuristic fallback)",
                   consistencia="solución heurística verificada", certificado=False, acuerdo=None,
                   gap=None, bound=None)
    del M.rows[n_nz:], M.cols[n_nz:], M.vals[n_nz:]
    del M.rlo[n_rows:], M.rhi[n_rows:]
    M.nrow = n_rows
    sol = mdl.decode(res["x"]) if res["x"] is not None else None
    return res, sol


def _val(terms, xv):
    return float(sum(c * xv[v] for v, c in terms))


def mejor_heuristica(sub):
    """Solución inicial: la mejor (f1, f1b) entre la reacción convencional y EDD."""
    from .indicadores import evaluar
    cands = []
    for nombre, f in (("CONV", reglas.convencional), ("EDD", reglas.edd)):
        try:
            s = f(sub)
            if not verificar(sub, s):
                k = evaluar(sub, s)
                cands.append(((k["penalidad"], k["tard_pond"]), nombre, s))
        except Exception:
            pass
    cands.sort(key=lambda c: c[0])
    return (cands[0][2], cands[0][1]) if cands else (None, None)


def lexicografico(sub, beta=8.0, regla_pen="FIJA", tl=(60, 60, 60), estabilidad=True, warm=None, tau=1e-6):
    mdl = ModeloMILP(sub, beta=beta, regla_pen=regla_pen, estabilidad=estabilidad)
    if warm is None:
        warm, _ = mejor_heuristica(sub)
    out = dict(tamano=mdl.tamano(), pasos=[])
    # P1
    r1, s1 = _resolver(mdl, mdl.f1_terms(), tl[0], warm)
    out["pasos"].append(_resumen("P1 min f1", r1))
    if s1 is None:
        out["sol"] = None
        return out
    f1v = r1["obj"]
    cap1 = f1v + max(1e-4, 1e-7 * abs(f1v))
    # P2
    r2, s2 = _resolver(mdl, mdl.f1b_terms(), tl[1], s1, [(mdl.f1_terms(), -INF, cap1)])
    out["pasos"].append(_resumen("P2 min f1b | f1<=f1*", r2))
    if s2 is None:
        s2, r2 = s1, r1
    sol = s2
    f1bv = _val(mdl.f1b_terms(), mdl.encode(s2))
    if estabilidad and sub.S0:
        cap2 = f1bv * (1 + tau) + 1e-4
        r3, s3 = _resolver(mdl, mdl.f2_terms(), tl[2], s2,
                           [(mdl.f1_terms(), -INF, cap1), (mdl.f1b_terms(), -INF, cap2)])
        out["pasos"].append(_resumen("P3 min f2 | f1<=f1*, f1b<=f1b*", r3))
        if s3 is not None:
            sol = s3
        sol = reglas.reparar(sub, sol)
    else:
        sol = reglas.semiactivo(sub, reglas.reparar(sub, sol))
    out["sol"] = sol
    out["mdl"] = mdl
    out["optimo_P1"] = out["pasos"][0]["estado"] == "Optimal"
    todos_opt = all(p["estado"] == "Optimal" for p in out["pasos"])
    # coherencia lexicográfica: la solución final conserva f1* y f1b*
    xv = mdl.encode(sol)
    f1_fin, f1b_fin = _val(mdl.f1_terms(), xv), _val(mdl.f1b_terms(), xv)
    out["f1_final"], out["f1b_final"] = f1_fin, f1b_fin
    coherente = f1_fin <= cap1 + 1e-6 and f1b_fin <= f1bv * (1 + tau) + 1e-3 + 1e-6
    out["coherente"] = coherente
    out["certificado"] = all(p.get("certificado", False) for p in out["pasos"])
    out["estado_global"] = _estado(out["pasos"], out["certificado"] and coherente) if sol is not None else "SIN SOLUCIÓN"
    return out


def mono(sub, regla_pen="FIJA", tl=(60, 60), warm=None):
    """MILP sin criterio de estabilidad (P1 → P2), para aislar el efecto de f2."""
    return lexicografico(sub, regla_pen=regla_pen, tl=(tl[0], tl[1], 0), estabilidad=False, warm=warm) \
        if not sub.S0 else _mono_reactivo(sub, regla_pen, tl, warm)


def _mono_reactivo(sub, regla_pen, tl, warm):
    mdl = ModeloMILP(sub, regla_pen=regla_pen, estabilidad=False)
    if warm is None:
        warm, _ = mejor_heuristica(sub)
    out = dict(tamano=mdl.tamano(), pasos=[])
    r1, s1 = _resolver(mdl, mdl.f1_terms(), tl[0], warm)
    out["pasos"].append(_resumen("P1 min f1", r1))
    if s1 is None:
        out["sol"] = None
        return out
    cap1 = r1["obj"] + max(1e-4, 1e-7 * abs(r1["obj"]))
    r2, s2 = _resolver(mdl, mdl.f1b_terms(), tl[1], s1, [(mdl.f1_terms(), -INF, cap1)])
    out["pasos"].append(_resumen("P2 min f1b | f1<=f1*", r2))
    sol = s2 if s2 is not None else s1
    out["sol"] = reglas.reparar(sub, sol)
    todos_opt = all(p["estado"] == "Optimal" for p in out["pasos"])
    ok = all(p.get("certificado", False) for p in out["pasos"])
    out["certificado"] = ok
    out["estado_global"] = _estado(out["pasos"], ok)
    return out


def epsilon(sub, f1_opt, f1b_min, f1b_max, n=7, beta=8.0, regla_pen="FIJA", tl=30, warm=None, rho=1e-4):
    """Frente aproximado f1b–f2 con f1 ≤ f1*: min f2 + ρ·f1b/rango  s.a. f1b ≤ ε_k."""
    mdl = ModeloMILP(sub, beta=beta, regla_pen=regla_pen, estabilidad=True)
    cap1 = f1_opt + max(1e-4, 1e-7 * abs(f1_opt))
    rango = max(1.0, f1b_max - f1b_min)
    pts = []
    last = warm
    for k, eps in enumerate(np.linspace(f1b_min, f1b_max, n)):
        terms = mdl.f2_terms() + [(v, rho * c / rango) for v, c in mdl.f1b_terms()]
        r, s = _resolver(mdl, terms, tl, last, [(mdl.f1_terms(), -INF, cap1), (mdl.f1b_terms(), -INF, eps + 1e-4)])
        if s is not None:
            s = reglas.reparar(sub, s)
            last = s
        pts.append(dict(k=k, eps=float(eps), estado=r["status"], brecha=r["gap"], tiempo=r["time"], sol=s))
    return pts


def _estado(pasos, certificado):
    """ÓPTIMO solo si el solucionador certifica cada paso y no hay pérdida lexicográfica.
    Un resultado de límite de tiempo es FACTIBLE, aunque tenga solución incumbente."""
    if not all(str(p["estado"]).startswith("Optimal") for p in pasos):
        return "FACTIBLE (límite de tiempo)"
    return "ÓPTIMO" if certificado else "FACTIBLE (no certificado)"


def _resumen(nombre, r):
    return dict(paso=nombre, estado=r["status"], obj=r["obj"], cota=r.get("bound"), brecha=r.get("gap"),
                tiempo=r["time"], nodos=r.get("nodes"), respaldo=r.get("fallback"), consistencia=r.get("consistencia"),
                acuerdo=r.get("acuerdo"), certificado=r.get("certificado", False),
                backend=r.get("backend"), configuraciones=r.get("configuraciones"))
