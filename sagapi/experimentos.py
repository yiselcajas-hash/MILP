"""Experimentos del Capítulo 4 (todos leen la base Excel y escriben CSV/JSON en la carpeta de resultados).

E1  Año 2025 por eventos (horizonte rodante): programación FIFO/EDD/MILP × reacción CONV/EDD/MILP,
    sin fallas (S00) y con las 12 fallas de la plegadora (S20A).
E2  Escenarios de falla individuales y simultáneos (S01–S19, políticas A y B) sobre dos programas
    vigentes: el FIFO de 16_PROGRAMA_BASE y el programa MILP del año sin fallas.
    Métodos: CONV, EDD, MILP-MONO (P1→P2) y MILP-LEX (P1→P2→P3).
E2b Fallas recurrentes S14 (F01→F02→F14) con reprogramación en cada evento.
E3  Frentes ε-restricción f1b–f2 (con f1 = f1*) en escenarios seleccionados.
E4  Sensibilidad (hoja 27_SENSIBILIDAD).
"""
from __future__ import annotations
import copy
import json
import random
import os
import time
from collections import defaultdict

import pandas as pd

from . import datos as D, instancia, estado, reglas, optimizacion as opt, simulacion as sim
from .indicadores import evaluar, completions
from .verificacion import verificar, control_personal, programa_completo

EPS = 1e-6


def _ventanas(d, eventos, mult=1.0):
    cal = d.calendario
    out = []
    for ev in eventos:
        f = d.fallas[ev]
        a = cal.a_horas(f["inicio"])
        b = cal.a_horas(f["fin"])
        b = a + (b - a) * mult
        out.append((f["maquina"], a, b))
    return out


def evento_unico(d, I, base, eventos, politica="A", beta=8.0, regla_pen="FIJA", tl=(60, 60, 60), mult=1.0,
                 metodos=("CONV", "EDD", "MILP-MONO", "MILP-LEX"), ref_milp=True, ventanas=None):
    """Resuelve un escenario de falla (uno o varios eventos; simultáneos o anunciados) sobre el programa 'base'.
    'ventanas' permite pasar directamente ventanas (m, a, b) en horas productivas (réplicas Monte Carlo)."""
    ws = ventanas if ventanas is not None else _ventanas(d, eventos, mult)
    tb = min(a for (_, a, _) in ws)
    jobs = [j for j in range(len(I.jobs)) if I.jobs[j]["r"] <= tb + EPS and base[I.job_ops[j][-1]][2] > tb + EPS]
    sub = estado.particionar(d, I, base, tb, jobs, ws, politica)
    refC_base = {j: base[I.job_ops[j][-1]][2] for j in jobs}
    filas = []
    sols = {}
    ref_lex = None
    if ref_milp and "MILP-LEX" in metodos:
        sub0 = estado.particionar(d, I, base, tb, jobs, [], politica)
        r0 = opt.lexicografico(sub0, beta=beta, regla_pen=regla_pen, tl=tl)
        if r0["sol"] is not None:
            ref_lex = completions(sub0, r0["sol"])
    for met in metodos:
        t0 = time.perf_counter()
        info = dict(estado="REGLA", tamano={}, pasos=[])
        if met == "CONV":
            sol = reglas.convencional(sub)
        elif met == "EDD":
            sol = reglas.edd(sub)
        elif met == "MILP-MONO":
            r = opt.mono(sub, regla_pen=regla_pen, tl=tl[:2])
            sol = r["sol"]; info = dict(estado=r["estado_global"], tamano=r["tamano"], pasos=r["pasos"], certificado=r.get("certificado"))
        elif met == "MILP-LEX":
            r = opt.lexicografico(sub, beta=beta, regla_pen=regla_pen, tl=tl)
            sol = r["sol"]; info = dict(estado=r["estado_global"], tamano=r["tamano"], pasos=r["pasos"], certificado=r.get("certificado"))
        dtime = time.perf_counter() - t0
        viol = verificar(sub, sol) if sol is not None else ["sin solución"]
        pc = control_personal(d, programa_completo(sub, sol)) if sol is not None else None
        ref = ref_lex if (met.startswith("MILP") and ref_lex is not None) else refC_base
        k = evaluar(sub, sol, beta=beta, ref_C=ref, datos=d) if sol is not None else {}
        fila = dict(metodo=met, t_b=tb, fecha_falla=d.calendario.a_fecha(tb), pedidos_instancia=len(jobs), ops_libres=len(sub.free),
                    interrumpidas=len(sub.interrupted), violaciones=len(viol), estado=info["estado"], certificado=info.get("certificado"),
                    tiempo_s=dtime,
                    conflictos_personal=(pc[0] if pc is not None else None),
                    conflictos_personal_h=(pc[1] if pc is not None else None),
                    **{f"modelo_{a}": b for a, b in info["tamano"].items()}, **k)
        for p in info["pasos"]:
            tag = p["paso"].split()[0]
            fila[f"{tag}_estado"] = p["estado"]; fila[f"{tag}_brecha"] = p["brecha"]; fila[f"{tag}_tiempo"] = p["tiempo"]
        filas.append(fila)
        sols[met] = sol
    return filas, sub, sols


