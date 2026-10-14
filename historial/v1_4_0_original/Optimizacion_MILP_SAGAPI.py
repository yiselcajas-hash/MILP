#!/usr/bin/env python3
"""Optimizacion_MILP_SAGAPI.py — programa principal.

Programación y reprogramación reactiva multiobjetivo (MILP) de la producción de SAGAPI ante la
disponibilidad reducida de máquinas. Lee la base SAGAPI con habilidades simuladas de 25 perfiles, construye conjuntos y
parámetros, resuelve con HiGHS, verifica cada solución y exporta indicadores, tablas, gráficos y las
hojas de resultados del Excel.

Uso (desde esta carpeta):
  python Optimizacion_MILP_SAGAPI.py validar   --excel Base_Datos_SAGAPI_Final.xlsx
  python Optimizacion_MILP_SAGAPI.py caso      --excel ... --escenario S06A [--base FIFO|MILP]
  python Optimizacion_MILP_SAGAPI.py anual     --excel ...
  python Optimizacion_MILP_SAGAPI.py escenarios --excel ...
  python Optimizacion_MILP_SAGAPI.py montecarlo --excel ...
  python Optimizacion_MILP_SAGAPI.py pareto    --excel ...
  python Optimizacion_MILP_SAGAPI.py sensibilidad --excel ...
  python Optimizacion_MILP_SAGAPI.py reportes  --excel ... [--escribir-excel]
  python Optimizacion_MILP_SAGAPI.py todo      --excel ... [--escribir-excel]
  python Optimizacion_MILP_SAGAPI.py auditar-personal --escenario S20A --salida auditoria_v121
  python Optimizacion_MILP_SAGAPI.py integrar-personal --escenario S13A --pedidos 2 --salida piloto_integrado
  python Optimizacion_MILP_SAGAPI.py rodante-personal --escenario S08A --pedidos 3 --ventanas 5
  python herramientas/generar_entrega_final.py --tl 60  # verificación completa + diagnóstico global
  python Optimizacion_MILP_SAGAPI.py exportar-mps --excel ... --escenario S06A
Opciones: --salida resultados  --tl 60  (límite en segundos por paso lexicográfico)
"""
import argparse
import json
import os
import sys
import time

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)

from sagapi import __version__, datos as D, instancia, reglas, estado, optimizacion as opt  # noqa: E402
from sagapi.experimentos import Experimentos, evento_unico, _ventanas                      # noqa: E402
from sagapi.solver import version_highs, exportar_mps                                       # noqa: E402


def log(msg):
    print(time.strftime("%H:%M:%S"), msg, flush=True)


def cmd_validar(a):
    d = D.leer(a.excel)
    I = instancia.construir(d)
    E = Experimentos(a.excel, a.salida, log=log)
    rep = E.e0_fifo()
    cal = d.calendario
    dif = [e for e, f in d.fallas.items()
           if f["horas_turno_excel"] is not None and abs((cal.a_horas(f["fin"]) - cal.a_horas(f["inicio"])) - f["horas_turno_excel"]) > 1e-3]
    from sagapi.personal import resumen_dotacion
    dotacion = resumen_dotacion(d.habilidades, I.machines)
    res = dict(personal=dotacion, version=__version__, highs=version_highs(), archivo=a.excel, pedidos=len(I.jobs), operaciones=len(I.ops),
               maquinas=len(I.machines), familias=sorted(I.fam_jobs), fallas=len(d.fallas), escenarios=len(d.escenarios),
               horas_productivas_horizonte=cal.total, fifo_reproduce_16=rep["reproduce"], max_dif_fifo_h=rep["max_dif_h"],
               fallas_con_horas_distintas=dif, avisos=d.avisos)
    print(json.dumps(res, indent=1, ensure_ascii=False, default=str))
    json.dump(res, open(os.path.join(a.salida, "validacion_datos.json"), "w"), indent=1, ensure_ascii=False, default=str)


