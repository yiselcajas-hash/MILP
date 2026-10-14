"""Indicadores de desempeño (KPI) con definición, fórmula, unidad y procedencia de los datos que usan.

Eje de tiempo: horas productivas (h) del calendario; 1 día productivo = h_dia horas (8 h). Los montos en soles
(S/) dependen de parámetros ESTIMADOS (penalidades por familia, costos horarios, tarifa) y se rotulan así.
Ningún indicador se calcula sobre datos que no salgan de una corrida real del programa.
"""
from __future__ import annotations

import statistics
from collections import defaultdict

from .instancia import recurso_base
from .verificacion import programa_completo

EPS = 1e-6

# nombre: (fórmula, unidad, definición, procedencia de los datos)
DEFINICIONES = {
    "pedidos": ("|J|", "pedidos", "Pedidos evaluados (todos deben completarse)", "SIMULADO (20_PEDIDOS_SIM)"),
    "completados": ("|{j : C_j definido}|", "pedidos", "Pedidos con todas sus operaciones programadas", "CALCULADO"),
    "atrasados": ("Σ_j U_j, U_j = 1[C_j > d_j]", "pedidos", "Pedidos que terminan después del vencimiento", "CALCULADO"),
    "otd_pct": ("100·(1 − atrasados/pedidos)", "%", "Entregas a tiempo (On-Time Delivery)", "CALCULADO"),
    "tardanza_total_h": ("Σ_j T_j, T_j = max(0, C_j − d_j)", "h productivas", "Tardanza total", "CALCULADO"),
    "tardanza_total_dias": ("Σ_j T_j / h_dia", "días productivos", "Tardanza total en días productivos", "CALCULADO"),
    "tardanza_ponderada": ("Σ_j w_j T_j, w_j = valor_j / valor medio", "h ponderadas", "Objetivo P1 por defecto",
                           "CALCULADO (valor con precio medio por familia: ESTIMADO)"),
    "tardanza_max_h": ("max_j T_j", "h productivas", "Mayor tardanza individual", "CALCULADO"),
    "tardanza_media_atrasados_h": ("Σ_j T_j / atrasados", "h productivas", "Tardanza media de los pedidos atrasados",
                                   "CALCULADO"),
    "adelanto_medio_h": ("Σ_j max(0, d_j − C_j) / |J|", "h productivas", "Holgura media al entregar", "CALCULADO"),
    "flujo_medio_h": ("Σ_j (C_j − r_j) / |J|", "h productivas", "Tiempo medio en el sistema desde la liberación",
                      "CALCULADO"),
    "makespan_h": ("max_j C_j", "h productivas", "Fin de la última operación (desde el inicio del calendario)",
                   "CALCULADO"),
    "penalidad_estimada": ("Σ_j P_j U_j, P_j = frac_familia · valor_j", "S/", "Penalidad fija contractual estimada",
                           "ESTIMADO (fracción de penalidad por familia sin contrato verificado)"),
    "penalidad_diaria_tope": ("Σ_j min(a_j T_j / h_dia, tope_j)", "S/", "Penalidad diaria con tope (sensibilidad)",
                              "ESTIMADO"),
    "horas_maquina": ("Σ_o (C_o − S_o) + Σ parciales", "h", "Horas de proceso ocupadas en unidades", "CALCULADO"),
    "horas_reproceso": ("Σ parciales perdidos (política B) + tiempo extra de recuperación", "h",
                        "Horas de proceso adicionales por interrupciones", "CALCULADO"),
    "utilizacion_media_pct": ("100·Σ_m ocupado_m / Σ_m disponible_m (en [0, makespan])", "%",
                              "Utilización media de las unidades usadas", "CALCULADO"),
    "utilizacion_max_pct": ("max_m 100·ocupado_m / disponible_m", "%", "Utilización de la unidad más cargada",
                            "CALCULADO"),
    "ocio_total_h": ("Σ_m (disponible_m − ocupado_m)", "h", "Tiempo ocioso de unidades en [0, makespan]",
                     "CALCULADO"),
    "energia_kwh": ("Σ_o p_o · kW_m · factor_carga_m", "kWh", "Energía eléctrica de proceso",
                    "ESTIMADO (potencias de referencia)"),
    "costo_uso_maquinas": ("Σ_m ocupado_m · costo_h_m", "S/", "Costo de uso de recursos", "ESTIMADO"),
    "costo_energia": ("energia_kwh · tarifa", "S/", "Costo de energía", "ESTIMADO (tarifa sin recibo)"),
    "costo_mano_obra_directa": ("Σ_w horas_w · costo_hora_hombre", "S/", "Mano de obra aplicada a operaciones",
                                "ESTIMADO (sin planilla)"),
    "carga_trabajador_max_h": ("max_w Σ_{o→w} p_o", "h", "Mayor carga anual de un trabajador",
                               "CALCULADO (habilidades SIMULADAS)"),
    "carga_trabajador_cv": ("desv. est. / media de las cargas", "-", "Desequilibrio de carga laboral",
                            "CALCULADO (habilidades SIMULADAS)"),
    "tiempo_computo_s": ("Σ tiempos de los eventos", "s", "Tiempo de cómputo total (reloj)", "MEDIDO"),
    "tiempo_solver_s": ("Σ tiempos de HiGHS", "s", "Tiempo de cómputo del solucionador", "MEDIDO"),
    "brecha_max": ("max (cota − incumbente)/incumbente", "-", "Mayor brecha de optimalidad informada por HiGHS",
                   "MEDIDO"),
    "eventos_milp": ("|eventos resueltos con MILP|", "eventos", "Eventos resueltos con MILP", "MEDIDO"),
    "eventos_optimos": ("|eventos con estado OPTIMO en todas las fases|", "eventos", "Eventos con óptimo demostrado",
                        "MEDIDO"),
    "desviacion_total_h": ("Σ_eventos Σ_o |S_o − S0_o|", "h", "Nerviosismo: desplazamiento de inicios planificados",
                           "CALCULADO"),
    "reasignaciones": ("Σ_eventos Σ_o 1[m_o ≠ m0_o]", "operaciones", "Cambios de unidad respecto del plan vigente",
                       "CALCULADO"),
}


