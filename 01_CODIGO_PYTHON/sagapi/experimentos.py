"""Experimentos computacionales reproducibles. Todo resultado se escribe desde corridas reales del programa.

E0  Validación de datos e instancia: calidad de la base, tamaño, certificado laboral, carga por recurso,
    tardanza inevitable (cota inferior) y diagnóstico del cuello de botella.
E1  Año completo por eventos (horizonte rodante): S00 (sin averías) y S20A (F01–F12) con FIFO+CONV, FIFO+MILP,
    EDD+EDD, MILP+CONV y MILP+MILP; mismas restricciones y datos para todos los métodos.
E2  Escenarios de avería de 24_ESCENARIOS_FALLA_SIM sobre el plan FIFO (práctica actual) con reacción CONV, EDD y
    MILP; KPI del sistema completo y su diferencia con el año sin averías (impacto de la falla).
E3  Escenarios operativos de 27_ESCENARIOS_OPERATIVOS_SIM (carga, plazos, ausencias, averías).
E4  Sensibilidad según 26_SENSIBILIDAD_SIM.
E5  Rendimiento: tamaño y tiempo del modelo v2.0 frente a v1.4 en el mismo subproblema; presolve de HiGHS.
Todos los escenarios son SIMULADOS (pedidos, averías y habilidades) y se rotulan así en cada tabla.
"""
from __future__ import annotations

import csv
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from . import __version__, escenarios as esc, estado, instancia, optimizacion as opt, personal as pers, reglas
from . import indicadores as K
from . import simulacion as sim
from .datos import cargar_base
from .explicabilidad import cambios
from .solver import version_highs
from .verificacion import programa_completo as verificacion_programa_completo, verificar_subproblema

COMBINACIONES = [("FIFO", "CONV"), ("FIFO", "MILP"), ("EDD", "EDD"), ("MILP", "CONV"), ("MILP", "MILP")]
EPS = 1e-6
SUB = {"milp": "Resultados_MILP", "comp": "Comparacion_MILP_FIFO", "kpi": "Indicadores_KPI", "esc": "Escenarios"}


def escribir_csv(ruta, filas, campos=None):
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    filas = list(filas)
    if campos is None:
        campos = []
        for f in filas:
            for k in f:
                if k not in campos:
                    campos.append(k)
    with ruta.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=campos, extrasaction="ignore")
        w.writeheader()
        for f in filas:
            w.writerow({k: _fmt(f.get(k)) for k in campos})
    return ruta


def escribir_calendario(d, ruta):
    """Días productivos del eje de tiempo: día k ↔ fecha y horas [k·h_dia, (k+1)·h_dia)."""
    cal = d.calendario
    return escribir_csv(ruta, [dict(dia=k, fecha=cal.fechas[i], hora_inicio=k * cal.h_dia, hora_fin=(k + 1) * cal.h_dia)
                               for k, i in enumerate(cal.prod_idx)])


def _fmt(v):
    if isinstance(v, float):
        return f"{v:.6f}".rstrip("0").rstrip(".") if abs(v) < 1e15 else v
    if isinstance(v, (list, tuple, set)):
        return ";".join(map(str, v))
    return v