def _kpis_subconjunto(I, programa, jobs, beta=8.0):
    out = defaultdict(float)
    for j in jobs:
        jb = I.jobs[j]
        C = programa[I.job_ops[j][-1]][2]
        T = max(0.0, C - jb["d"])
        out["pedidos"] += 1
        out["atrasados"] += T > EPS
        out["penalidad"] += jb["P"] if T > EPS else 0
        out["tardanza_h"] += T
        out["tard_pond"] += jb["w"] * T
    out["otd_pct"] = 100 * (1 - out["atrasados"] / max(1, out["pedidos"]))
    return dict(out)


class Experimentos:
    def __init__(self, archivo, salida, tl=(60, 60, 60), log=print):
        self.archivo = archivo
        self.salida = salida
        os.makedirs(salida, exist_ok=True)
        self.d = D.leer(archivo)
        self.I = instancia.construir(self.d)
        self.tl = tl
        self.log = log
        self.beta = float(self.d.parametros.get("Costo equivalente reasignación") or 8)

    # ------------------------------------------------------------------------------ E0
    def e0_fifo(self):
        d, I = self.d, self.I
        cal = d.calendario
        plan, _ = reglas.fifo_plan(I, range(len(I.jobs)))
        idx = {(I.jobs[I.ops[o]["job"]]["id"], I.ops[o]["paso"]): o for o in range(len(I.ops))}
        maxdif, n = 0.0, 0
        for b in d.programa_base:
            o = idx[(b["pedido"], b["paso"])]
            maxdif = max(maxdif, abs(plan[o][1] - cal.a_horas(b["inicio"])), abs(plan[o][2] - cal.a_horas(b["fin"])))
            n += b["maquina"] == plan[o][0]
        res = dict(operaciones=len(d.programa_base), misma_maquina=n, max_dif_h=maxdif, reproduce=maxdif < 1e-3 and n == len(d.programa_base))
        json.dump(res, open(os.path.join(self.salida, "E0_reproduccion_fifo.json"), "w"), indent=1, default=str)
        return res

    # ------------------------------------------------------------------------------ E1
    def e1_anual(self, combinaciones=None, escenarios=("S00", "S20A"), regla_pen="FIJA", etiqueta=""):
        d, I = self.d, self.I
        combinaciones = combinaciones or [("FIFO", "CONV"), ("FIFO", "MILP"), ("EDD", "EDD"), ("MILP", "CONV"), ("MILP", "MILP")]
        fallas12 = [f"F{k:02d}" for k in range(1, 13)]
        filas, fam_rows, det_rows, reg_rows = [], [], [], []
        programas = {}
        for esc in escenarios:
            evs = [] if esc == "S00" else fallas12
            for plan, reac in combinaciones:
                if esc == "S00" and reac != "CONV" and plan in ("FIFO", "MILP"):
                    # sin fallas la reacción no interviene: se reutiliza la corrida con CONV
                    continue
                t0 = time.perf_counter()
                prog, reg = sim.simular(d, I, plan, reac, evs, beta=self.beta, regla_pen=regla_pen, tl=self.tl)
                k, fam, det = sim.kpis_anuales(I, prog)
                pc = control_personal(d, prog)
                energia = sum((C - S) * d.maquinas[m].potencia_kw * d.maquinas[m].factor_carga for o, (m, S, C) in prog.items())
                nom = f"{plan}+{reac}"
                fila = dict(escenario=esc, combinacion=nom, regla_pen=regla_pen, tiempo_total_s=time.perf_counter() - t0,
                            decisiones_milp=sum(1 for r in reg if r["estado"] != "REGLA"),
                            decisiones_optimas=sum(1 for r in reg if r["estado"] == "ÓPTIMO"),
                            max_binarias=max([r["binarias"] or 0 for r in reg]),
                            conflictos_personal_h=(pc[1] if pc else None), energia_kwh=energia, **k)
                filas.append(fila)
                for f, v in fam.items():
                    fam_rows.append(dict(escenario=esc, combinacion=nom, familia=f, **v))
                for r in det:
                    det_rows.append(dict(escenario=esc, combinacion=nom, **r))
                for r in reg:
                    reg_rows.append(dict(escenario=esc, combinacion=nom, **r))
                programas[(esc, nom)] = prog
                self.log(f"E1 {esc} {nom}: atrasados={k['atrasados']:.0f} penalidad={k['penalidad']:.0f} t={fila['tiempo_total_s']:.0f}s")
        suf = f"_{etiqueta}" if etiqueta else ""
        pd.DataFrame(filas).to_csv(os.path.join(self.salida, f"E1_anual{suf}.csv"), index=False)
        pd.DataFrame(fam_rows).to_csv(os.path.join(self.salida, f"E1_familias{suf}.csv"), index=False)
        pd.DataFrame(det_rows).to_csv(os.path.join(self.salida, f"E1_pedidos{suf}.csv"), index=False)
        pd.DataFrame(reg_rows).to_csv(os.path.join(self.salida, f"E1_registro_decisiones{suf}.csv"), index=False)
        self.programas = programas
        return filas, programas

    def programa_milp_sin_fallas(self):
        prog, _ = sim.simular(self.d, self.I, "MILP", "CONV", [], beta=self.beta, tl=self.tl)
        return prog

    # ------------------------------------------------------------------------------ E2
    def e2_escenarios(self, bases=None, escenarios=None):
        d, I = self.d, self.I
        if bases is None:
            fifo, _ = reglas.fifo_plan(I, range(len(I.jobs)))
            bases = {"FIFO (16_PROGRAMA_BASE)": fifo, "MILP (año sin fallas)": self.programa_milp_sin_fallas()}
        filas = []
        for e in d.escenarios:
            sid = e["id"]
            if sid in ("S00",) or sid.startswith("S20") or sid.startswith("S14"):
                continue
            if escenarios and sid not in escenarios:
                continue
            evs = [x for x in e["eventos"].split("+") if x]
            for nb, base in bases.items():
                rows, sub, sols = evento_unico(d, I, base, evs, e["politica"], beta=self.beta, tl=self.tl)
                for r in rows:
                    r.update(escenario=sid, caso=e["caso"], eventos=e["eventos"], politica=e["politica"], programa_base=nb,
                             maquinas=";".join(sorted({d.fallas[x]["maquina"] for x in evs})))
                    filas.append(r)
                lex = [r for r in rows if r["metodo"] == "MILP-LEX"][0]
                conv = [r for r in rows if r["metodo"] == "CONV"][0]
                self.log(f"E2 {sid} [{nb[:4]}] CONV atr={conv['atrasados']:.0f} pen={conv['penalidad']:.0f} | "
                         f"LEX atr={lex['atrasados']:.0f} pen={lex['penalidad']:.0f} {lex['estado']} {lex['tiempo_s']:.1f}s")
        df = pd.DataFrame(filas)
        df.to_csv(os.path.join(self.salida, "E2_escenarios.csv"), index=False)
        return df

    def e2b_recurrentes(self, eventos=("F01", "F02", "F14"), politica="A"):
        d, I = self.d, self.I
        cal = d.calendario
        ws = _ventanas(d, eventos)
        t1, tn = min(a for _, a, _ in ws), max(a for _, a, _ in ws)
        fifo, _ = reglas.fifo_plan(I, range(len(I.jobs)))
        jobs = [j for j in range(len(I.jobs)) if I.jobs[j]["r"] <= tn + EPS and fifo[I.job_ops[j][-1]][2] > t1 + EPS]
        filas = []
        for reac in ("CONV", "EDD", "MILP"):
            t0 = time.perf_counter()
            prog, reg = sim.simular(d, I, "FIFO", reac, list(eventos), politica=politica, beta=self.beta, tl=self.tl)
            k = _kpis_subconjunto(I, prog, jobs)
            filas.append(dict(escenario="S14" + politica, reaccion=reac, eventos="+".join(eventos), tiempo_s=time.perf_counter() - t0,
                              estados=";".join(r["estado"] for r in reg if r["tipo"] == "FALLA"), **k))
            self.log(f"E2b S14{politica} {reac}: atrasados={k['atrasados']:.0f} penalidad={k['penalidad']:.0f}")
        ref = _kpis_subconjunto(I, fifo, jobs)
        filas.append(dict(escenario="S14" + politica, reaccion="SIN FALLA (FIFO)", eventos="", **ref))
        df = pd.DataFrame(filas)
        df.to_csv(os.path.join(self.salida, f"E2b_recurrentes_{politica}.csv"), index=False)
        return df

    # ------------------------------------------------------------------------------ E5
    def e5_montecarlo(self, n=None, semilla=None, politicas=("A", "B")):
        """Robustez: n fallas de la máquina crítica en instantes al azar dentro de sus operaciones del programa FIFO
        vigente; duración remuestreada de las horas de turno de F01–F12 (19_PARAMETROS)."""
        d, I = self.d, self.I
        n = int(n or d.parametros.get("Réplicas Monte Carlo de fallas de la plegadora") or 40)
        semilla = int(semilla or d.parametros.get("Semilla Monte Carlo") or 2025200)
        rng = random.Random(semilla)
        crit = d.maquina_critica()
        fifo, _ = reglas.fifo_plan(I, range(len(I.jobs)))
        ops_crit = sorted((S, C, o) for o, (m, S, C) in fifo.items() if m == crit)
        dur = [d.calendario.a_horas(d.fallas[f"F{k:02d}"]["fin"]) - d.calendario.a_horas(d.fallas[f"F{k:02d}"]["inicio"])
               for k in range(1, 13)]
        filas = []
        for rep in range(n):
            S, C, o = ops_crit[rng.randrange(len(ops_crit))]
            a = round(S + rng.uniform(0.05, 0.95) * (C - S), 4)
            b = round(a + rng.choice(dur), 4)
            for pol in politicas:
                rows, sub, _ = evento_unico(d, I, fifo, [], pol, beta=self.beta, tl=self.tl,
                                            metodos=("CONV", "EDD", "MILP-LEX"), ventanas=[(crit, a, b)])
                for r in rows:
                    r.update(replica=rep, politica=pol, operacion=I.op_label(o), duracion_h=b - a)
                    filas.append(r)
            lex = [r for r in filas if r["replica"] == rep and r["metodo"] == "MILP-LEX"]
            self.log(f"E5 réplica {rep}: " + "; ".join(f"{r['politica']} {r['estado']} {r['tiempo_s']:.1f}s" for r in lex))
        df = pd.DataFrame(filas)
        df.to_csv(os.path.join(self.salida, "E5_montecarlo.csv"), index=False)
        return df

    # ------------------------------------------------------------------------------ E3
    def e3_pareto(self, escenarios=("S06A", "S08A", "S13A", "S19A"), n=7):
        d, I = self.d, self.I
        fifo, _ = reglas.fifo_plan(I, range(len(I.jobs)))
        filas = []
        esc = {e["id"]: e for e in d.escenarios}
        for sid in escenarios:
            e = esc[sid]
            evs = [x for x in e["eventos"].split("+") if x]
            ws = _ventanas(d, evs)
            tb = min(a for _, a, _ in ws)
            jobs = [j for j in range(len(I.jobs)) if I.jobs[j]["r"] <= tb + EPS and fifo[I.job_ops[j][-1]][2] > tb + EPS]
            sub = estado.particionar(d, I, fifo, tb, jobs, ws, e["politica"])
            lex = opt.lexicografico(sub, beta=self.beta, tl=self.tl)
            k_lex = evaluar(sub, lex["sol"], beta=self.beta)
            # extremo de máxima estabilidad con f1 = f1*: min f2 | f1<=f1*, luego min f1b | f2<=f2*
            mdl = lex["mdl"]
            from .solver import INF
            cap1 = k_lex["penalidad"] + 1e-4
            r_a, s_a = opt._resolver(mdl, mdl.f2_terms(), self.tl[2], lex["sol"], [(mdl.f1_terms(), -INF, cap1)])
            f2star = r_a["obj"]
            r_b, s_b = opt._resolver(mdl, mdl.f1b_terms(), self.tl[2], s_a,
                                     [(mdl.f1_terms(), -INF, cap1), (mdl.f2_terms(), -INF, f2star + 1e-4)])
            s_b = reglas.reparar(sub, s_b if s_b is not None else s_a)
            k_b = evaluar(sub, s_b, beta=self.beta)
            # niveles ε en términos del modelo (sin las constantes de pedidos ya terminados que sí suma 'evaluar')
            f1b_lex = opt._val(mdl.f1b_terms(), mdl.encode(lex["sol"]))
            f1b_est = opt._val(mdl.f1b_terms(), mdl.encode(s_b))
            pts = opt.epsilon(sub, opt._val(mdl.f1_terms(), mdl.encode(lex["sol"])), f1b_lex, f1b_est, n=n, beta=self.beta,
                              tl=self.tl[2], warm=lex["sol"])
            for p in pts:
                if p["sol"] is None:
                    filas.append(dict(escenario=sid, k=p["k"], eps=p["eps"], estado=p["estado"]))
                    continue
                k = evaluar(sub, p["sol"], beta=self.beta)
                v = verificar(sub, p["sol"])
                filas.append(dict(escenario=sid, k=p["k"], eps=p["eps"], estado=p["estado"], brecha=p["brecha"], tiempo_s=p["tiempo"],
                                  violaciones=len(v), penalidad=k["penalidad"], atrasados=k["atrasados"], tard_pond=k["tard_pond"],
                                  D=k["D"], R=k["R"], SEQ=k["SEQ"], f2=k["f2"]))
            conv = evaluar(sub, reglas.convencional(sub), beta=self.beta)
            filas.append(dict(escenario=sid, k="CONV", penalidad=conv["penalidad"], atrasados=conv["atrasados"], tard_pond=conv["tard_pond"],
                              D=conv["D"], R=conv["R"], SEQ=conv["SEQ"], f2=conv["f2"]))
            self.log(f"E3 {sid}: {len(pts)} puntos")
        df = pd.DataFrame(filas)
        df.to_csv(os.path.join(self.salida, "E3_pareto.csv"), index=False)
        return df

    # ------------------------------------------------------------------------------ E4
    def e4_sensibilidad(self):
        d, I = self.d, self.I
        fifo, _ = reglas.fifo_plan(I, range(len(I.jobs)))
        base_ev = [f"F{k:02d}" for k in range(1, 13)]
        filas = []
        # (a) duración de la avería
        for mult in (0.5, 1.0, 2.0, 4.0):
            for ev in base_ev:
                rows, _, _ = evento_unico(d, I, fifo, [ev], "A", beta=self.beta, tl=self.tl, mult=mult,
                                          metodos=("CONV", "MILP-LEX"), ref_milp=False)
                for r in rows:
                    filas.append(dict(factor="Multiplicador de duración", nivel=mult, evento=ev, **r))
            self.log(f"E4 duración x{mult} listo")
        # (b) β
        for beta in (0.0, 8.0, 24.0):
            for ev in base_ev:
                rows, _, _ = evento_unico(d, I, fifo, [ev], "A", beta=beta, tl=self.tl, metodos=("MILP-LEX",), ref_milp=False)
                for r in rows:
                    filas.append(dict(factor="Peso de reasignación β", nivel=beta, evento=ev, **r))
            self.log(f"E4 beta={beta} listo")
        # (c) regla de penalidad en eventos
        for ev in base_ev:
            rows, _, _ = evento_unico(d, I, fifo, [ev], "A", beta=self.beta, regla_pen="DIARIA_CON_TOPE", tl=self.tl,
                                      metodos=("CONV", "MILP-LEX"), ref_milp=False)
            for r in rows:
                filas.append(dict(factor="Regla de penalidad", nivel="DIARIA_CON_TOPE", evento=ev, **r))
        # (d) factor de tiempo en máquina alternativa
        for fac in (1.0, 1.1, 1.25):
            d2 = copy.deepcopy(d)
            for key, lst in d2.elegibilidad.items():
                d2.elegibilidad[key] = [(m, t, (fac if t == "ALTERNATIVA CON UTILLAJE COMPATIBLE" else f)) for (m, t, f) in lst]
            I2 = instancia.construir(d2)
            fifo2, _ = reglas.fifo_plan(I2, range(len(I2.jobs)))
            for ev in ("F15", "F16"):
                rows, _, _ = evento_unico(d2, I2, fifo2, [ev], "A", beta=self.beta, tl=self.tl, metodos=("CONV", "MILP-LEX"), ref_milp=False)
                for r in rows:
                    filas.append(dict(factor="Factor de tiempo en alternativa", nivel=fac, evento=ev, **r))
        self.log("E4 eventos listos")
        df = pd.DataFrame(filas)
        df.to_csv(os.path.join(self.salida, "E4_sensibilidad_eventos.csv"), index=False)
        return df

    def e4_anual_sensibilidad(self):
        """Regla de penalidad diaria y calendario con feriados en el año completo."""
        filas = []
        f, _ = self.e1_anual(combinaciones=[("FIFO", "CONV"), ("MILP", "MILP")], escenarios=("S00", "S20A"),
                             regla_pen="DIARIA_CON_TOPE", etiqueta="penalidad_diaria")
        for r in f:
            filas.append(dict(factor="Regla de penalidad", nivel="DIARIA_CON_TOPE", **r))
        d_fer = D.leer(self.archivo)
        d_fer.parametros["Aplicar feriados nacionales (1/0)"] = 1
        # recargar calendario con feriados
        import openpyxl
        from .calendario import Calendario
        wb = openpyxl.load_workbook(self.archivo, read_only=True)
        dias = []
        enc = None
        for row in wb["07_CALENDARIO"].iter_rows(values_only=True):
            if enc is None:
                enc = list(row); continue
            fila = dict(zip(enc, row))
            if fila.get("Fecha") is None:
                continue
            p = (fila.get("Productivo (1/0)") == 1) and not (fila.get("Feriado nacional Perú") or "")
            dias.append((fila["Fecha"].date(), p))
        d_fer.calendario = Calendario(sorted(dias))
        I_fer = instancia.construir(d_fer)
        for plan, reac in (("FIFO", "CONV"), ("MILP", "MILP")):
            for esc, evs in (("S00", []), ("S20A", [f"F{k:02d}" for k in range(1, 13)])):
                prog, reg = sim.simular(d_fer, I_fer, plan, reac, evs, beta=self.beta, tl=self.tl)
                k, fam, _ = sim.kpis_anuales(I_fer, prog)
                filas.append(dict(factor="Calendario con feriados", nivel=1, escenario=esc, combinacion=f"{plan}+{reac}", **k))
                self.log(f"E4 feriados {esc} {plan}+{reac}: atrasados={k['atrasados']:.0f}")
        df = pd.DataFrame(filas)
        df.to_csv(os.path.join(self.salida, "E4_sensibilidad_anual.csv"), index=False)
        return df