def tabla_definiciones():
    return [dict(indicador=k, formula=v[0], unidad=v[1], definicion=v[2], procedencia=v[3]) for k, v in DEFINICIONES.items()]


def fines(inst, programa, jobs):
    return {j: programa[inst.job_ops[j][-1]][2] for j in jobs if inst.job_ops[j][-1] in programa}


def tabla_pedidos(inst, programa, jobs=None):
    jobs = range(len(inst.jobs)) if jobs is None else jobs
    filas = []
    for j in jobs:
        jb = inst.jobs[j]
        last = inst.job_ops[j][-1]
        if last not in programa:
            filas.append(dict(pedido=jb["id"], familia=jb["familia"], completado=0))
            continue
        C = programa[last][2]
        S = programa[inst.job_ops[j][0]][1]
        T = max(0.0, C - jb["d"])
        filas.append(dict(pedido=jb["id"], familia=jb["familia"], producto=jb["producto"], q=jb["q"], completado=1,
                          r_h=jb["r"], d_h=jb["d"], inicio_h=S, fin_h=C, tardanza_h=T, atrasado=int(T > EPS),
                          adelanto_h=max(0.0, jb["d"] - C), flujo_h=C - jb["r"], w=jb["w"], P=jb["P"],
                          penalidad=jb["P"] if T > EPS else 0.0))
    return filas


def _ocupacion(programa, parciales=()):
    occ = defaultdict(float)
    for o, (m, S, C) in programa.items():
        occ[m] += C - S
    for (o, m, S, C) in parciales:
        occ[m] += C - S
    return occ


def utilizacion(inst, programa, parciales=(), ventanas=(), horizonte=None):
    """Por unidad: ocupado, indisponible, disponible y utilización en [0, horizonte] (por defecto el makespan)."""
    H = horizonte if horizonte is not None else max((C for (_, _, C) in programa.values()), default=0.0)
    occ = _ocupacion(programa, parciales)
    caida = defaultdict(float)
    for (u, a, b) in ventanas:
        caida[u] += max(0.0, min(b, H) - max(a, 0.0))
    filas = []
    for m in inst.machines:
        disp = max(0.0, H - caida[m])
        filas.append(dict(unidad=m, recurso=recurso_base(m), ocupado_h=occ[m], indisponible_h=caida[m], disponible_h=disp,
                          ocio_h=max(0.0, disp - occ[m]), utilizacion_pct=100 * occ[m] / disp if disp > 0 else 0.0))
    return filas


def espera_por_recurso(inst, programa):
    """Espera en cola atribuible a cada unidad: Σ (S_o − instante en que o estaba lista), con lista = max(r_j, C_pred)."""
    esp = defaultdict(float)
    n = defaultdict(int)
    for o, (m, S, C) in programa.items():
        pr = inst.pred(o)
        listo = inst.jobs[inst.ops[o]["job"]]["r"] if pr is None else programa[pr][2] if pr in programa else S
        esp[m] += max(0.0, S - listo)
        n[m] += 1
    return {m: dict(espera_total_h=esp[m], operaciones=n[m], espera_media_h=esp[m] / n[m] if n[m] else 0.0)
            for m in inst.machines}