class Experimentos:
    def __init__(self, base, salida, tl=None, regla_objetivo=None, tl_personal=None, log=print):
        self.base = str(base)
        self.salida = Path(salida)
        self.log = log
        self.d, self.informe = cargar_base(base)
        d = self.d
        self.regla = regla_objetivo or str(d.p("regla_objetivo") or "TARDANZA_PONDERADA")
        self.beta = float(d.p("beta_reasignacion") or 8.0)
        self.H = float(d.p("horizonte_congelado_h") or 0.0)
        self.tl = float(tl if tl is not None else (d.p("limite_computo_s") or 60.0))
        self.gap = float(d.p("brecha_relativa") or 1e-5)
        self.tl_personal = float(tl_personal or d.p("limite_asignacion_personal_s") or 120.0)
        self.inst = instancia.construir(d)
        self.dot = pers.dotacion(d)
        self._s00 = {}
        for k in SUB.values():
            (self.salida / k).mkdir(parents=True, exist_ok=True)

    def ruta(self, sub, nombre):
        return self.salida / SUB[sub] / nombre

    # ------------------------------------------------------------------------------------------ utilidades
    def correr(self, plan, reac, eventos=(), inst=None, dot=None, asignar=False, politica="A", regla=None, beta=None,
               congelar_h=None, mult_falla=1.0, datos=None):
        datos = datos or self.d
        inst = inst or self.inst
        res = sim.simular(datos, inst, plan, reac, eventos, politica=politica, regla_objetivo=regla or self.regla,
                          beta=self.beta if beta is None else beta, tl=self.tl, gap=self.gap,
                          congelar_h=self.H if congelar_h is None else congelar_h, dot=dot or self.dot,
                          asignar_personal=asignar, tl_personal=self.tl_personal, mult_falla=mult_falla)
        if res.verificacion["total"]:
            raise sim.ErrorSimulacion(f"{res.combinacion}: el verificador independiente encontró {res.verificacion}")
        k = K.kpis_programa(inst, res.programa, datos, parciales=res.parciales, ventanas=res.ventanas,
                            registro=res.registro, cargas=(res.asignacion_info or {}).get("cargas"))
        fila = dict(combinacion=res.combinacion, plan=plan, reaccion=reac, regla_objetivo=res.regla_objetivo,
                    politica=politica, eventos="+".join(e if isinstance(e, str) else e[0] for e in eventos),
                    verificacion_violaciones=res.verificacion["total"], modo_personal=res.modo_personal,
                    asignacion_personal=(res.asignacion_info or {}).get("estado", "NO_CALCULADA"),
                    tiempo_total_s=res.tiempo_total_s, **k)
        return res, fila

    def guardar_corrida(self, res, etiqueta, datos=None, inst=None):
        datos, inst = datos or self.d, inst or self.inst
        cal = datos.calendario
        asig = res.asignacion or {}
        filas = []
        for o, (m, S, C) in sorted(res.programa.items(), key=lambda kv: (kv[1][1], kv[0])):
            op = inst.ops[o]
            jb = inst.jobs[op["job"]]
            filas.append(dict(pedido=jb["id"], familia=jb["familia"], producto=jb["producto"], paso=op["paso"],
                              operacion=op["operacion"], unidad=m, recurso=instancia.recurso_base(m), tramo="FINAL",
                              inicio_h=S, fin_h=C, duracion_h=C - S, inicio=cal.a_fecha(S), fin=cal.a_fecha(C, "fin"),
                              vencimiento_h=jb["d"], trabajadores=asig.get(("F", o), [])))
        for i, (o, m, S, C) in enumerate(res.parciales):
            op = inst.ops[o]
            jb = inst.jobs[op["job"]]
            filas.append(dict(pedido=jb["id"], familia=jb["familia"], producto=jb["producto"], paso=op["paso"],
                              operacion=op["operacion"], unidad=m, recurso=instancia.recurso_base(m),
                              tramo="PARCIAL_INTERRUMPIDO", inicio_h=S, fin_h=C, duracion_h=C - S, inicio=cal.a_fecha(S),
                              fin=cal.a_fecha(C, "fin"), vencimiento_h=jb["d"], trabajadores=asig.get(("P", i), [])))
        escribir_csv(self.ruta("milp", f"programa_{etiqueta}.csv"), filas)
        escribir_csv(self.ruta("milp", f"eventos_{etiqueta}.csv"), res.registro)
        escribir_csv(self.ruta("milp", f"ventanas_{etiqueta}.csv"),
                     [dict(unidad=u, inicio_h=a, fin_h=b) for (u, a, b) in res.ventanas])
        escribir_csv(self.ruta("kpi", f"pedidos_{etiqueta}.csv"), K.tabla_pedidos(inst, res.programa))
        escribir_csv(self.ruta("kpi", f"utilizacion_{etiqueta}.csv"),
                     K.utilizacion(inst, res.programa, res.parciales, res.ventanas))
        if res.asignacion_info.get("cargas"):
            escribir_csv(self.ruta("kpi", f"carga_trabajadores_{etiqueta}.csv"),
                         [dict(trabajador=w, horas=h, recursos_habilitados=";".join(sorted(self.dot.habilidades.get(w, ()))))
                          for w, h in sorted(res.asignacion_info["cargas"].items())])

    # ------------------------------------------------------------------------------------------ E0
    def e0_validacion(self):
        d, inst = self.d, self.inst
        cal = d.calendario
        cert = pers.certificado_cobertura(self.dot, inst)
        lb = K.cota_inferior_tardanza(inst)
        carga = K.carga_teorica(inst, horas_disponibles=cal.total)
        fifo, _ = reglas.fifo_plan(inst, list(range(len(inst.jobs))), ventanas=[])
        espera = K.espera_por_recurso(inst, fifo)
        ut = {u["unidad"]: u for u in K.utilizacion(inst, fifo)}
        diag = []
        for m in inst.machines:
            diag.append(dict(unidad=m, recurso=instancia.recurso_base(m), nombre=d.nombre_maquina(m),
                             carga_teorica_h=next((c["carga_h"] for c in carga if c["recurso"] == instancia.recurso_base(m)), 0.0),
                             utilizacion_fifo_pct=ut[m]["utilizacion_pct"], espera_cola_fifo_h=espera[m]["espera_total_h"],
                             espera_media_fifo_h=espera[m]["espera_media_h"], operaciones=espera[m]["operaciones"],
                             declarado_critico=int(instancia.recurso_base(m) == d.maquina_critica())))
        diag.sort(key=lambda x: -x["espera_cola_fifo_h"])
        n_inev = sum(1 for v in lb.values() if v > EPS)
        res = dict(version=__version__, highs=version_highs(), base=os.path.basename(self.base),
                   calidad=self.informe.resumen(), procedencia=d.procedencia, pedidos=len(inst.jobs),
                   operaciones=len(inst.ops), unidades=len(inst.machines), regla_continuidad=d.p("lote_no_cruza"),
                   L_segmento_h=inst.L_segmento, horas_productivas_horizonte=cal.total, dias_productivos=len(cal.prod_idx),
                   regla_objetivo=self.regla, beta=self.beta, horizonte_congelado_h=self.H,
                   certificado_personal=dict(ok=cert["ok"], demanda=cert["demanda"], cubierto=cert["cubierto"],
                                             deficit=cert["deficit"], equipos=cert["equipos"],
                                             fuente_habilidades=cert["fuente_habilidades"]),
                   trabajadores=len(self.dot.trabajadores),
                   pedidos_con_tardanza_inevitable=n_inev, tardanza_inevitable_total_h=sum(lb.values()),
                   tardanza_inevitable_ponderada=sum(inst.jobs[j]["w"] * v for j, v in lb.items()),
                   recurso_mayor_espera_fifo=diag[0]["recurso"], recurso_mayor_utilizacion_fifo=max(
                       diag, key=lambda x: x["utilizacion_fifo_pct"])["recurso"],
                   maquina_critica_declarada=d.maquina_critica())
        json.dump(res, open(self.ruta("milp", "E0_validacion.json"), "w", encoding="utf-8"), indent=1,
                  ensure_ascii=False, default=str)
        escribir_csv(self.ruta("kpi", "E0_diagnostico_cuello_botella.csv"), diag)
        escribir_csv(self.ruta("kpi", "E0_carga_teorica_recursos.csv"), carga)
        escribir_csv(self.ruta("kpi", "E0_cota_inferior_tardanza.csv"),
                     [dict(pedido=inst.jobs[j]["id"], r_h=inst.jobs[j]["r"], d_h=inst.jobs[j]["d"],
                           ruta_minima_h=inst.jobs[j]["d"] - inst.jobs[j]["r"] + v if v > 0 else None,
                           tardanza_inevitable_h=v) for j, v in lb.items()])
        escribir_csv(self.ruta("kpi", "KPI_definiciones.csv"), K.tabla_definiciones())
        escribir_calendario(d, self.ruta("milp", "calendario_productivo.csv"))
        escribir_csv(self.ruta("milp", "E0_calidad_datos.csv"), [p.__dict__ for p in self.informe.problemas])
        self.log(f"E0 pedidos={len(inst.jobs)} ops={len(inst.ops)} certificado={cert['ok']} "
                 f"tardanza inevitable: {n_inev} pedidos")
        return res

    # ------------------------------------------------------------------------------------------ E1
    def e1_anual(self):
        filas, fam = [], []
        e20, pol20 = esc.eventos_escenario(self.d, "S20A")
        for nombre, evs in (("S00", []), ("S20A", e20)):
            for plan, reac in COMBINACIONES:
                if not evs and reac != "CONV" and plan in ("FIFO", "MILP"):
                    continue     # sin averías la reacción no interviene: FIFO+MILP ≡ FIFO+CONV y MILP+MILP ≡ MILP+CONV
                res, f = self.correr(plan, reac, evs, asignar=True, politica=pol20)
                f.update(escenario=nombre, naturaleza="SIMULADO")
                filas.append(f)
                etiqueta = f"{nombre}_{plan}_{reac}"
                self.guardar_corrida(res, etiqueta)
                for r in K.por_familia(self.inst, res.programa):
                    fam.append(dict(escenario=nombre, combinacion=res.combinacion, **r))
                if nombre == "S00":
                    self._s00[(plan, reac)] = f
                self.log(f"E1 {nombre} {res.combinacion}: atrasados={f['atrasados']:.0f} OTD={f['otd_pct']:.1f}% "
                         f"Σw·T={f['tardanza_ponderada']:.1f} pen={f['penalidad_estimada']:.0f} "
                         f"MILP óptimos={f.get('eventos_optimos', 0):.0f}/{f.get('eventos_milp', 0):.0f} t={f['tiempo_total_s']:.0f}s")
        escribir_csv(self.ruta("comp", "E1_anual.csv"), filas)
        escribir_csv(self.ruta("comp", "E1_por_familia.csv"), fam)
        return filas

    # ------------------------------------------------------------------------------------------ E2
    def _s00_ref(self, plan, reac):
        if (plan, reac) not in self._s00:
            res, f = self.correr(plan, reac, [])
            self._s00[(plan, reac)] = f
        return self._s00[(plan, reac)]

    def e2_fallas(self, escenarios=None, reacciones=("CONV", "EDD", "MILP")):
        filas = []
        for e in self.d.escenarios:
            sid = e["id"]
            if sid in ("S00", "S20A") or (escenarios and sid not in escenarios):
                continue
            for reac in reacciones:
                plan = "EDD" if reac == "EDD" else "FIFO"
                res, f = self.correr(plan, reac, e["eventos"], politica=e["politica"])
                ref = self._s00_ref(plan, "CONV" if plan == "FIFO" else "EDD")
                fal = [r for r in res.registro if r["tipo"] == "FALLA"]
                f.update(escenario=sid, caso=e["caso"], naturaleza=e["naturaleza"],
                         recursos=";".join(sorted({self.d.fallas[x]["maquina"] for x in e["eventos"]})),
                         interrumpidas=sum(r["interrumpidas"] for r in fal),
                         ops_reprogramadas=sum(r.get("ops_libres", 0) for r in fal),
                         estado_eventos=";".join(str(r["estado"]) for r in fal),
                         tiempo_reaccion_s=sum(r["tiempo_s"] for r in fal),
                         delta_atrasados=f["atrasados"] - ref["atrasados"],
                         delta_tardanza_ponderada=f["tardanza_ponderada"] - ref["tardanza_ponderada"],
                         delta_tardanza_h=f["tardanza_total_h"] - ref["tardanza_total_h"],
                         delta_penalidad=f["penalidad_estimada"] - ref["penalidad_estimada"])
                filas.append(f)
            ult = filas[-len(reacciones):]
            self.log("E2 " + sid + " " + " | ".join(f"{x['combinacion']} Δw·T={x['delta_tardanza_ponderada']:+.1f} "
                                                     f"Δatr={x['delta_atrasados']:+.0f}" for x in ult))
        escribir_csv(self.ruta("comp", "E2_escenarios_falla.csv"), filas)
        return filas

    # ------------------------------------------------------------------------------------------ E2b
    def e2b_casos(self, escenarios=("S06A", "S13A", "S19A")):
        """Reacción a la primera avería de cada escenario sobre el plan FIFO vigente: CONV, EDD y MILP resuelven
        EL MISMO subproblema (mismas operaciones libres, ventanas, tiempos restantes y disponibilidad)."""
        filas = []
        inst = self.inst
        base, _ = reglas.fifo_plan(inst, list(range(len(inst.jobs))))
        for sid in escenarios:
            evs, pol = esc.eventos_escenario(self.d, sid)
            ws = [(m, a, b) for (_, m, a, b) in sim.ventanas_de(self.d, evs)]
            wu = estado.ventanas_unidades(inst, ws)
            tb = min(a for _, a, _ in wu)
            jobs = [j for j in range(len(inst.jobs)) if inst.jobs[j]["r"] <= tb + EPS
                    and base[inst.job_ops[j][-1]][2] > tb + EPS]
            sub = estado.particionar(self.d, inst, base, tb, jobs, wu, pol, congelar_h=self.H)
            sols = {}
            for met in ("CONV", "EDD", "MILP"):
                t = time.perf_counter()
                info = dict(estado="REGLA")
                if met == "CONV":
                    sol = reglas.convencional(sub)
                elif met == "EDD":
                    sol = reglas.edd(sub)
                else:
                    r = opt.optimizar(sub, beta=self.beta, regla_objetivo=self.regla, tl=self.tl, gap=self.gap)
                    sol = r["sol"]
                    info = dict(estado=r["estado_global"], respaldo=r["respaldo"],
                                **{f"modelo_{k}": v for k, v in r["tamano"].items()},
                                brecha_max=max((p["brecha"] or 0.0) for p in r["pasos"]),
                                **{f"obj_{k}": v for k, v in r["objetivos"].items()})
                viol = verificar_subproblema(sub, sol)
                k = K.kpis_subproblema(sub, sol, beta=self.beta, horas_dia=self.d.calendario.h_dia)
                filas.append(dict(escenario=sid, metodo=met, t_decision_h=tb, fecha=self.d.calendario.a_fecha(tb),
                                  ops_libres=len(sub.free), interrumpidas=len(sub.interrupted),
                                  violaciones=len(viol), tiempo_s=time.perf_counter() - t, naturaleza="SIMULADO",
                                  **info, **k))
                sols[met] = sol
            for met, sol in sols.items():
                full = verificacion_programa_completo(sub, sol)
                escribir_csv(self.ruta("milp", f"caso_{sid}_{met}.csv"),
                             [dict(pedido=inst.jobs[inst.ops[o]["job"]]["id"], paso=inst.ops[o]["paso"], unidad=m,
                                   inicio_h=S, fin_h=C, libre=int(o in sub.free), vencimiento_h=inst.jobs[inst.ops[o]["job"]]["d"])
                              for o, (m, S, C) in sorted(full.items(), key=lambda kv: kv[1][1])])
            escribir_csv(self.ruta("milp", f"caso_{sid}_ventanas.csv"),
                         [dict(unidad=u, inicio_h=a, fin_h=b) for (u, a, b) in sub.all_windows])
            escribir_csv(self.ruta("milp", f"caso_{sid}_cambios.csv"),
                         [dict(metodo=met, **c) for met, sol in sols.items() for c in cambios(sub, sol)])
            ult = filas[-3:]
            self.log("E2b " + sid + " " + " | ".join(f"{x['metodo']} atr={x['atrasados']:.0f}/{x['pedidos']:.0f} "
                                                      f"w·T={x['tardanza_ponderada']:.1f} D={x['desviacion_total_h']:.1f}"
                                                      for x in ult))
        escribir_csv(self.ruta("comp", "E2b_reaccion_evento.csv"), filas)
        return filas

    # ------------------------------------------------------------------------------------------ E3
    def e3_operativos(self, combinaciones=(("FIFO", "CONV"), ("EDD", "EDD"), ("MILP", "MILP")), escenarios=None):
        filas = []
        for e in self.d.escenarios_operativos:
            if escenarios and e["id"] not in escenarios:
                continue
            peds, avisos = esc.pedidos_transformados(self.d, e["factor_cantidad"], e["factor_plazo"])
            inst = instancia.construir(self.d, pedidos=peds)
            dot = pers.dotacion(self.d, e["ausentes"])
            for plan, reac in combinaciones:
                res, f = self.correr(plan, reac, e["eventos"], inst=inst, dot=dot, asignar=True, politica=e["politica"])
                f.update(escenario=e["id"], descripcion=e["descripcion"], factor_cantidad=e["factor_cantidad"],
                         factor_plazo=e["factor_plazo"], ausentes=len(e["ausentes"]),
                         trabajadores_disponibles=len(dot.disponibles()), certificado_personal=res.certificado["ok"],
                         avisos=";".join(avisos), naturaleza=e["naturaleza"],
                         cota_inferior_tardanza_h=sum(K.cota_inferior_tardanza(inst).values()))
                filas.append(f)
                if e["id"] in ("E-CARGA-MUY-ALTA", "E-PERSONAL-15") and plan == "MILP":
                    self.guardar_corrida(res, f"{e['id']}_{plan}_{reac}", inst=inst)
            ult = filas[-len(combinaciones):]
            self.log("E3 " + e["id"] + " " + " | ".join(f"{x['combinacion']} atr={x['atrasados']:.0f} "
                                                         f"w·T={x['tardanza_ponderada']:.1f}" for x in ult))
        escribir_csv(self.ruta("esc", "E3_escenarios_operativos.csv"), filas)
        return filas

    # ------------------------------------------------------------------------------------------ E4
    def e4_sensibilidad(self, factores=None):
        d = self.d
        filas = []
        e20, pol20 = esc.eventos_escenario(d, "S20A")
        sens = {k: v for k, v in d.sensibilidad.items() if not factores or k in factores}

        def add(factor, nivel, escenario, res_f, extra=None):
            res, f = res_f
            f.update(factor=factor, nivel=nivel, escenario=escenario, naturaleza="SIMULADO", **(extra or {}))
            filas.append(f)
            self.log(f"E4 {factor}={nivel} {escenario} {f['combinacion']}: atr={f['atrasados']:.0f} "
                     f"w·T={f['tardanza_ponderada']:.1f} pen={f['penalidad_estimada']:.0f} D={f.get('desviacion_total_h', 0):.1f}")

        if "duracion_falla_mult" in sens:
            for nv in sens["duracion_falla_mult"]["niveles"]:
                for plan, reac in (("FIFO", "CONV"), ("MILP", "MILP")):
                    add("duracion_falla_mult", nv, "S20A", self.correr(plan, reac, e20, politica=pol20, mult_falla=float(nv)))
        if "regla_objetivo" in sens:
            for nv in sens["regla_objetivo"]["niveles"]:
                for nombre, evs in (("S00", []), ("S20A", e20)):
                    add("regla_objetivo", nv, nombre, self.correr("MILP", "MILP", evs, politica=pol20, regla=nv))
        if "beta_reasignacion" in sens:
            for nv in sens["beta_reasignacion"]["niveles"]:
                add("beta_reasignacion", nv, "S20A", self.correr("MILP", "MILP", e20, politica=pol20, beta=float(nv)))
        if "horizonte_congelado_h" in sens:
            for nv in sens["horizonte_congelado_h"]["niveles"]:
                add("horizonte_congelado_h", nv, "S20A",
                    self.correr("MILP", "MILP", e20, politica=pol20, congelar_h=float(nv)))
        if "factor_alternativa" in sens:
            for nv in sens["factor_alternativa"]["niveles"]:
                d2 = esc.datos_con_factor_alternativa(d, float(nv))
                inst2 = instancia.construir(d2)
                for sid in ("S15A", "S16A"):
                    evs, pol = esc.eventos_escenario(d, sid)
                    for plan, reac in (("FIFO", "CONV"), ("FIFO", "MILP")):
                        add("factor_alternativa", nv, sid, self.correr(plan, reac, evs, inst=inst2, politica=pol, datos=d2))
        if "aplicar_feriados" in sens:
            for nv in sens["aplicar_feriados"]["niveles"]:
                d3, _ = cargar_base(self.base, ajustes={"aplicar_feriados": float(nv)})
                inst3 = instancia.construir(d3)
                for plan, reac in (("FIFO", "CONV"), ("MILP", "CONV")):
                    add("aplicar_feriados", nv, "S00",
                        self.correr(plan, reac, [], inst=inst3, datos=d3, dot=pers.dotacion(d3)),
                        dict(horas_productivas_horizonte=d3.calendario.total))
        if "lote_no_cruza" in sens:
            for nv in sens["lote_no_cruza"]["niveles"]:
                inst4 = instancia.construir(d, regla_continuidad=nv)
                for plan, reac in (("FIFO", "CONV"), ("MILP", "CONV")):
                    add("lote_no_cruza", nv, "S00", self.correr(plan, reac, [], inst=inst4), dict(L_segmento_h=inst4.L_segmento))
        escribir_csv(self.ruta("esc", "E4_sensibilidad.csv"), filas)
        return filas

    # ------------------------------------------------------------------------------------------ E5
    def e5_rendimiento(self, escenarios=("S06A", "S13A", "S19A", "S08A"), v14=None):
        """Tamaño y tiempo del MILP en el subproblema de la primera avería de cada escenario sobre el plan FIFO.

        v2.0 se mide con la configuración por defecto y con la configuración equivalente a v1.4 (sin R12,
        penalidad fija primero); v1.4 se ejecuta en un proceso separado con su propio código y su Excel v1.2.
        """
        filas = []
        for regla_c, regla_o, etiqueta in (("NINGUNA", "PENALIDAD_FIJA", "v2.0 config. v1.4"),
                                           (None, self.regla, "v2.0 por defecto")):
            inst = instancia.construir(self.d, regla_continuidad=regla_c)
            base, _ = reglas.fifo_plan(inst, list(range(len(inst.jobs))))
            for sid in escenarios:
                evs, pol = esc.eventos_escenario(self.d, sid)
                ws = [(m, a, b) for (_, m, a, b) in sim.ventanas_de(self.d, evs)]
                wu = estado.ventanas_unidades(inst, ws)
                tb = min(a for _, a, _ in wu)
                jobs = [j for j in range(len(inst.jobs)) if inst.jobs[j]["r"] <= tb + EPS
                        and base[inst.job_ops[j][-1]][2] > tb + EPS]
                sub = estado.particionar(self.d, inst, base, tb, jobs, wu, pol)
                for presolve in (True, False):
                    t = time.perf_counter()
                    r = opt.optimizar(sub, beta=self.beta, regla_objetivo=regla_o, tl=self.tl, gap=self.gap,
                                      presolve=presolve)
                    filas.append(dict(version=etiqueta, escenario=sid, presolve=int(presolve), estado=r["estado_global"],
                                      tiempo_total_s=time.perf_counter() - t,
                                      tiempo_solver_s=sum(p["tiempo_s"] for p in r["pasos"]),
                                      fases=len(r["pasos"]), **r["tamano"],
                                      **{f"obj_{k}": v for k, v in (r.get("objetivos") or {}).items()},
                                      nodos=sum((p.get("nodos") or 0) for p in r["pasos"])))
                    self.log(f"E5 {etiqueta} {sid} presolve={presolve}: {r['estado_global']} "
                             f"{filas[-1]['tiempo_solver_s']:.2f}s vars={r['tamano']['variables']}")
        v14 = v14 or _ruta_v14()
        if v14 is not None:
            for sid in escenarios:
                filas.extend(_rendimiento_v14(v14, sid, self.tl, self.log))
        escribir_csv(self.ruta("milp", "E5_rendimiento.csv"), filas)
        return filas

    def todo(self):
        t = time.perf_counter()
        out = dict(e0=self.e0_validacion())
        out["e1"] = self.e1_anual()
        out["e2"] = self.e2_fallas()
        out["e2b"] = self.e2b_casos()
        out["e3"] = self.e3_operativos()
        out["e4"] = self.e4_sensibilidad()
        out["e5"] = self.e5_rendimiento()
        self.log(f"Experimentos completos en {time.perf_counter() - t:.0f} s")
        return out


