"""Horizonte rodante por eventos (llegada de pedidos y averías) con estado persistente entre periodos.

En cada evento t se construye el subproblema con TODOS los pedidos activos (liberados y no terminados):
  * lo completado (C ≤ t) y lo que está en curso en una unidad sana queda fijo y no se vuelve a decidir;
  * lo pendiente dentro del horizonte congelado [t, t + H) también queda fijo (decisión congelada);
  * la operación en curso en la unidad que falla queda interrumpida: su tramo ejecutado se registra como
    'parcial' (ocupa la unidad, no cuenta como producción) y el resto se reprograma con su tiempo restante.
Al final se verifica el programa completo (cada operación exactamente una vez, sin solapes, ventanas,
continuidad) y, si se pide, se asignan trabajadores y se verifica el personal.

Combinaciones programación / reacción: FIFO+CONV (práctica actual aproximada), FIFO+MILP, EDD+EDD, MILP+CONV,
MILP+MILP. Todas usan el mismo subproblema en cada evento (mismas restricciones, mismos datos).
Supuestos: ejecución perfecta entre eventos; la duración de una avería se conoce al ocurrir (ver
Limitaciones_y_Supuestos.md).
"""
from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field

from . import estado, optimizacion as opt, personal as pers, reglas
from .solver import Estado
from .verificacion import resumen, verificar_programa, verificar_subproblema

EPS = 1e-6
PLANES = ("FIFO", "EDD", "MILP")
REACCIONES = ("CONV", "EDD", "MILP")


class ErrorSimulacion(RuntimeError):
    """Violación de factibilidad o de inmutabilidad detectada durante la simulación (nunca se ignora)."""


def ventanas_de(datos, eventos, mult=1.0):
    """[(evento, recurso, a, b)] en horas productivas; mult escala la duración (análisis de sensibilidad)."""
    cal = datos.calendario
    out = []
    for ev in eventos:
        f = datos.fallas[ev]
        a, b = cal.a_horas(f["inicio"]), cal.a_horas(f["fin"])
        b = a + (b - a) * mult
        if b > a + EPS:
            out.append((ev, f["maquina"], a, b))
    return out


@dataclass
class ResultadoSimulacion:
    combinacion: str
    programa: dict
    parciales: list
    duraciones: dict
    ventanas: list
    registro: list
    verificacion: dict
    tiempo_total_s: float
    certificado: dict | None = None
    modo_personal: str = "SIN_PERSONAL"
    asignacion: dict | None = None
    asignacion_info: dict = field(default_factory=dict)
    regla_objetivo: str = ""
    politica: str = "A"
    detalle_violaciones: dict = field(default_factory=dict)

    @property
    def factible(self):
        return self.verificacion.get("total", 1) == 0


def _avail(programa, parciales):
    av = defaultdict(float)
    for o, (m, S, C) in programa.items():
        av[m] = max(av[m], C)
    for (o, m, S, C) in parciales:
        av[m] = max(av[m], C)
    return av