def carga_teorica(inst, jobs=None, horas_disponibles=None):
    """Carga de trabajo por recurso con tiempos de la ruta principal (sin depender del programa)."""
    jobs = range(len(inst.jobs)) if jobs is None else jobs
    carga = defaultdict(float)
    for j in jobs:
        for o in inst.job_ops[j]:
            m = inst.ops[o]["principal"]
            u = inst.unidades.get(m, [m])[0]
            carga[m] += inst.p[(o, u)] if (o, u) in inst.p else 0.0
    out = []
    for m, h in sorted(carga.items(), key=lambda kv: -kv[1]):
        k = len(inst.unidades.get(m, [m]))
        fila = dict(recurso=m, unidades=k, carga_h=h)
        if horas_disponibles:
            fila["carga_relativa_pct"] = 100 * h / (k * horas_disponibles)
        out.append(fila)
    return out


def cota_inferior_tardanza(inst, jobs=None):
    """T_j^LB = max(0, r_j + Σ_o min_m p_om − d_j): tardanza inevitable aun con capacidad infinita."""
    jobs = range(len(inst.jobs)) if jobs is None else jobs
    out = {}
    for j in jobs:
        jb = inst.jobs[j]
        dur = sum(min(inst.p[(o, m)] for m in inst.elig[o]) for o in inst.job_ops[j])
        out[j] = max(0.0, jb["r"] + dur - jb["d"])
    return out


def kpis_programa(inst, programa, datos, jobs=None, parciales=(), ventanas=(), registro=None, cargas=None):
    """KPI del sistema completo (todas las órdenes del alcance) sobre un programa ejecutado."""
    jobs = list(range(len(inst.jobs))) if jobs is None else list(jobs)
    h_dia = datos.calendario.h_dia
    k = defaultdict(float)
    C = fines(inst, programa, jobs)
    k["pedidos"] = len(jobs)
    k["completados"] = len(C)
    T_late = []
    for j, c in C.items():
        jb = inst.jobs[j]
        T = max(0.0, c - jb["d"])
        tarde = T > EPS
        k["atrasados"] += tarde
        k["tardanza_total_h"] += T
        k["tardanza_ponderada"] += jb["w"] * T
        k["tardanza_max_h"] = max(k["tardanza_max_h"], T)
        k["adelanto_medio_h"] += max(0.0, jb["d"] - c)
        k["flujo_medio_h"] += c - jb["r"]
        k["penalidad_estimada"] += jb["P"] if tarde else 0.0
        k["penalidad_diaria_tope"] += min(jb["pdia"] * T / h_dia, jb.get("tope", 0.10 * jb["valor"]))
        if tarde:
            T_late.append(T)
    n = max(1, len(C))
    k["otd_pct"] = 100.0 * (1 - k["atrasados"] / n)
    k["tardanza_total_dias"] = k["tardanza_total_h"] / h_dia
    k["tardanza_media_atrasados_h"] = statistics.fmean(T_late) if T_late else 0.0
    k["adelanto_medio_h"] /= n
    k["flujo_medio_h"] /= n
    k["makespan_h"] = max(C.values()) if C else 0.0
    ut = utilizacion(inst, programa, parciales, ventanas)
    usadas = [u for u in ut if u["ocupado_h"] > 0]
    k["horas_maquina"] = sum(u["ocupado_h"] for u in ut)
    k["horas_reproceso"] = horas_reproceso(inst, programa, parciales)
    disp = sum(u["disponible_h"] for u in usadas)
    k["utilizacion_media_pct"] = 100 * sum(u["ocupado_h"] for u in usadas) / disp if disp else 0.0
    k["utilizacion_max_pct"] = max((u["utilizacion_pct"] for u in usadas), default=0.0)
    k["ocio_total_h"] = sum(u["ocio_h"] for u in usadas)
    occ = _ocupacion(programa, parciales)
    tarifa = float(datos.parametros.get("tarifa_electrica") or 0.0)
    for m, h in occ.items():
        mq = datos.maquinas.get(recurso_base(m))
        if mq:
            k["energia_kwh"] += h * (mq.potencia_kw or 0.0) * (mq.factor_carga or 0.0)
            k["costo_uso_maquinas"] += h * (mq.costo_h or 0.0)
    k["costo_energia"] = k["energia_kwh"] * tarifa
    hh = sum(h * int(inst.ops[o].get("crew", 1)) for o, (m, S, C2) in programa.items() for h in [C2 - S])
    hh += sum((C2 - S) * int(inst.ops[o].get("crew", 1)) for (o, m, S, C2) in parciales)
    k["horas_hombre"] = hh
    k["costo_mano_obra_directa"] = hh * float(datos.parametros.get("costo_hora_hombre") or 0.0)
    if cargas:
        vals = list(cargas.values())
        media = statistics.fmean(vals)
        k["carga_trabajador_max_h"] = max(vals)
        k["carga_trabajador_min_h"] = min(vals)
        k["carga_trabajador_cv"] = statistics.pstdev(vals) / media if media else 0.0
    if registro is not None:
        k["eventos_procesados"] = len(registro)
        k["tiempo_computo_s"] = sum(f.get("tiempo_s", 0.0) for f in registro)
        k["tiempo_solver_s"] = sum(f.get("tiempo_solver_s", 0.0) or 0.0 for f in registro)
        mil = [f for f in registro if f.get("metodo") == "MILP"]
        k["eventos_milp"] = len(mil)
        k["eventos_optimos"] = sum(1 for f in mil if f.get("estado") == "OPTIMO")
        k["eventos_heuristica"] = sum(1 for f in mil if f.get("estado") == "HEURISTICA_VERIFICADA")
        k["eventos_limite_tiempo"] = sum(1 for f in mil if f.get("estado") == "FACTIBLE_LIMITE_TIEMPO")
        k["brecha_max"] = max([f.get("brecha_max") or 0.0 for f in mil], default=0.0)
        k["binarias_max"] = max([f.get("modelo_binarias") or 0 for f in mil], default=0)
        fal = [f for f in registro if f.get("tipo") == "FALLA"]
        k["desviacion_total_h"] = sum(f.get("D_h", 0.0) for f in fal)
        k["reasignaciones"] = sum(f.get("R", 0) for f in fal)
    return dict(k)