# ---------------------------------------------------------------------------------------------- v1.4
def _ruta_v14():
    raiz = Path(__file__).resolve().parents[2]
    for c in (raiz / "06_AUDITORIA_Y_VALIDACION" / "Evidencias_Validacion" / "version_inicial_v1_4_0",
              raiz / "historial" / "v1_4_0_original"):
        if (c / "sagapi" / "modelo.py").exists():
            return c
    return None


_SCRIPT_V14 = r'''
import json, sys, time
sys.path.insert(0, sys.argv[1])
from sagapi import datos as D, instancia, estado, reglas, optimizacion as opt
d = D.leer(sys.argv[2]); I = instancia.construir(d)
base = reglas.fifo_plan(I, range(len(I.jobs)))[0]
esc = {e["id"]: e for e in d.escenarios}[sys.argv[3]]
evs = [x for x in esc["eventos"].split("+") if x]
cal = d.calendario
ws = [(d.fallas[e]["maquina"], cal.a_horas(d.fallas[e]["inicio"]), cal.a_horas(d.fallas[e]["fin"])) for e in evs]
tb = min(a for _, a, _ in ws)
jobs = [j for j in range(len(I.jobs)) if I.jobs[j]["r"] <= tb + 1e-6 and base[I.job_ops[j][-1]][2] > tb + 1e-6]
sub = estado.particionar(d, I, base, tb, jobs, ws, esc["politica"])
t = time.perf_counter()
r = opt.lexicografico(sub, beta=8.0, regla_pen="FIJA", tl=(float(sys.argv[4]),) * 3)
dt = time.perf_counter() - t
print(json.dumps(dict(tamano=r["tamano"], estado=r["estado_global"], tiempo=dt,
                      tiempo_solver=sum(p.get("tiempo", 0) or 0 for p in r["pasos"]), f1=r.get("f1_final"),
                      f1b=r.get("f1b_final"), libres=len(sub.free), pedidos=len(jobs)), default=str))
'''


