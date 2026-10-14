"""Modelo algebraico y resolución MILP con la API pública de SciPy/HiGHS.

Verifica independientemente dominios, integridad y restricciones Ax en [lo,hi].
El arranque en caliente no está soportado en esta API. La exportación MPS usa una
interfaz opcional y debe comprobarse de forma separada.
"""
from __future__ import annotations
import time
import numpy as np
from scipy.sparse import coo_matrix

INF = float("inf")


class Estado:
    """Estados de solución que el sistema distingue expresamente (nunca se confunden)."""
    OPTIMO = "OPTIMO"                          # HiGHS cerró la brecha (≤ mip_rel_gap) y la solución pasó la verificación
    FACTIBLE_LIMITE = "FACTIBLE_LIMITE_TIEMPO"  # límite alcanzado con solución incumbente verificada (no óptima demostrada)
    SIN_SOLUCION_LIMITE = "SIN_SOLUCION_LIMITE_TIEMPO"
    INFACTIBLE = "INFACTIBLE"                  # HiGHS demostró que no existe solución
    NO_ACOTADO = "NO_ACOTADO"
    SOLUCION_INVALIDA = "SOLUCION_INVALIDA"    # el vector devuelto viola filas, cotas o integralidad
    ERROR = "ERROR_EJECUCION"
    HEURISTICA = "HEURISTICA_VERIFICADA"       # respaldo: solución de regla verificada (no óptima)

    CON_SOLUCION = (OPTIMO, FACTIBLE_LIMITE, HEURISTICA)


class LinModel:
    def __init__(self):
        self.lb, self.ub, self.integer, self.cost, self.names = [], [], [], [], []
        self.rows, self.cols, self.vals, self.rlo, self.rhi = [], [], [], [], []
        self.nrow = 0

    def var(self, name, lb=0.0, ub=INF, integer=False, cost=0.0):
        self.lb.append(lb); self.ub.append(ub); self.integer.append(integer)
        self.cost.append(cost); self.names.append(name)
        return len(self.lb) - 1

    def row(self, terms, lo=-INF, hi=INF):
        for v, c in terms:
            if c != 0.0:
                self.rows.append(self.nrow); self.cols.append(v); self.vals.append(float(c))
        self.rlo.append(lo); self.rhi.append(hi)
        self.nrow += 1

    def set_objective(self, terms):
        self.cost = [0.0] * len(self.lb)
        for v, c in terms:
            self.cost[v] += c

    @property
    def nvar(self):
        return len(self.lb)


def validar_vector(model, xv, tol=1e-5):
    """Comprobación algebraica independiente del estado emitido por el solucionador.

    Verifica dominios, integridad y las filas originales Ax en [lo, hi].
    Se utiliza incluso cuando HiGHS informa una solución óptima.
    """
    if xv is None:
        return ["no hay vector de solución"]
    x = np.asarray(xv, dtype=float)
    if x.shape != (model.nvar,) or not np.isfinite(x).all():
        return ["longitud incorrecta o componentes no finitas"]
    bad = []
    lo, hi = np.asarray(model.lb), np.asarray(model.ub)
    if np.any(x < lo - tol) or np.any(x > hi + tol):
        bad.append("cotas de variables violadas")
    integrality = np.asarray(model.integer, dtype=bool)
    if np.any(np.abs(x[integrality] - np.rint(x[integrality])) > tol):
        bad.append("variables enteras no integrales")
    A = coo_matrix((model.vals, (model.rows, model.cols)),
                   shape=(model.nrow, model.nvar)).tocsr()
    residual = A @ x
    low, high = np.asarray(model.rlo), np.asarray(model.rhi)
    viol = np.flatnonzero((residual < low - tol) | (residual > high + tol))
    if len(viol):
        bad.append(f"{len(viol)} filas algebraicas violadas; primeras: {viol[:8].tolist()}")
    return bad