def _base(E, nombre):
    if nombre == "MILP":
        return E.programa_milp_sin_fallas()
    return reglas.fifo_plan(E.I, range(len(E.I.jobs)))[0]


def cmd_caso(a):
    E = Experimentos(a.excel, a.salida, tl=(a.tl,) * 3, log=log)
    esc = {e["id"]: e for e in E.d.escenarios}[a.escenario]
    evs = [x for x in esc["eventos"].split("+") if x]
    base = _base(E, a.base)
    filas, sub, sols = evento_unico(E.d, E.I, base, evs, esc["politica"], beta=E.beta, tl=E.tl)
    for f in filas:
        log(f"{f['metodo']:10s} atrasados={f['atrasados']:.0f}/{f['pedidos']:.0f} penalidad=S/{f['penalidad']:,.0f} "
            f"tard.pond={f['tard_pond']:.1f} D={f['D']:.1f} R={f['R']:.0f} estado={f['estado']} viol={f['violaciones']}")
    from sagapi import reportes
    reportes.gantt_caso(E, sub, base, sols, a.escenario, os.path.join(a.salida, f"gantt_{a.escenario}.png"))
    reportes.tabla_programa(E, sub, sols, os.path.join(a.salida, f"programa_{a.escenario}.csv"))
    from sagapi.explicabilidad import exportar_cambios
    from sagapi.verificacion import programa_completo, control_personal
    exportar_cambios(sub, sols, os.path.join(a.salida, f"cambios_{a.escenario}.csv"))
    conflictos = []
    for metodo, sol in sols.items():
        if sol is None:
            continue
        pc = control_personal(E.d, programa_completo(sub, sol))
        if pc is not None:
            n, horas, _ = pc
            log(f"PERSONAL {metodo}: {n} intervalos en conflicto; {horas:.3f} horas (solo pedidos del subproblema)")
            if n:
                conflictos.append(metodo)
    if a.personal_estricto and conflictos:
        raise RuntimeError("La solución NO es viable con el personal declarado: " + ", ".join(conflictos))


def cmd_auditar_personal(a):
    """Recalcula dos programas anuales S00/S20A y exporta dotación operativa simulada."""
    import pandas as pd
    from sagapi import simulacion
    from sagapi.auditoria_personal import asignar_personal
    E = Experimentos(a.excel, a.salida, tl=(a.tl,) * 3, log=log)
    if a.escenario not in ("S00", "S20A"):
        raise ValueError("auditar-personal admite S00 o S20A; elige uno de ellos")
    eventos = [] if a.escenario == "S00" else [f"F{k:02d}" for k in range(1, 13)]
    resumen, segmentos = [], []
    for plan, reaccion in (("FIFO", "CONV"), ("MILP", "MILP")):
        etiqueta = f"{plan}+{reaccion}"
        log(f"Auditoría: simulando {a.escenario} {etiqueta}")
        programa, registro = simulacion.simular(E.d, E.I, plan, reaccion, eventos, beta=E.beta, tl=E.tl)
        filas, aud = asignar_personal(E.I, programa, escenario=a.escenario, combinacion=etiqueta)
        resumen.append(aud)
        segmentos.extend(filas)
        log(f"Personal {etiqueta}: {aud['trabajadores_utilizados']} personas simuladas usadas; "
            f"{aud['conflictos_h']:.3f} h en conflicto; {aud['relevos_intraproceso']} relevos")
    ruta_det = os.path.join(a.salida, f"auditoria_personal_{a.escenario}_detalle.csv")
    ruta_res = os.path.join(a.salida, f"auditoria_personal_{a.escenario}_resumen.csv")
    pd.DataFrame(segmentos).to_csv(ruta_det, index=False, encoding="utf-8-sig")
    pd.DataFrame(resumen).to_csv(ruta_res, index=False, encoding="utf-8-sig")
    log(f"Archivos generados: {ruta_res} y {ruta_det}")