def horas_reproceso(inst, programa, parciales):
    """Horas ocupadas por encima del tiempo nominal p_om: lo ejecutado dos veces o repetido tras interrupciones
    (tramos parciales + preparación/verificación repetidas); 0 si no hubo interrupciones."""
    nominal = sum(inst.p[(o, m)] for o, (m, S, C) in programa.items())
    real = sum(C - S for (m, S, C) in programa.values()) + sum(C - S for (_, _, S, C) in parciales)
    return max(0.0, real - nominal)


def por_familia(inst, programa, jobs=None):
    jobs = range(len(inst.jobs)) if jobs is None else jobs
    fam = defaultdict(lambda: dict(pedidos=0, atrasados=0, tardanza_h=0.0, penalidad=0.0))
    for j in jobs:
        jb = inst.jobs[j]
        C = programa[inst.job_ops[j][-1]][2]
        T = max(0.0, C - jb["d"])
        f = fam[jb["familia"]]
        f["pedidos"] += 1
        f["atrasados"] += int(T > EPS)
        f["tardanza_h"] += T
        f["penalidad"] += jb["P"] if T > EPS else 0.0
    return [dict(familia=k, **v, otd_pct=100 * (1 - v["atrasados"] / v["pedidos"])) for k, v in sorted(fam.items())]


# ---------------------------------------------------------------------------------- subproblema (evento único)
def completions(sub, sol):
    full = programa_completo(sub, sol)
    inst = sub.inst
    return {j: full[inst.job_ops[j][-1]][2] for j in sub.jobs if inst.job_ops[j][-1] in full}


def kpis_subproblema(sub, sol, beta=8.0, horas_dia=8.0):
    """KPI de un subproblema reactivo: cumplimiento de sus pedidos y estabilidad frente al programa vigente."""
    inst = sub.inst
    C = completions(sub, sol)
    k = defaultdict(float)
    for j, c in C.items():
        jb = inst.jobs[j]
        T = max(0.0, c - jb["d"])
        tarde = T > EPS
        k["pedidos"] += 1
        k["atrasados"] += tarde
        k["penalidad_estimada"] += jb["P"] if tarde else 0.0
        k["tardanza_total_h"] += T
        k["tardanza_ponderada"] += jb["w"] * T
        k["tardanza_max_h"] = max(k["tardanza_max_h"], T)
    k["otd_pct"] = 100.0 * (1 - k["atrasados"] / k["pedidos"]) if k["pedidos"] else 0.0
    k["makespan_h"] = max(C.values()) if C else 0.0
    D = R = 0.0
    if sub.S0:
        for o in sub.pending:
            D += abs(sol[o][1] - sub.S0[o])
        R = sum(1 for o in sub.free if o in sub.m0 and sol[o][0] != sub.m0[o])
    k["desviacion_total_h"] = D
    k["reasignaciones"] = R
    k["estabilidad_f3"] = D + beta * R
    return dict(k)
