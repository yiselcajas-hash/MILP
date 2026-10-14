"""Indicadores de desempeño (Capítulo 3, sección de indicadores) calculados sobre el programa completo."""
from __future__ import annotations
from collections import defaultdict
from .verificacion import programa_completo


def completions(sub, sol):
    full = programa_completo(sub, sol)
    inst = sub.inst
    return {j: full[inst.job_ops[j][-1]][2] for j in sub.jobs if inst.job_ops[j][-1] in full}


def evaluar(sub, sol, beta=8.0, horas_dia=8.0, ref_C=None, datos=None):
    inst = sub.inst
    C = completions(sub, sol)
    k = defaultdict(float)
    fam_tarde = defaultdict(int)
    fam_n = defaultdict(int)
    for j, c in C.items():
        jb = inst.jobs[j]
        T = max(0.0, c - jb["d"])
        tarde = T > 1e-6
        k["pedidos"] += 1
        k["atrasados"] += tarde
        k["penalidad"] += jb["P"] if tarde else 0.0
        k["pen_diaria_tope"] += min(jb["pdia"] * T / horas_dia, 0.10 * jb["valor"])
        k["tardanza_h"] += T
        k["tard_pond"] += jb["w"] * T
        k["tard_max_h"] = max(k["tard_max_h"], T)
        k["valor_atrasado"] += jb["valor"] if tarde else 0.0
        fam_n[jb["familia"]] += 1
        fam_tarde[jb["familia"]] += tarde
        if ref_C is not None and j in ref_C:
            k["retraso_propagado_h"] += max(0.0, c - ref_C[j])
            k["atrasados_ref"] += (ref_C[j] - jb["d"]) > 1e-6
            k["penalidad_ref"] += jb["P"] if (ref_C[j] - jb["d"]) > 1e-6 else 0.0
    k["otd_pct"] = 100.0 * (1 - k["atrasados"] / k["pedidos"]) if k["pedidos"] else 0.0
    k["tardanza_dias"] = k["tardanza_h"] / horas_dia
    k["cmax"] = max(C.values()) if C else 0.0
    # estabilidad (sólo si hay programa vigente)
    D = R = SEQ = 0.0
    movidas_dia = 0
    if sub.S0:
        for o in sub.pending:
            dlt = abs(sol[o][1] - sub.S0[o])
            D += dlt
            movidas_dia += dlt >= horas_dia - 1e-9
        R = sum(1 for o in sub.free if o in sub.m0 and sol[o][0] != sub.m0[o])
        fr = [o for o in sub.free if o in sub.m0]
        for a in range(len(fr)):
            for b in range(a + 1, len(fr)):
                o1, o2 = fr[a], fr[b]
                if sub.m0[o1] == sub.m0[o2] == sol[o1][0] == sol[o2][0]:
                    if (sub.S0[o1] < sub.S0[o2]) != (sol[o1][1] < sol[o2][1]):
                        SEQ += 1
    k["D"] = D
    k["R"] = R
    k["SEQ"] = SEQ
    k["f2"] = D + beta * R
    k["ops_movidas_mas_1dia"] = movidas_dia
    # sostenibilidad: energía de las operaciones decididas y reprocesos por interrupción
    if datos is not None:
        e = 0.0
        for o, (m, S) in sol.items():
            mq = datos.maquinas.get(m)
            if mq:
                e += sub.pR[(o, m)] * mq.potencia_kw * mq.factor_carga
        k["energia_kwh"] = e
        rep_kg = 0.0
        rep_kwh = 0.0
        for o, inf in sub.info.items():
            if not inf.get("unidades"):
                continue
            kdone, reproc = inf["unidades"]
            m = sol[o][0]
            prod = inst.jobs[inst.ops[o]["job"]]["producto"]
            rep_kg += reproc * datos.masa_chapa.get(prod, 0.0)
            # horas repetidas = tiempo restante asignado − tiempo nominal de las unidades no terminadas
            op = inst.ops[o]
            fac = inst.p[(o, m)] / inst.p[(o, op["principal"])] if inst.p[(o, op["principal"])] > 0 else 1.0
            nominal = (op["q"] - kdone) * op["min_unidad"] / 60.0 * fac
            extra = max(0.0, sub.pR[(o, m)] - nominal)
            mq = datos.maquinas.get(m)
            if mq:
                rep_kwh += extra * mq.potencia_kw * mq.factor_carga
        k["material_reproceso_kg"] = rep_kg
        k["energia_reproceso_kwh"] = rep_kwh
    for f in fam_n:
        k[f"atrasados|{f}"] = fam_tarde[f]
        k[f"pedidos|{f}"] = fam_n[f]
    return dict(k)