def cmd_integrar_personal(a):
    """Prueba experimental: trabajador-por-operación DECIDIDO dentro del MILP.

    Se selecciona un subconjunto de pedidos activos, pero se auto-incluyen otros
    pedidos que estén sufriendo la misma falla en t0. Las operaciones externas
    sobre máquinas sanas que ya estaban en curso consumen máquina y personal.
    Las operaciones FUTURAS de pedidos excluidos quedan fuera del MILP; NO
    representa una validación anual ni competencias verificadas.
    """
    import pandas as pd
    from sagapi.personal_integrado import ModeloPersonalOperaciones
    from sagapi.solver import solve
    from sagapi.verificacion import verificar
    E = Experimentos(a.excel, a.salida, tl=(a.tl,) * 3, log=log)
    esc = {e["id"]: e for e in E.d.escenarios}[a.escenario]
    eventos = [x for x in esc["eventos"].split("+") if x]
    ventanas = _ventanas(E.d, eventos)
    if not ventanas:
        raise ValueError('El escenario elegido no contiene fallas')
    t0 = min(w[1] for w in ventanas)
    base = _base(E, a.base)
    candidatas = [j for j in range(len(E.I.jobs))
                  if E.I.jobs[j]['r'] <= t0 + 1e-6
                  and base[E.I.job_ops[j][-1]][2] > t0 + 1e-6]
    if a.pedidos < 1 or a.max_operaciones < 1:
        raise ValueError('--pedidos y --max-operaciones deben ser positivos')
    sel = candidatas[:a.pedidos]
    if not sel:
        raise ValueError('No existen pedidos activos para este escenario')
    from sagapi.cobertura_externa import preparar_con_cobertura
    sub, cobertura = preparar_con_cobertura(E.d, E.I, base, t0, sel, ventanas, esc['politica'])
    # Modo experimental: las operaciones FUTURAS ajenas quedan congeladas
    # dentro de un horizonte productivo acotado, con máquina y persona simulada.
    from sagapi.cobertura_externa import preparar_reservas_futuras
    reservas_info = preparar_reservas_futuras(sub, base, a.horizonte_externos)
    log(f'RESERVAS EXTERNAS: {reservas_info["operaciones_externas_congeladas"]} operaciones '
        f'protegidas en {a.horizonte_externos:g} h productivas; '
        f'{reservas_info["operaciones_externas_futuras_sin_proteger"]} futuras quedan fuera.')
    if reservas_info['cruces_reservas_con_averia']:
        log('ADVERTENCIA: el plan externo FIFO congelado contiene '
            f'{reservas_info["cruces_reservas_con_averia"]} cruces con averías.')
    log(f'PILOTO CON COBERTURA {a.escenario}: {len(sub.jobs)} pedidos (iniciales={len(sel)}), '
        f'{len(sub.free)} operaciones libres, {len(sub.fixed)} operaciones fijadas, '
        f'{cobertura["externas_activas_fijadas"]} externas en curso, '
        f'{cobertura["externas_futuras_no_integradas"]} externas FUTURAS no integradas')
    if cobertura['pedidos_autoincluidos_por_falla']:
        log('Pedidos auto-incluidos por avería: '+', '.join(cobertura['pedidos_autoincluidos_por_falla']))
    mdl = ModeloPersonalOperaciones(sub, max_operaciones=a.max_operaciones,
                                   beta=E.beta, estabilidad=True)
    log(f'Modelo: {mdl.tamano()}')
    fases = []

    def fase(nombre, terms):
        mdl.M.set_objective(terms)
        r = solve(mdl.M, time_limit=a.tl)
        fases.append(dict(fase=nombre, estado=r['status'], certificado=r['certificado'],
                          obj=r['obj'], tiempo_s=r['time'], brecha=r['gap']))
        log(f'{nombre}: {r["status"]}, t={r["time"]:.2f}s, objetivo={r["obj"]}')
        return r

    r1 = fase('P1_penalidad', mdl.f1_terms())
    if r1['x'] is None:
        raise RuntimeError('No se obtuvo solución factible en P1; no se generan cronogramas')
    elegido = r1
    cap1 = r1['obj'] + max(1e-4, 1e-7 * abs(r1['obj']))
    mdl.M.row(mdl.f1_terms(), -float('inf'), cap1)
    r2 = fase('P2_tardanza', mdl.f1b_terms())
    if r2['x'] is not None:
        elegido = r2
    if sub.S0 and r2['x'] is not None:
        cap2 = r2['obj'] * (1 + 1e-6) + 1e-4
        mdl.M.row(mdl.f1b_terms(), -float('inf'), cap2)
        r3 = fase('P3_estabilidad', mdl.f2_terms())
        if r3['x'] is not None:
            elegido = r3
    xv = elegido['x']
    errores = mdl.verificar_personal(xv)
    asignadas = mdl.asignaciones(xv)
    sol = mdl.decode(xv)
    # Diagnóstico EXTRA (no restricción): las operaciones futuras de pedidos
    # excluidos mantienen el cronograma FIFO sólo como referencia hipotética.
    # Si se cruzan, el piloto NO es una solución global de la planta.
    from collections import defaultdict
    externas_pendientes_maquina = defaultdict(list)
    for oe, (me, se, ce) in base.items():
        if (E.I.ops[oe]['job'] not in sub.jobs and se >= t0-1e-6
                and oe not in sub.trabajadores_externos):
            externas_pendientes_maquina[me].append((oe,se,ce))
    cruces_base_futuro = []
    for o, (m, start) in sol.items():
        finish = start+sub.pR[(o,m)]
        for oe,se,ce in externas_pendientes_maquina[m]:
            if start < ce-1e-6 and se < finish-1e-6:
                cruces_base_futuro.append((o,oe))
    if cruces_base_futuro:
        log(f'ADVERTENCIA: {len(cruces_base_futuro)} cruces fuera del horizonte protegido '
            '(comparación hipotética con FIFO externo, NO validación global).')
    detalle = []
    for o in sorted(asignadas):
        w = asignadas[o]
        if o in sol:
            m, inicio = sol[o]
            fin = inicio + sub.pR[(o, m)]
            estado_op = 'LIBRE_MILP'
        else:
            if o in sub.externas_activas:
                m, inicio, fin = sub.externas_activas[o]
                estado_op = 'EXTERNA_ACTIVA_EN_T0'
            else:
                m, inicio, fin = sub.fixed[o]
                estado_op = 'FIJADA_EN_CURSO'
        op = E.I.ops[o]
        jb = E.I.jobs[op['job']]
        detalle.append(dict(escenario=a.escenario, estado_operacion=estado_op,
            pedido=jb['id'], familia=jb['familia'], operacion_id=o,
            paso=op['paso'], maquina=m, trabajador_simulado=w,
            inicio_h=round(inicio, 6), fin_h=round(fin, 6),
            duracion_h=round(fin-inicio, 6), habilidades='SIMULADAS_NO_VERIFICADAS',
            integracion='BINARIA_MILP_OPERACION',
            alcance='SOLO_PEDIDOS_SELECCIONADOS_NO_AUDITORIA_ANUAL'))
    ruta = os.path.join(a.salida, f'personal_milp_{a.escenario}_{len(sub.jobs)}pedidos.csv')
    pd.DataFrame(detalle).to_csv(ruta, index=False, encoding='utf-8-sig')
    from sagapi.jornada_piloto import comprobar_jornadas
    segmentos, auditoria_turno = comprobar_jornadas(E.d.calendario, detalle)
    rsegmentos = os.path.join(a.salida, f'personal_milp_{a.escenario}_{len(sub.jobs)}pedidos_segmentos.csv')
    pd.DataFrame(segmentos).to_csv(rsegmentos, index=False, encoding='utf-8-sig')
    rexternas = os.path.join(a.salida, f'personal_milp_{a.escenario}_{len(sub.jobs)}pedidos_externos_reservados.csv')
    rows_externas = [dict(operacion_id=o, pedido=E.I.jobs[E.I.ops[o]['job']]['id'],
                          maquina=m, inicio_h=s, fin_h=c, trabajador_simulado=w,
                          fuente='FIFO_EXTERNO_CONGELADO_HABILIDADES_SIMULADAS')
                    for o,(m,s,c,w) in sorted(sub.trabajadores_externos.items())]
    pd.DataFrame(rows_externas, columns=['operacion_id','pedido','maquina','inicio_h','fin_h',
                                        'trabajador_simulado','fuente']).to_csv(
                                            rexternas,index=False,encoding='utf-8-sig')
    resumen = dict(version=__version__, escenario=a.escenario, pedidos=[E.I.jobs[j]['id'] for j in sub.jobs],
        operarios_simulados=len(E.d.habilidades), turno_h=8,
        operaciones_libres=len(sub.free), operaciones_fijas_activas=len(mdl.fijas_activas),
        operaciones_con_personal=len(asignadas), workers_usados=len(set(asignadas.values())),
        cobertura_externa=cobertura, reservas_externas=reservas_info,
        auditoria_turno=auditoria_turno,
        cruces_maquina_con_baseline_externo_futuro=len(cruces_base_futuro),
        muestra_cruces_externos_futuros=[list(z) for z in cruces_base_futuro[:15]],
        advertencias_alcance=['El programa FIFO externo FUTURO se congela como reserva en un '
                             'horizonte rodante, pero NO se optimiza; el resto de operaciones '
                             'externas permanece fuera; NO es una programación global válida.'],
        externas_activas_con_trabajador=len([o for o in sub.externas_activas if o in asignadas]),
        estado_ultimo_paso=elegido['status'], certificado_ultimo_paso=elegido['certificado'],
        resultado_lexicografico_completo=len(fases)==(3 if sub.S0 else 2),
        certificado_lexicografico_completo=all(f['certificado'] for f in fases),
        f1_penalidad_modelada=sum(c*xv[k] for k,c in mdl.f1_terms()),
        f1b_tardanza_ponderada=sum(c*xv[k] for k,c in mdl.f1b_terms()),
        f2_inestabilidad=sum(c*xv[k] for k,c in mdl.f2_terms()) + mdl.f2_const(),
        errores=errores, fases=fases, tamano=mdl.tamano(),
        nota='PILOTO: habilidades, pedidos y penalidades simulados; no representa plantilla verificada ni horizonte anual.')
    rres = os.path.join(a.salida, f'personal_milp_{a.escenario}_{len(sub.jobs)}pedidos_resumen.json')
    with open(rres, 'w', encoding='utf-8') as fh:
        json.dump(resumen, fh, ensure_ascii=False, indent=2, default=str)
    log(f'Asignaciones={len(asignadas)}; trabajadores distintos={resumen["workers_usados"]}; '
        f'errores={len(errores)}; certificado_ultimo_paso={resumen["certificado_ultimo_paso"]}')
    log(f'Resultados: {ruta}, {rsegmentos}, {rexternas} y {rres}')
    if errores:
        raise RuntimeError(f'Verificación integrada falló: {errores[:5]}')