def simular(datos, inst, plan="FIFO", reaccion="CONV", eventos=(), politica="A", regla_objetivo="TARDANZA_PONDERADA",
            beta=8.0, tl=60.0, gap=1e-5, congelar_h=0.0, dot=None, asignar_personal=True, tl_personal=120.0,
            mult_falla=1.0, log=None):
    """Simula el horizonte completo y devuelve un ResultadoSimulacion verificado.

    eventos: identificadores de 23_EVENTOS_SIM o tuplas (id, recurso, a, b) en horas productivas.
    dot:     Dotacion (personal.dotacion); None = no se modela personal.
    """
    if plan not in PLANES or reaccion not in REACCIONES:
        raise ValueError(f"combinación desconocida {plan}+{reaccion}")
    t_ini = time.perf_counter()
    h_dia = datos.calendario.h_dia
    # Los mantenimientos planificados se conocen desde el inicio (ventanas anunciadas que todo método respeta);
    # las averías se conocen recién al ocurrir y disparan una reprogramación.
    ids = [e for e in eventos if not isinstance(e, tuple)]
    planificados = [e for e in ids if str(datos.fallas[e]["tipo"]).upper().startswith("MANTENIMIENTO")]
    fallas = [e for e in eventos if isinstance(e, tuple)] + \
        ventanas_de(datos, [e for e in ids if e not in planificados], mult_falla)
    fallas.sort(key=lambda w: (w[2], w[0]))
    llegadas = sorted({jb["r"] for jb in inst.jobs})
    cola = [(t, 0, "LLEGADA", None) for t in llegadas] + [(w[2], 1, "FALLA", w) for w in fallas]
    cola.sort(key=lambda e: (e[0], e[1]))
    # ---- personal
    cert, modo, est_global = None, "SIN_PERSONAL", None
    if dot is not None:
        cert = pers.certificado_cobertura(dot, inst)
        modo = "CERTIFICADO" if cert["ok"] else "REPARACION_LABORAL"
        # una operación cuyas unidades elegibles carecen todas de personal habilitado no puede programarse
        imposibles = sorted({inst.op_label(o) for o in range(len(inst.ops)) if set(inst.elig[o]) <= set(cert["sin_personal"])})
        if imposibles:
            raise ErrorSimulacion(f"personal insuficiente: {len(imposibles)} operaciones solo pueden hacerse en recursos sin "
                                  f"trabajadores habilitados disponibles ({', '.join(cert['sin_personal'])}); "
                                  f"p. ej. {imposibles[:3]}")
    asign_global = {}
    # ---- estado persistente
    programa, pR, dur = {}, {}, {}
    parciales, ventanas, registro = [], [], []
    for (ev, m, a, b) in ventanas_de(datos, planificados):
        ventanas += estado.ventanas_unidades(inst, [(m, a, b)])
    for t, _, tipo, info in cola:
        if tipo == "FALLA":
            ev, m, a, b = info
            ventanas += estado.ventanas_unidades(inst, [(m, a, b)])
        liberados = [j for j in range(len(inst.jobs)) if inst.jobs[j]["r"] <= t + EPS]
        activos = [j for j in liberados if not all(o in programa and programa[o][2] <= t + EPS for o in inst.job_ops[j])]
        metodo = plan if tipo == "LLEGADA" else reaccion
        t0 = time.perf_counter()
        fila = dict(t=t, fecha=datos.calendario.a_fecha(t), tipo=tipo, evento=(info[0] if info else ""), metodo=metodo,
                    activos=len(activos), estado="REGLA", interrumpidas=0, congeladas=0, D_h=0.0, R=0)
        previo = dict(programa)
        if tipo == "LLEGADA" and plan == "FIFO":
            nuevos = [j for j in liberados if inst.job_ops[j][0] not in programa]
            est = pers.estado_desde_programa(dot, inst, programa, asign_global, h_dia, parciales) \
                if modo == "REPARACION_LABORAL" else None
            nuevo, _ = reglas.fifo_plan(inst, nuevos, _avail(programa, parciales), t, ventanas, personal=est)
            for o, v in nuevo.items():
                programa[o] = v
                dur[o] = v[2] - v[1]
                pR[(o, v[0])] = inst.p[(o, v[0])]
                if est is not None:
                    asign_global[("F", o)] = est.asignacion[o]
            fila["ops_libres"] = len(nuevo)
        else:
            if not activos:
                continue
            sub = estado.particionar(datos, inst, programa, t, activos, ventanas, politica, pR, congelar_h)
            # tramos interrumpidos: ocupan la unidad, no son producción terminada
            for o in sub.interrupted:
                inf = sub.info[o]
                if inf["transcurrido"] > EPS:
                    parciales.append((o, inf["m_star"], inf["S_orig"], t))
                    if ("F", o) in asign_global:
                        asign_global[("P", len(parciales) - 1)] = asign_global.pop(("F", o))
            est = None
            if modo == "REPARACION_LABORAL":
                libres = set(sub.free)
                fijos = {o: v for o, v in programa.items() if o not in libres}
                est = pers.estado_desde_programa(dot, inst, fijos, asign_global, h_dia, parciales)
            if metodo == "EDD":
                sol = reglas.edd(sub, personal=est)
            elif metodo == "CONV":
                sol = reglas.convencional(sub, personal=est)
            else:
                r = opt.optimizar(sub, beta=beta, regla_objetivo=regla_objetivo, tl=tl, gap=gap,
                                  estabilidad=(tipo == "FALLA"), horas_dia=h_dia, personal=est)
                if r["sol"] is None:
                    raise ErrorSimulacion(f"t={t:.2f} {tipo}: el MILP no devolvió solución ({r['estado_global']})")
                sol = r["sol"]
                fila.update(estado=r["estado_global"], respaldo=r["respaldo"], reparacion_laboral=r["reparacion_laboral"],
                            **{f"modelo_{k}": v for k, v in r["tamano"].items()},
                            brecha_max=max((p["brecha"] or 0.0) for p in r["pasos"]) if r["pasos"] else None,
                            tiempo_solver_s=sum(p["tiempo_s"] for p in r["pasos"]),
                            **{f"obj_{k}": v for k, v in r["objetivos"].items()})
            viol = verificar_subproblema(sub, sol)
            if viol:
                raise ErrorSimulacion(f"t={t:.2f} {tipo} {metodo}: solución infactible: {viol[:3]}")
            # control de inmutabilidad: nada iniciado (salvo lo interrumpido) ni congelado vuelve a decidirse
            for o in sub.free:
                if o in previo and previo[o][1] < t - EPS and o not in sub.interrupted:
                    raise ErrorSimulacion(f"t={t:.2f}: {inst.op_label(o)} ya había iniciado y se intentó reprogramar")
            for o in sub.pending:
                m, S = sol[o]
                fila["D_h"] += abs(S - sub.S0[o])
                fila["R"] += int(m != sub.m0[o])
            for o, (m, S) in sol.items():
                programa[o] = (m, S, S + sub.pR[(o, m)])
                dur[o] = sub.pR[(o, m)]
                for mm in sub.eligR[o]:
                    pR[(o, mm)] = sub.pR[(o, mm)]
                if est is not None:
                    asign_global[("F", o)] = est.asignacion[o]
            fila.update(ops_libres=len(sub.free), interrumpidas=len(sub.interrupted), congeladas=len(sub.congeladas))
        for o, v in previo.items():          # lo completado antes de t nunca cambia
            if v[2] <= t + EPS and programa.get(o) != v:
                raise ErrorSimulacion(f"t={t:.2f}: se modificó la operación completada {inst.op_label(o)}")
        fila["tiempo_s"] = time.perf_counter() - t0
        registro.append(fila)
        if log:
            log(fila)
    ver = verificar_programa(inst, programa, ventanas, parciales=parciales, duraciones=dur)
    res = ResultadoSimulacion(f"{plan}+{reaccion}", programa, parciales, dur, ventanas, registro, resumen(ver),
                              time.perf_counter() - t_ini, cert, modo, regla_objetivo=regla_objetivo, politica=politica)
    res.detalle_violaciones = ver
    if dot is not None and asignar_personal:
        respaldo = pers.asignacion_por_equipos(inst, programa, cert, parciales) if cert["ok"] else asign_global
        t1 = time.perf_counter()
        a = pers.asignar_trabajadores(inst, programa, dot, parciales, tl=tl_personal, respaldo=respaldo, horas_dia=h_dia)
        res.asignacion = a["asignacion"]
        res.asignacion_info = dict(estado=a["estado"], violaciones=len(a.get("violaciones") or []),
                                   cargas=a["cargas"], tiempo_s=time.perf_counter() - t1, pasos=a["pasos"],
                                   cliques=a.get("cliques"))
        if a.get("violaciones"):
            res.verificacion["personal"] = len(a["violaciones"])
            res.verificacion["total"] += len(a["violaciones"])
            res.detalle_violaciones["personal"] = a["violaciones"]
    return res


def estados_milp(res):
    """Conteo de estados de solución de los eventos resueltos con MILP."""
    c = defaultdict(int)
    for f in res.registro:
        if f["metodo"] == "MILP":
            c[f["estado"]] += 1
    return dict(c)


def todos_optimos(res):
    return all(f["estado"] == Estado.OPTIMO for f in res.registro if f["metodo"] == "MILP")
