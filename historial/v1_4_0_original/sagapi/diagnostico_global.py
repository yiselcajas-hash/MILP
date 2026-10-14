"""Diagnóstico de coherencia al insertar los compromisos MILP en FIFO ANUAL.

Nunca convierte la programación hipotética ensamblada en un plan ejecutable.
Operaciones sin trabajador real siguen no auditadas laboralmente.
"""
from collections import defaultdict

EPS=1e-5


def diagnosticar(inst, base, compromisos, ventanas_fallas=(), limite_muestras=200):
    """Retorna métricas y conflictos (máquinas, precedencias, averías).

    base[o] = (máquina, inicio, fin); compromisos[o] añade trabajador.
    Se preserva el programa base para todas las operaciones no comprometidas.
    """
    errores=[]
    nops=len(inst.ops)
    ensamblado=dict(base)
    for o, (m,s,c,w) in compromisos.items():
        if o not in base:
            errores.append(dict(tipo='ID_INVALIDO', operacion_a=o, operacion_b='', recurso='', inicio_h=s, fin_h=c))
        else:
            ensamblado[o]=(m,s,c)
    no_cubiertas=sorted(set(range(nops))-set(ensamblado))
    for o in no_cubiertas[:limite_muestras]:
        errores.append(dict(tipo='FALTA_OPERACION',operacion_a=o,operacion_b='',recurso='',inicio_h='',fin_h=''))
    por_maquina=defaultdict(list)
    for o,(m,s,c) in ensamblado.items():
        if c<=s+EPS:
            errores.append(dict(tipo='DURACION_INVALIDA',operacion_a=o,operacion_b='',recurso=m,inicio_h=s,fin_h=c))
        por_maquina[m].append((s,c,o))
    n_maquina=0
    for m,bl in por_maquina.items():
        bl.sort()
        # Todos los solapamientos, incluso anidamientos que un chequeo solo-adjacent omitiría.
        for i,(s,c,o) in enumerate(bl):
            j=i+1
            while j<len(bl) and bl[j][0]<c-EPS:
                ss,cc,oo=bl[j]
                n_maquina+=1
                if len(errores)<limite_muestras:
                    errores.append(dict(tipo='MAQUINA_SOLAPADA',operacion_a=o,operacion_b=oo,recurso=m,inicio_h=max(s,ss),fin_h=min(c,cc)))
                j+=1
    n_precedencia=0
    for j, ops in inst.job_ops.items():
        for a,b in zip(ops,ops[1:]):
            if a not in ensamblado or b not in ensamblado: continue
            if ensamblado[b][1] < ensamblado[a][2]-EPS:
                n_precedencia+=1
                if len(errores)<limite_muestras:
                    errores.append(dict(tipo='PRECEDENCIA',operacion_a=a,operacion_b=b,recurso=inst.jobs[j]['id'],inicio_h=ensamblado[b][1],fin_h=ensamblado[a][2]))
    n_averias=0
    for o,(m,s,c) in ensamblado.items():
        for mf,fs,fc in ventanas_fallas:
            if m==mf and s < fc-EPS and fs < c-EPS:
                n_averias+=1
                if len(errores)<limite_muestras:
                    errores.append(dict(tipo='AVERIA_MAQUINA',operacion_a=o,operacion_b='',recurso=m,inicio_h=max(s,fs),fin_h=min(c,fc)))
    # No se auditó personal de todos los externos: NO proclamar factibilidad anual.
    cobertura_compromisos=len(compromisos)/nops if nops else 0
    resumen=dict(
        alcance='ENSAMBLAJE_HIPOTETICO_FIFO_CON_COMPROMISOS_MILP',
        pedidos_totales=len(inst.jobs), operaciones_totales=nops,
        operaciones_base=len(base), operaciones_comprometidas_milp=len(compromisos),
        operaciones_sin_compromiso_milp=nops-len(compromisos),
        porcentaje_operaciones_comprometidas_milp=round(100*cobertura_compromisos,3),
        operaciones_sin_programacion=len(no_cubiertas),
        cruces_maquinas_ensamblaje=n_maquina,
        violaciones_precedencia_ensamblaje=n_precedencia,
        cruces_fallas_ensamblaje=n_averias,
        operaciones_externas_sin_asignacion_laboral_verificada=nops-len(compromisos),
        total_incidencias_diagnosticas=n_maquina+n_precedencia+n_averias+len(no_cubiertas),
        incidencias_exportadas=len(errores),
        programa_global_certificado=False,
        validacion_laboral_real=False,
        mensaje='Diagnóstico informativo: no hay optimización anual conjunta; FIFO externo es referencial y no cuenta con personal real verificado.'
    )
    return resumen, errores
