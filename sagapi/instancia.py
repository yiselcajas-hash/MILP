"""Construcción de conjuntos y parámetros del modelo a partir de la base leída.

Conjuntos (notación del Capítulo 3):
  J   pedidos (órdenes de producción) ; F familias ; M máquinas ; O operaciones (pedido, paso)
  O_j operaciones del pedido j en orden de ruta ; M_o máquinas elegibles para o
Parámetros:
  r_j liberación, d_j vencimiento (h productivas), w_j peso, P_j penalidad fija (S/), p_om tiempo (h)
"""
from __future__ import annotations
from dataclasses import dataclass, field
from .datos import Datos, duracion_h


@dataclass
class Instancia:
    datos: Datos
    jobs: list                 # dicts: id, idx, familia, producto, q, r, d, w, P, pdia, valor
    ops: list                  # dicts: idx, job, paso, operacion, principal, trato, setup_min, min_unidad, lote, q
    job_ops: dict              # job idx -> [op idx]
    elig: dict                 # op -> [m]
    p: dict                    # (op, m) -> h
    machines: list             # nombres
    fam_jobs: dict = field(default_factory=dict)

    def pred(self, o):
        j = self.ops[o]["job"]
        seq = self.job_ops[j]
        k = seq.index(o)
        return seq[k - 1] if k > 0 else None

    def succ(self, o):
        j = self.ops[o]["job"]
        seq = self.job_ops[j]
        k = seq.index(o)
        return seq[k + 1] if k + 1 < len(seq) else None

    def op_label(self, o):
        op = self.ops[o]
        return f"{self.jobs[op['job']]['id']}-{op['paso']:02d}"


def construir(d: Datos, pedidos=None, usar_alternativas=True) -> Instancia:
    cal = d.calendario
    peds = d.pedidos if pedidos is None else [p for p in d.pedidos if p["id"] in set(pedidos)]
    machines = sorted({r["maquina"] for prod in d.rutas for r in d.rutas[prod]} |
                      {m for v in d.elegibilidad.values() for (m, _, _) in v})
    jobs, ops, job_ops, elig, p = [], [], {}, {}, {}
    for j, pe in enumerate(peds):
        jobs.append(dict(idx=j, id=pe["id"], familia=pe["familia"], producto=pe["producto"], q=pe["q"],
                         r=cal.a_horas(pe["liberacion"].replace(hour=8, minute=0)),
                         d=cal.fin_de_dia(pe["compromiso"].date()),
                         w=pe["w"], P=pe["pen_fija"], pdia=pe["pen_dia_sens"], valor=pe["valor"],
                         compromiso=pe["compromiso"], liberacion=pe["liberacion"]))
        job_ops[j] = []
        for paso in d.rutas[pe["producto"]]:
            o = len(ops)
            ops.append(dict(idx=o, job=j, paso=paso["paso"], operacion=paso["operacion"], principal=paso["maquina"],
                            trato=paso["trato"], setup_min=paso["setup_min"], min_unidad=paso["min_unidad"],
                            lote=pe["lote"], q=pe["q"]))
            job_ops[j].append(o)
            cand = d.elegibilidad.get((pe["producto"], paso["paso"]), [(paso["maquina"], "PRINCIPAL", 1.0)])
            if not usar_alternativas:
                cand = [c for c in cand if c[0] == paso["maquina"]]
            elig[o] = []
            for (m, tipo, fac) in cand:
                elig[o].append(m)
                p[(o, m)] = round(duracion_h(paso, pe["q"], pe["lote"], fac if m != paso["maquina"] else 1.0), 6)
    fam = {}
    for jb in jobs:
        fam.setdefault(jb["familia"], []).append(jb["idx"])
    return Instancia(d, jobs, ops, job_ops, elig, p, machines, fam)