def _rendimiento_v14(v14, sid, tl, log):
    excel = next(iter(sorted(Path(v14).glob("Base_Datos_SAGAPI*.xlsx"))), None)
    if excel is None:
        return []
    try:
        p = subprocess.run([sys.executable, "-I", "-c", _SCRIPT_V14, str(v14), str(excel), sid, str(tl)],
                           capture_output=True, text=True, timeout=max(600, 10 * tl), cwd=str(v14))
        out = json.loads(p.stdout.strip().splitlines()[-1])
    except (subprocess.SubprocessError, ValueError, IndexError) as ex:
        log(f"E5 v1.4 {sid}: no ejecutado ({type(ex).__name__})")
        return [dict(version="v1.4.0 (original)", escenario=sid, estado="NO_EJECUTADO", error=str(ex)[:200])]
    t = out["tamano"]
    fila = dict(version="v1.4.0 (original)", escenario=sid, presolve=1, estado=out["estado"], tiempo_total_s=out["tiempo"],
                tiempo_solver_s=out["tiempo_solver"], variables=t.get("variables"), restricciones=t.get("restricciones"),
                binarias=t.get("binarias"), ops_libres=out["libres"], pedidos=out["pedidos"],
                obj_P1_penalidad_estimada=out["f1"], obj_P2_tardanza_ponderada=out["f1b"])
    log(f"E5 v1.4 {sid}: {out['estado']} {out['tiempo']:.2f}s vars={fila['variables']}")
    return [fila]