def solve(model, time_limit=60.0, warm=None, rel_gap=1e-5, threads=1, seed=0, presolve=True):
    """Resuelve mediante la API pública documentada scipy.optimize.milp.

    ``warm`` se acepta por compatibilidad; SciPy no ofrece warm-start en MILP.
    La semilla y el número de hilos no se garantizan con esta interfaz.
    El estado Optimal procede únicamente de HiGHS y su cota/brecha, no de votaciones.
    """
    from scipy.optimize import milp, LinearConstraint, Bounds
    t = time.perf_counter()
    A = coo_matrix((model.vals, (model.rows, model.cols)),
                   shape=(model.nrow, model.nvar)).tocsr()
    # Los parámetros sin efecto se declaran, pero no se filtran a opciones internas no soportadas.
    options = {"time_limit": max(float(time_limit), 0.001),
               "mip_rel_gap": float(rel_gap), "presolve": bool(presolve),
               "disp": False}
    try:
        res = milp(c=np.asarray(model.cost, dtype=float),
                   integrality=np.asarray(model.integer, dtype=int),
                   bounds=Bounds(model.lb, model.ub),
                   constraints=LinearConstraint(A, model.rlo, model.rhi),
                   options=options)
    except Exception as ex:
        return dict(status=f"Solve error: {type(ex).__name__}: {ex}", estado=Estado.ERROR,
                    x=None, obj=None, gap=None, bound=None, nodes=None,
                    time=time.perf_counter()-t, nvar=model.nvar, nrow=model.nrow,
                    nbin=int(sum(model.integer)), certificado=False,
                    backend="scipy.optimize.milp")
    x = None if res.x is None else np.asarray(res.x, dtype=float)
    viol = validar_vector(model, x) if x is not None else []
    feasible = x is not None and not viol
    obj = float(np.dot(model.cost, x)) if feasible else None
    gap = getattr(res, "mip_gap", None)
    dual = getattr(res, "mip_dual_bound", None)
    optimal = res.status == 0 and feasible
    status = "Optimal" if optimal else (
        "Feasible (time/iteration limit)" if feasible else str(res.message))
    if viol:
        status = "Invalid solver candidate: " + "; ".join(viol)
    if viol:
        estado = Estado.SOLUCION_INVALIDA
    elif optimal:
        estado = Estado.OPTIMO
    elif res.status == 1:
        estado = Estado.FACTIBLE_LIMITE if feasible else Estado.SIN_SOLUCION_LIMITE
    elif res.status == 2:
        estado = Estado.INFACTIBLE
    elif res.status == 3:
        estado = Estado.NO_ACOTADO
    else:
        estado = Estado.ERROR
    return dict(status=status, estado=estado, codigo_scipy=int(res.status), x=x if feasible else None, obj=obj,
                gap=float(gap) if gap is not None else None,
                bound=float(dual) if dual is not None else None,
                nodes=getattr(res, "mip_node_count", None),
                time=time.perf_counter()-t, nvar=model.nvar, nrow=model.nrow,
                nbin=int(sum(model.integer)), certificado=optimal,
                backend="scipy.optimize.milp", violaciones_algebraicas=viol,
                solucionador_mensaje=str(res.message))


def exportar_mps(model, ruta):
    """Exporta MPS libre sin utilizar APIs privadas ni dependencias comerciales.

    Cada fila con intervalo estricto se divide en desigualdades inferior y superior.
    Los enteros se marcan mediante los tipos estándar BV, LI y UI de MPS.
    """
    from pathlib import Path
    path = Path(ruta)
    path.parent.mkdir(parents=True, exist_ok=True)
    mapping = []
    for i, (lo, hi) in enumerate(zip(model.rlo, model.rhi)):
        if np.isfinite(lo) and np.isfinite(hi) and abs(lo-hi) < 1e-10:
            mapping.append((i, "E", float(lo), f"R{i:06d}"))
        else:
            if np.isfinite(lo):
                mapping.append((i, "G", float(lo), f"L{i:06d}"))
            if np.isfinite(hi):
                mapping.append((i, "L", float(hi), f"U{i:06d}"))
    names = [f"X{k:07d}" for k in range(model.nvar)]
    # Evitar construir toda la matriz densa: cada variable visita únicamente sus coeficientes.
    bycol = [[] for _ in range(model.nvar)]
    byrow = [[] for _ in range(model.nrow)]
    for row, col, coef in zip(model.rows, model.cols, model.vals):
        byrow[row].append((col, float(coef)))
    for row, typ, rhs, rn in mapping:
        for col, val in byrow[row]:
            bycol[col].append((rn, val))
    with path.open("w", encoding="utf-8", newline="\n") as f:
        f.write("NAME SAGAPI\nROWS\n N OBJ\n")
        for _, typ, _, name in mapping:
            f.write(f" {typ} {name}\n")
        f.write("COLUMNS\n")
        for col, name in enumerate(names):
            # OBJ 0 también preserva variables sin entradas en restricciones.
            f.write(f"    {name} OBJ {model.cost[col]:.15g}\n")
            for rn, value in bycol[col]:
                f.write(f"    {name} {rn} {value:.15g}\n")
        f.write("RHS\n")
        for _, _, rhs, rn in mapping:
            if rhs:
                f.write(f"    RHS1 {rn} {rhs:.15g}\n")
        f.write("BOUNDS\n")
        for k, name in enumerate(names):
            lo, hi = model.lb[k], model.ub[k]
            if model.integer[k] and lo == 0 and hi == 1:
                f.write(f" BV BND1 {name}\n")
            elif model.integer[k]:
                f.write(f" LI BND1 {name} {lo:.15g}\n")
                if np.isfinite(hi):
                    f.write(f" UI BND1 {name} {hi:.15g}\n")
            elif lo == -INF and hi == INF:
                f.write(f" FR BND1 {name}\n")
            else:
                if lo != 0 and np.isfinite(lo):
                    f.write(f" LO BND1 {name} {lo:.15g}\n")
                elif lo == -INF:
                    f.write(f" MI BND1 {name}\n")
                if np.isfinite(hi):
                    f.write(f" UP BND1 {name} {hi:.15g}\n")
        f.write("ENDATA\n")
    # Guardar correspondencia de variables para auditoría sin alterar el estándar MPS.
    import json
    with path.with_suffix(".variables.json").open("w", encoding="utf-8") as f:
        json.dump(dict(zip(names, model.names)), f, ensure_ascii=False, indent=2)
    return str(path)


def version_highs():
    """Identificador de biblioteca realmente usada para resolver (API pública SciPy)."""
    import scipy
    return f"HiGHS vía scipy.optimize.milp (SciPy {scipy.__version__})"
