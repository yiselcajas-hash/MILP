"""Simulación de horizonte rodante (año 2025) por eventos: llegada de pedidos y averías.

En cada evento se decide sólo lo que aún no empezó; lo ejecutado queda fijo (estrategia
predictiva-reactiva). Cuatro combinaciones de programación / reacción:
  FIFO+CONV  situación actual aproximada (16_PROGRAMA_BASE + desplazamiento a la derecha)
  FIFO+MILP  programa convencional y reprogramación MILP sólo ante averías
  MILP+CONV  programación MILP en cada llegada de pedidos y reacción convencional ante averías
  MILP+MILP  propuesta completa
  EDD+...    despacho por fecha comprometida en cada llegada (regla de referencia más exigente que FIFO)
Se supone ejecución perfecta del programa entre eventos y duración de la avería conocida al ocurrir.
"""
from __future__ import annotations
import time
from collections import defaultdict
from . import estado, reglas, optimizacion as opt
from .verificacion import verificar

EPS = 1e-6


def ventanas_de(datos, eventos):
    cal = datos.calendario
    out = []
    for ev in eventos:
        f = datos.fallas[ev]
        a, b = cal.a_horas(f["inicio"]), cal.a_horas(f["fin"])
        if b > a + EPS:
            out.append((ev, f["maquina"], a, b))
    return out


def simular(datos, inst, plan="FIFO", reaccion="CONV", eventos_falla=(), politica="A", beta=8.0,
            regla_pen="FIJA", tl=(60, 60, 60), log=None):
    cal = datos.calendario
    fallas = sorted(ventanas_de(datos, eventos_falla), key=lambda w: w[2])
    llegadas = sorted({jb["r"] for jb in inst.jobs})
    eventos = [(t, 0, "LLEGADA", None) for t in llegadas] + [(a, 1, "FALLA", (ev, m, a, b)) for (ev, m, a, b) in fallas]
    eventos.sort(key=lambda e: (e[0], e[1]))
    programa = {}           # o -> (m, S, C)
    pR = {}                 # duraciones vigentes (restantes tras interrupciones)
    ventanas = []           # (m, a, b)
    registro = []
    for t, _, tipo, info in eventos:
        if tipo == "FALLA":
            ev, m, a, b = info
            ventanas.append((m, a, b))
        liberados = [j for j in range(len(inst.jobs)) if inst.jobs[j]["r"] <= t + EPS]
        activos = [j for j in liberados
                   if not all(o in programa and programa[o][2] <= t + EPS for o in inst.job_ops[j])]
        t0 = time.perf_counter()
        estado_s, tam = "REGLA", None
        if tipo == "LLEGADA" and plan == "FIFO":
            nuevos = [j for j in liberados if inst.job_ops[j][0] not in programa]
            avail = defaultdict(float)
            for o, (m, S, C) in programa.items():
                avail[m] = max(avail[m], C)
            nuevo, _ = reglas.fifo_plan(inst, nuevos, avail, t, ventanas)
            programa.update(nuevo)
            for o in nuevo:
                pR[(o, nuevo[o][0])] = inst.p[(o, nuevo[o][0])]
            n_free = sum(len(inst.job_ops[j]) for j in nuevos)
        else:
            sub = estado.particionar(datos, inst, programa, t, activos, ventanas, politica, pR)
            # ocupación por operaciones fijas de pedidos fuera del subproblema (no debería haber: todos activos)
            usar_milp = (tipo == "LLEGADA" and plan == "MILP") or (tipo == "FALLA" and reaccion == "MILP")
            usar_edd = (tipo == "LLEGADA" and plan == "EDD") or (tipo == "FALLA" and reaccion == "EDD")
            if usar_edd:
                sol = reglas.edd(sub)
            elif usar_milp:
                if tipo == "LLEGADA":
                    r = opt.lexicografico(sub, beta=beta, regla_pen=regla_pen, tl=tl, estabilidad=False)
                else:
                    r = opt.lexicografico(sub, beta=beta, regla_pen=regla_pen, tl=tl, estabilidad=True)
                sol = r["sol"]
                estado_s, tam = r["estado_global"], r["tamano"]
            else:
                sol = reglas.convencional(sub)
            viol = verificar(sub, sol)
            if viol:
                raise RuntimeError(f"Solución infactible en t={t:.2f} ({tipo}): {viol[:3]}")
            for o, (m, S) in sol.items():
                programa[o] = (m, S, S + sub.pR[(o, m)])
                for mm in sub.eligR[o]:
                    pR[(o, mm)] = sub.pR[(o, mm)]
            n_free = len(sub.free)
        registro.append(dict(t=t, fecha=cal.a_fecha(t), tipo=tipo, evento=(info[0] if info else ""),
                             activos=len(activos), ops_libres=n_free, estado=estado_s,
                             binarias=(tam or {}).get("binarias"), tiempo_s=time.perf_counter() - t0))
        if log:
            log(registro[-1])
    return programa, registro


def kpis_anuales(inst, programa, horas_dia=8.0):
    out = defaultdict(float)
    fam = defaultdict(lambda: [0, 0, 0.0])
    detalle = []
    for j, jb in enumerate(inst.jobs):
        C = programa[inst.job_ops[j][-1]][2]
        T = max(0.0, C - jb["d"])
        tarde = T > EPS
        out["pedidos"] += 1
        out["atrasados"] += tarde
        out["penalidad"] += jb["P"] if tarde else 0.0
        out["pen_diaria_tope"] += min(jb["pdia"] * T / horas_dia, 0.10 * jb["valor"])
        out["tardanza_h"] += T
        out["tard_pond"] += jb["w"] * T
        out["tard_max_h"] = max(out["tard_max_h"], T)
        f = fam[jb["familia"]]
        f[0] += 1; f[1] += tarde; f[2] += jb["P"] if tarde else 0.0
        detalle.append(dict(pedido=jb["id"], familia=jb["familia"], C=C, d=jb["d"], T=T, tarde=int(tarde),
                            penalidad=jb["P"] if tarde else 0.0))
    out["otd_pct"] = 100 * (1 - out["atrasados"] / out["pedidos"])
    out["tardanza_dias"] = out["tardanza_h"] / horas_dia
    return dict(out), {k: dict(pedidos=v[0], atrasados=v[1], penalidad=v[2]) for k, v in fam.items()}, detalle