def cmd_rodante_personal(a):
    """Piloto de varias ventanas de 8 h: no es validación global anual."""
    import pandas as pd
    from sagapi.rodante_personal import ejecutar
    E = Experimentos(a.excel, a.salida, tl=(a.tl,) * 3, log=log)
    esc = {e['id']:e for e in E.d.escenarios}[a.escenario]
    fallas = [x for x in esc['eventos'].split('+') if x]
    ventanas = _ventanas(E.d, fallas)
    if not ventanas:
        raise ValueError('Este piloto rodante requiere un escenario con fallas')
    t0 = min(w[1] for w in ventanas)
    base = _base(E, a.base)
    candidatos = [j for j in range(len(E.I.jobs))
                  if E.I.jobs[j]['r'] <= t0 + 1e-6
                  and base[E.I.job_ops[j][-1]][2] > t0 + 1e-6]
    seleccion = candidatos[:a.pedidos]
    res, historial, detalle, compromisos, plan, reservas_por_ventana, arrastres = ejecutar(
        E.d, E.I, base, ventanas, esc['politica'], seleccion, t0,
        n_ventanas=a.ventanas, paso_h=a.paso_rodante,
        horizonte_externos=a.horizonte_externos,
        max_operaciones=a.max_operaciones, limite_s=a.tl, beta=E.beta, log=log)
    pref = os.path.join(a.salida, f'rodante_{a.escenario}')
    with open(pref+'_resumen.json','w',encoding='utf-8') as fh:
        json.dump(dict(res, ventanas=historial),fh,ensure_ascii=False,indent=2,default=str)
    pd.DataFrame(detalle).to_csv(pref+'_decisiones.csv',index=False,encoding='utf-8-sig')
    filas = [dict(operacion_id=o, pedido=E.I.jobs[E.I.ops[o]['job']]['id'],
                  maquina=m, inicio_h=s, fin_h=c, trabajador_simulado=w)
             for o,(m,s,c,w) in sorted(compromisos.items())]
    pd.DataFrame(filas,columns=['operacion_id','pedido','maquina','inicio_h','fin_h',
                                'trabajador_simulado']).to_csv(pref+'_compromisos.csv',index=False,encoding='utf-8-sig')
    from sagapi.jornada_piloto import comprobar_jornadas
    segmentos, _ = comprobar_jornadas(E.d.calendario, filas)
    pd.DataFrame(segmentos).to_csv(pref+'_compromisos_jornadas.csv',index=False,encoding='utf-8-sig')
    pd.DataFrame(reservas_por_ventana, columns=['ventana','operacion_id','maquina',
        'inicio_h','fin_h','trabajador_simulado','tipo']).to_csv(
            pref+'_reservas_externas_por_ventana.csv',index=False,encoding='utf-8-sig')
    pd.DataFrame(arrastres, columns=['ventana','operacion_id','maquina','inicio_h',
        'fin_h','trabajador_simulado','horas_pendientes_al_abrir','tipo']).to_csv(
            pref+'_arrastres_entre_turnos.csv',index=False,encoding='utf-8-sig')
    log(f'RODANTE AUDITORÍA: {res["auditoria_reservas_y_compromisos"]["reservas_externas_unicas"]} '
        f'reservas externas únicas; {res["auditoria_reservas_y_compromisos"]["errores"]} errores; '
        f'{len(arrastres)} arrastres de operaciones iniciadas.')
    log(f'RODANTE {res["estado"]}: {res["ventanas_resueltas"]}/{a.ventanas} ventanas; ' 
        f'{len(compromisos)} operaciones comprometidas; cobertura anual NO validada')
    log(f'Resultados: {pref}_resumen.json, {pref}_decisiones.csv, '
        f'{pref}_compromisos.csv, {pref}_compromisos_jornadas.csv, '
        f'{pref}_reservas_externas_por_ventana.csv y {pref}_arrastres_entre_turnos.csv')
    if res['estado']=='DETENIDO_SIN_CERTIFICACION_GLOBAL':
        raise RuntimeError('El piloto rodante se detuvo; ver resumen JSON. No se declara solución completa.')


