#!/usr/bin/env python3
"""Evidencia ampliada de la validación por enumeración: compara el MILP con la enumeración exhaustiva en N
microinstancias por jerarquía y escribe una fila por caso (valores enumerados y del MILP, estado, tamaño).

Uso: python 01_CODIGO_PYTHON/herramientas/reporte_enumeracion.py [N] [salida.csv]
"""
from __future__ import annotations

import csv
import os
import sys
import time

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(RAIZ, "01_CODIGO_PYTHON"))
sys.path.insert(0, os.path.join(RAIZ, "tests"))

from micro import escenario, inicial, optimo_enumerado  # noqa: E402
from sagapi import optimizacion as opt  # noqa: E402
from sagapi.indicadores import kpis_subproblema  # noqa: E402
from sagapi.verificacion import verificar_subproblema  # noqa: E402


def main(n=200, salida=None):
    salida = salida or os.path.join(RAIZ, "06_AUDITORIA_Y_VALIDACION", "Reporte_Pruebas", "enumeracion_exhaustiva.csv")
    os.makedirs(os.path.dirname(salida), exist_ok=True)
    filas, fallos = [], 0
    casos = [("reactivo", s, r) for s in range(n) for r in ("TARDANZA_PONDERADA", "PENALIDAD_FIJA")]
    casos += [("inicial", 1000 + s, "TARDANZA_PONDERADA") for s in range(n // 4)]
    for tipo, seed, regla in casos:
        sub = escenario(seed) if tipo == "reactivo" else inicial(seed)
        if not sub.free or len(sub.free) > 7:
            continue
        t = time.perf_counter()
        e1, e2, e3, nprog = optimo_enumerado(sub, regla)
        te = time.perf_counter() - t
        r = opt.optimizar(sub, regla_objetivo=regla, tl=60)
        k = kpis_subproblema(sub, r["sol"])
        m1, m2 = ((k["tardanza_ponderada"], k["penalidad_estimada"]) if regla == "TARDANZA_PONDERADA"
                  else (k["penalidad_estimada"], k["tardanza_ponderada"]))
        ok1 = abs(m1 - e1) <= 1e-3
        ok2 = abs(m2 - e2) <= 1e-3 * max(1, e2)
        ok3 = True if e3 is None else abs(k["estabilidad_f3"] - e3) <= 2e-3 * max(1, e3)
        viol = len(verificar_subproblema(sub, r["sol"]))
        ok = ok1 and ok2 and ok3 and viol == 0 and r["estado_global"] == "OPTIMO"
        fallos += not ok
        filas.append(dict(tipo=tipo, semilla=seed, regla=regla, ops_libres=len(sub.free),
                          ops_no_interrumpibles=sum(1 for o in sub.free if not sub.inst.ops[o]["interrumpible"]),
                          ventanas_futuras=len(sub.windows), interrumpidas=len(sub.interrupted),
                          programas_enumerados=nprog, P1_enum=round(e1, 6), P1_milp=round(m1, 6), P2_enum=round(e2, 6),
                          P2_milp=round(m2, 6), P3_enum=None if e3 is None else round(e3, 6),
                          P3_milp=round(k["estabilidad_f3"], 6) if e3 is not None else None,
                          estado=r["estado_global"], violaciones=viol, coincide=int(ok),
                          tiempo_enum_s=round(te, 3), tiempo_milp_s=round(sum(p["tiempo_s"] for p in r["pasos"]), 3)))
    with open(salida, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(filas[0]))
        w.writeheader()
        w.writerows(filas)
    p3 = sum(1 for f in filas if f["P3_enum"] is not None)
    print(f"{len(filas)} casos comparados; coincidencias {len(filas) - fallos}/{len(filas)}; con P3 {p3}; "
          f"con R12 {sum(1 for f in filas if f['ops_no_interrumpibles'])}; con ventanas futuras "
          f"{sum(1 for f in filas if f['ventanas_futuras'])} → {salida}")
    return 0 if fallos == 0 else 1


if __name__ == "__main__":
    sys.exit(main(int(sys.argv[1]) if len(sys.argv) > 1 else 200, sys.argv[2] if len(sys.argv) > 2 else None))
