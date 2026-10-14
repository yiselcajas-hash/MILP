"""Transformaciones de escenarios operativos y de sensibilidad (todas SIMULADAS; nunca alteran la base Excel).

Cada transformación devuelve copias de los pedidos o de los datos; la base original no se modifica. Los
escenarios se definen en 27_ESCENARIOS_OPERATIVOS_SIM y 26_SENSIBILIDAD_SIM: este módulo solo los aplica.
"""
from __future__ import annotations

import copy
import datetime as dt

from .datos import recalcular_pesos


def pedidos_transformados(datos, factor_cantidad=1.0, factor_plazo=1.0):
    """Copia de los pedidos con cantidad q·f_q (redondeo, mínimo 1) y plazo (compromiso − recepción)·f_p.

    El vencimiento nunca queda antes de la liberación (se acota y se cuenta). Pesos w_j, P_j y topes se
    recalculan con las fórmulas de la base sobre los pedidos transformados.
    Devuelve (pedidos, avisos).
    """
    hl = datos.pedidos[0]["liberacion_h"].time() if datos.pedidos else dt.time(8, 0)
    hv = datos.pedidos[0]["vencimiento_h"].time() if datos.pedidos else dt.time(17, 0)
    out, acotados = [], 0
    for p in datos.pedidos:
        n = dict(p)
        if factor_cantidad != 1.0:
            n["q"] = max(1, int(round(p["q"] * factor_cantidad)))
        if factor_plazo != 1.0:
            plazo = (p["compromiso"] - p["recepcion"]).days
            nuevo = p["recepcion"] + dt.timedelta(days=max(1, int(round(plazo * factor_plazo))))
            if nuevo.date() < p["liberacion"].date():
                nuevo = dt.datetime.combine(p["liberacion"].date(), dt.time())
                acotados += 1
            n["compromiso"] = nuevo
        n["liberacion_h"] = dt.datetime.combine(n["liberacion"].date(), hl)
        n["vencimiento_h"] = dt.datetime.combine(n["compromiso"].date(), hv)
        out.append(n)
    recalcular_pesos(out)
    avisos = [f"{acotados} pedido(s) con vencimiento acotado a su fecha de liberación"] if acotados else []
    return out, avisos


def datos_con_factor_alternativa(datos, factor):
    """Copia de los datos con el factor de tiempo de TODAS las asignaciones alternativas igual a `factor`."""
    d2 = copy.copy(datos)
    d2.elegibilidad = {k: [(m, tipo, (fac if tipo == "PRINCIPAL" else float(factor))) for (m, tipo, fac) in v]
                       for k, v in datos.elegibilidad.items()}
    return d2


def eventos_escenario(datos, escenario_id):
    esc = {e["id"]: e for e in datos.escenarios}[escenario_id]
    return list(esc["eventos"]), esc["politica"]
