"""Conjuntos y parámetros del modelo a partir del modelo de datos validado.

Conjuntos
  J    pedidos;  O operaciones (j, paso);  O_j operaciones del pedido j en orden de ruta
  M    unidades de recurso (un recurso con cantidad k > 1 se expande en k unidades idénticas m#1..m#k)
  M_o  unidades elegibles para la operación o
  O^N  operaciones no interrumpibles (deben completarse dentro de un tramo continuo; p. ej. ciclo de horno)
Parámetros
  r_j liberación y d_j vencimiento (horas productivas, desde 11_PARAMETROS: hora_liberacion / hora_vencimiento)
  w_j = valor_j / valor medio;  P_j penalidad fija estimada;  p_om tiempo de proceso (h);  c_o personas requeridas
"""
from __future__ import annotations

from dataclasses import dataclass, field


def duracion_h(paso: dict, q: int, lote: int, factor: float = 1.0) -> float:
    """p_om = (⌈q/L⌉·setup + q·u)/60 × factor de la máquina (misma fórmula que la carga del Excel)."""
    lotes = -(-q // lote)
    return (lotes * paso["setup_min"] + q * paso["min_unidad"]) / 60.0 * factor


def recurso_base(m: str) -> str:
    return str(m).split("#")[0]


@dataclass
class Instancia:
    datos: object
    jobs: list
    ops: list
    job_ops: dict
    elig: dict
    p: dict
    machines: list
    fam_jobs: dict = field(default_factory=dict)
    unidades: dict = field(default_factory=dict)       # recurso base -> [unidades]
    L_segmento: float = 4.0

    def pred(self, o):
        seq = self.job_ops[self.ops[o]["job"]]
        k = self.ops[o]["pos"]
        return seq[k - 1] if k > 0 else None

    def succ(self, o):
        seq = self.job_ops[self.ops[o]["job"]]
        k = self.ops[o]["pos"]
        return seq[k + 1] if k + 1 < len(seq) else None

    def op_label(self, o):
        op = self.ops[o]
        return f"{self.jobs[op['job']]['id']}-{op['paso']:02d}"

    def no_partible(self, o):
        return not self.ops[o]["interrumpible"]


def construir(d, pedidos=None, usar_alternativas=True, regla_continuidad=None):
    """pedidos: lista de dicts de pedido (por defecto d.pedidos); permite escenarios transformados.
    regla_continuidad: TRAMO | JORNADA | NINGUNA (por defecto, parámetro lote_no_cruza de la base)."""
    cal = d.calendario
    peds = d.pedidos if pedidos is None else pedidos
    regla = regla_continuidad or str(d.parametros.get("lote_no_cruza") or "TRAMO")
    if regla not in ("TRAMO", "JORNADA", "NINGUNA"):
        raise ValueError(f"regla de continuidad desconocida: {regla} (TRAMO | JORNADA | NINGUNA)")
    unidades = {}
    for m, maq in d.maquinas.items():
        k = int(maq.cantidad or 0)
        if k >= 1:
            unidades[m] = [m] if k == 1 else [f"{m}#{u}" for u in range(1, k + 1)]
    jobs, ops, job_ops, elig, p = [], [], {}, {}, {}
    usados = set()
    for j, pe in enumerate(peds):
        jobs.append(dict(idx=j, id=pe["id"], familia=pe["familia"], producto=pe["producto"], q=pe["q"],
                         r=cal.a_horas(pe["liberacion_h"]), d=cal.a_horas(pe["vencimiento_h"]),
                         w=pe["w"], P=pe["pen_fija"], pdia=pe["pen_dia_sens"], valor=pe["valor"], tope=pe["tope"],
                         compromiso=pe["compromiso"], liberacion=pe["liberacion"], naturaleza=pe.get("naturaleza", "")))
        job_ops[j] = []
        for k, paso in enumerate(d.rutas[pe["producto"]]):
            o = len(ops)
            ops.append(dict(idx=o, job=j, pos=k, paso=paso["paso"], operacion=paso["operacion"], principal=paso["maquina"],
                            trato=paso["trato"], setup_min=paso["setup_min"], min_unidad=paso["min_unidad"],
                            lote=pe["lote"], q=pe["q"], crew=int(paso.get("trabajadores", 1)),
                            interrumpible=bool(paso.get("interrumpible", 1))))
            job_ops[j].append(o)
            cand = d.elegibilidad.get((pe["producto"], paso["paso"]), [(paso["maquina"], "PRINCIPAL", 1.0)])
            if not usar_alternativas:
                cand = [c for c in cand if c[0] == paso["maquina"]]
            elig[o] = []
            for (m, tipo, fac) in cand:
                for u in unidades.get(m, []):
                    elig[o].append(u)
                    usados.add(u)
                    p[(o, u)] = round(duracion_h(paso, pe["q"], pe["lote"], fac if m != paso["maquina"] else 1.0), 6)
            if not elig[o]:
                raise ValueError(f"Operación {pe['id']}-{paso['paso']}: sin unidades de recurso disponibles")
    # M: todas las unidades de recursos que aparecen en alguna ruta o elegibilidad del catálogo (como en v1.4)
    machines = sorted({u for prod in d.rutas for r in d.rutas[prod] for u in unidades.get(r["maquina"], [])} |
                      {u for v in d.elegibilidad.values() for (m, _, _) in v for u in unidades.get(m, [])})
    fam = {}
    for jb in jobs:
        fam.setdefault(jb["familia"], []).append(jb["idx"])
    # NINGUNA desactiva R12 (solo para reproducir v1.4 en las pruebas de regresión; no es una regla de planta)
    L = 0.0 if regla == "NINGUNA" else cal.longitud_segmento(regla)
    return Instancia(d, jobs, ops, job_ops, elig, p, machines, fam, unidades, L)
