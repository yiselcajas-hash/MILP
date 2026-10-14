"""Auditoría INDEPENDIENTE ex post de trabajadores sobre un cronograma de máquinas.

NO es una variable de decisión del MILP ni valida habilidades reales. Busca una
asignación simulada concreta por intervalo productivo, priorizando mantener al
mismo operario en una operación que continúa. Divide el reloj productivo en
tramos de jornada, de modo que el descanso y cierre no computen como trabajo.
"""
from __future__ import annotations

from collections import Counter, defaultdict

import numpy as np
from scipy.optimize import linear_sum_assignment

EPS = 1e-7


class ErrorAuditoriaPersonal(RuntimeError):
    """Cronograma no asignable con habilidades/capacidad del escenario."""


def _limites_jornada(cal, minimo, maximo):
    """Cortes reales del calendario expresados en horas productivas."""
    limites = set()
    for i in cal.prod_idx:
        base = cal.base[i]
        avance = 0.0
        for a, b in cal.tramos:
            avance += b - a
            x = base + avance
            if minimo + EPS < x < maximo - EPS:
                limites.add(round(x, 8))
    return limites


def asignar_personal(inst, programa, escenario="", combinacion="", exigir_cobertura=True):
    """Construye asignación por intervalos máquina–operación–trabajador.

    :param programa: {op_id: (maquina, inicio_h_productivas, fin_h_productivas)}.
    :return: (filas de asignación, auditoría resumida)

    Se permite relevo entre intervalos cuando el emparejamiento lo requiere;
    cada fila identifica exactamente quién atiende una operación durante un tramo.
    La asignación NO se transmite al solver de SAGAPI 1.2.0-beta.
    """
    datos = inst.datos
    habilidades = datos.habilidades
    if not habilidades:
        raise ErrorAuditoriaPersonal("No existe matriz de habilidades. No se puede certificar una asignación.")
    if not programa:
        return [], {"operaciones": 0, "segmentos": 0, "conflictos_h": 0, "relevos": 0}

    n_esperadas = set(programa)
    if any(o < 0 or o >= len(inst.ops) for o in n_esperadas):
        raise ErrorAuditoriaPersonal("El cronograma contiene identificadores de operación inexistentes.")
    trabajadores = sorted(habilidades)
    if len(trabajadores) != len(set(trabajadores)):
        raise ErrorAuditoriaPersonal("Identificadores de operario duplicados.")

    for o, (m, s, c) in programa.items():
        if m not in inst.machines:
            raise ErrorAuditoriaPersonal(f"Operación {o}: máquina desconocida {m}")
        if c <= s + EPS or s < -EPS:
            raise ErrorAuditoriaPersonal(f"Operación {o}: intervalo no válido [{s}, {c}]")
        if c > datos.calendario.total + EPS:
            raise ErrorAuditoriaPersonal(f"Operación {o}: termina más allá del horizonte calendario registrado; ampliar 07_CALENDARIO.")
        if not any(m in habilidades[w] for w in trabajadores):
            raise ErrorAuditoriaPersonal(f"Operación {o}: no existe operario habilitado para {m}.")

    minimo = min(s for _, s, _ in programa.values())
    maximo = max(c for _, _, c in programa.values())
    puntos = {round(x, 8) for _, s, c in programa.values() for x in (s, c)}
    puntos |= _limites_jornada(datos.calendario, minimo, maximo)
    puntos = sorted(puntos)
    if len(puntos) < 2:
        raise ErrorAuditoriaPersonal("Cronograma sin intervalos positivos")

    segmentos = []
    asign_prev = {}
    relevos = 0
    conflictos_h = 0.0
    intervalos_en_conflicto = 0
    pares_maquina = []
    carga = defaultdict(float)
    ultimo_operario = {}
    num_tramos = 0

    for a, b in zip(puntos, puntos[1:]):
        if b - a <= EPS:
            continue
        mid = (a + b) / 2
        activos = sorted(o for o, (m, s, c) in programa.items() if s < mid < c)
        if not activos:
            asign_prev = {}
            continue
        num_tramos += 1
        por_maquina = Counter(programa[o][0] for o in activos)
        dobles = [m for m, cnt in por_maquina.items() if cnt > 1]
        if dobles:
            pares_maquina.extend((a, b, m) for m in dobles)

        # Solver de asignación bipartita por intervalo: continuidad primero,
        # luego desempate determinista por identificador de trabajador.
        costes = np.full((len(activos), len(trabajadores)), 1e9, dtype=float)
        for i, o in enumerate(activos):
            m = programa[o][0]
            previo = asign_prev.get(o)
            for j, w in enumerate(trabajadores):
                if m in habilidades[w]:
                    costes[i, j] = (0 if w == previo else 10000) + j * 0.00001
        filas, cols = linear_sum_assignment(costes)
        emparejamiento = {activos[i]: trabajadores[j] for i, j in zip(filas, cols) if costes[i, j] < 1e8}
        if len(emparejamiento) != len(activos) or dobles:
            intervalos_en_conflicto += 1
            conflictos_h += b - a
            if exigir_cobertura:
                faltantes = [inst.op_label(o) for o in activos if o not in emparejamiento]
                raise ErrorAuditoriaPersonal(
                    f"Intervalo productivo [{a:.4f},{b:.4f}]: {len(activos)} operaciones, "
                    f"{len(emparejamiento)} operarios, máquinas solapadas={dobles}, sin cobertura={faltantes}"
                )
        if len(set(emparejamiento.values())) != len(emparejamiento):
            raise ErrorAuditoriaPersonal("Se detectó una asignación duplicada de trabajador")

        for o in activos:
            w = emparejamiento.get(o)
            if w is None:
                continue
            m, s, c = programa[o]
            op = inst.ops[o]
            job = inst.jobs[op["job"]]
            if o in ultimo_operario and ultimo_operario[o] != w:
                relevos += 1
            ultimo_operario[o] = w
            carga[w] += b - a
            segmentos.append(dict(
                escenario=escenario, combinacion=combinacion,
                pedido=job["id"], familia=job["familia"], operacion_id=o,
                paso=op["paso"], operacion=op["operacion"],
                maquina=m, trabajador_simulado=w,
                inicio_h=round(a, 6), fin_h=round(b, 6), duracion_h=round(b - a, 6),
                inicio_reloj=datos.calendario.a_fecha(a, "inicio").isoformat(sep=" "),
                fin_reloj=datos.calendario.a_fecha(b, "fin").isoformat(sep=" "),
                origen_habilidades="SIMULADO_NO_VERIFICADO",
                metodo_asignacion="EMPAREJAMIENTO_EX_POST_NO_INTEGRADO_MILP",
            ))
        asign_prev = emparejamiento

    # Cada operación debe tener exactamente su duración de cobertura asignada.
    asignadas = defaultdict(float)
    for r in segmentos:
        asignadas[r["operacion_id"]] += r["duracion_h"]
    faltantes = [(o, programa[o][2]-programa[o][1], asignadas[o]) for o in programa
                 if abs((programa[o][2]-programa[o][1])-asignadas[o]) > 1e-3]
    if faltantes and exigir_cobertura:
        raise ErrorAuditoriaPersonal(f"Duración sin cobertura laboral (primeras): {faltantes[:3]}")

    auditoria = dict(
        escenario=escenario, combinacion=combinacion,
        operaciones_programadas=len(programa), operaciones_con_cobertura=len(asignadas),
        trabajadores_disponibles=len(trabajadores), trabajadores_utilizados=len(carga),
        segmentos=len(segmentos), tramos_productivos=num_tramos,
        conflictos_h=round(conflictos_h, 6), intervalos_con_conflicto=intervalos_en_conflicto,
        solapamientos_maquina=len(pares_maquina), operaciones_sin_cobertura=len(faltantes),
        relevos_intraproceso=relevos, horas_hombre_asignadas=round(sum(carga.values()), 5),
        horas_productivas_de_operaciones=round(sum(c-s for _,s,c in programa.values()), 5),
        matriz_habilidades="SIMULADA", validacion_real="PENDIENTE",
        integracion_al_milp="NO; AUDITORIA EX POST",
        nota="Los tiempos productivos excluyen refrigerio, noches y dias no productivos; no equivalen a competencias reales certificadas.",
    )
    return segmentos, auditoria