def cmd_exportar(a):
    E = Experimentos(a.excel, a.salida, log=log)
    esc = {e["id"]: e for e in E.d.escenarios}[a.escenario]
    evs = [x for x in esc["eventos"].split("+") if x]
    base = _base(E, a.base)
    ws = _ventanas(E.d, evs)
    tb = min(x[1] for x in ws)
    jobs = [j for j in range(len(E.I.jobs)) if E.I.jobs[j]["r"] <= tb + 1e-6 and base[E.I.job_ops[j][-1]][2] > tb + 1e-6]
    sub = estado.particionar(E.d, E.I, base, tb, jobs, ws, esc["politica"])
    from sagapi.modelo import ModeloMILP
    mdl = ModeloMILP(sub, beta=E.beta)
    mdl.M.set_objective(mdl.f1_terms())
    ruta = os.path.join(a.salida, f"modelo_P1_{a.escenario}.mps")
    exportar_mps(mdl.M, ruta)
    log(f"Modelo P1 exportado: {ruta} ({mdl.tamano()})")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("comando", choices=["validar", "caso", "anual", "escenarios", "montecarlo", "pareto", "sensibilidad", "reportes", "todo", "exportar-mps", "auditar-personal", "integrar-personal", "rodante-personal"])
    p.add_argument("--excel", default=os.path.join(AQUI, "Base_Datos_SAGAPI_25_TRABAJADORES_SIMULADOS_v1_2.xlsx"))
    p.add_argument("--salida", default=os.path.join(AQUI, "resultados"))
    p.add_argument("--tl", type=float, default=60.0)
    p.add_argument("--escenario", default="S06A")
    p.add_argument("--base", default="FIFO", choices=["FIFO", "MILP"])
    p.add_argument("--escribir-excel", action="store_true")
    p.add_argument("--pedidos", type=int, default=2, help="solo piloto: numero de pedidos activos seleccionados")
    p.add_argument("--max-operaciones", type=int, default=36, help="solo piloto: limite de operaciones MILP")
    p.add_argument("--horizonte-externos", type=float, default=96.0,
                   help="solo piloto: horas productivas con operaciones externas FUTURAS reservadas")
    p.add_argument("--ventanas", type=int, default=3, help="solo piloto rodante: número de turnos a resolver")
    p.add_argument("--paso-rodante", type=float, default=8.0, help="solo piloto rodante: horas productivas comprometidas por paso")
    p.add_argument("--personal-estricto", action="store_true",
                   help="en el comando caso, detener la ejecución si el verificador detecta conflictos laborales")
    a = p.parse_args()
    os.makedirs(a.salida, exist_ok=True)
    tl = (a.tl,) * 3
    if a.comando == "validar":
        return cmd_validar(a)
    if a.comando == "caso":
        return cmd_caso(a)
    if a.comando == "auditar-personal":
        return cmd_auditar_personal(a)
    if a.comando == "integrar-personal":
        return cmd_integrar_personal(a)
    if a.comando == "rodante-personal":
        return cmd_rodante_personal(a)
    if a.comando == "exportar-mps":
        return cmd_exportar(a)
    E = Experimentos(a.excel, a.salida, tl=tl, log=log)
    meta = dict(version=__version__, highs=version_highs(), python=sys.version.split()[0], inicio=time.strftime("%Y-%m-%d %H:%M:%S"),
                excel=os.path.basename(a.excel), limite_s=a.tl)
    if a.comando in ("anual", "todo"):
        E.e0_fifo()
        E.e1_anual()
    if a.comando in ("escenarios", "todo"):
        E.e2_escenarios()
        E.e2b_recurrentes(politica="A")
        E.e2b_recurrentes(politica="B")
    if a.comando in ("montecarlo", "todo"):
        E.e5_montecarlo()
    if a.comando in ("pareto", "todo"):
        E.e3_pareto()
    if a.comando in ("sensibilidad", "todo"):
        E.e4_sensibilidad()
        E.e4_anual_sensibilidad()
    meta["fin"] = time.strftime("%Y-%m-%d %H:%M:%S")
    json.dump(meta, open(os.path.join(a.salida, f"meta_{a.comando}.json"), "w"), indent=1)
    if a.comando in ("reportes", "todo"):
        from sagapi import reportes
        reportes.generar(E, a.salida, escribir_excel=a.escribir_excel)


if __name__ == "__main__":
    main()
