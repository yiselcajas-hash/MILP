"""Rastreo descriptivo de cambios entre el programa vigente y el propuesto.

Los motivos son señales de restricciones detectables; no se presentan como
explicaciones causales únicas del optimizador matemático.
"""
from __future__ import annotations
import csv
from pathlib import Path


def cambios(sub, solucion):
    """Compara operaciones libres con sus inicios y asignaciones anteriores."""
    filas = []
    inst = sub.inst
    for o in sub.free:
        if o not in solucion:
            continue
        m, inicio = solucion[o]
        anterior = sub.m0.get(o)
        s0 = sub.S0.get(o)
        delta = None if s0 is None else inicio - s0
        motivos = []
        if o in sub.interrupted:
            motivos.append("operación interrumpida en el evento")
        if anterior is not None and anterior != m:
            motivos.append("reasignación a recurso elegible")
        if anterior is not None and any(mm == anterior and a <= sub.t0 < b for mm, a, b in sub.all_windows):
            motivos.append("recurso anterior indisponible en el instante de decisión")
        if s0 is not None and delta > 1e-6:
            motivos.append("inicio desplazado por restricciones del nuevo programa")
        if s0 is not None and delta < -1e-6:
            motivos.append("operación adelantada por reordenación")
        if not motivos:
            motivos.append("sin modificación detectada" if s0 is not None else "pedido nuevo sin programa anterior")
        filas.append({
            "pedido": inst.jobs[inst.ops[o]["job"]]["id"],
            "operacion": inst.op_label(o),
            "maquina_anterior": anterior or "",
            "maquina_propuesta": m,
            "inicio_anterior_h": s0 if s0 is not None else "",
            "inicio_propuesto_h": round(inicio, 6),
            "cambio_h": round(delta, 6) if delta is not None else "",
            "duracion_pendiente_h": round(sub.pR[(o, m)], 6),
            "factores_observables": "; ".join(motivos),
        })
    return filas


def exportar_cambios(sub, soluciones, ruta):
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    keys = ["metodo", "pedido", "operacion", "maquina_anterior", "maquina_propuesta",
            "inicio_anterior_h", "inicio_propuesto_h", "cambio_h",
            "duracion_pendiente_h", "factores_observables"]
    with ruta.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        for metodo, sol in soluciones.items():
            if sol is not None:
                for fila in cambios(sub, sol):
                    w.writerow({"metodo": metodo, **fila})
    return ruta
