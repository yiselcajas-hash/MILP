"""Auditoría explícita de calendario para las operaciones del piloto integrado.

Segmenta horas productivas en turnos reales definidos en 07_CALENDARIO (sin
repartir el operario dentro de una misma operación). No cambia la formulación.
"""
from __future__ import annotations
import datetime as dt
from collections import defaultdict

EPS = 1e-6


def segmentar_turnos(cal, inicio, fin):
    if inicio < -EPS or fin <= inicio + EPS:
        raise ValueError(f'Intervalo productivo inválido [{inicio}, {fin}]')
    if fin > cal.total + EPS:
        raise ValueError(f'La operación termina en hora productiva {fin:.2f}; horizonte calendario {cal.total:.2f}.')
    inicio, fin = max(0., inicio), min(fin,cal.total)
    out=[]
    for i in cal.prod_idx:
        base=cal.base[i]
        if base + cal.h_dia <= inicio + EPS:
            continue
        if base >= fin - EPS:
            break
        off=0.
        for ha,hb in cal.tramos:
            segmento_inicio=base+off
            segmento_fin=segmento_inicio+(hb-ha)
            a,b=max(inicio,segmento_inicio),min(fin,segmento_fin)
            if b > a + EPS:
                fecha=cal.fechas[i]
                reloj_inicio=dt.datetime.combine(fecha,dt.time())+dt.timedelta(hours=ha+(a-segmento_inicio))
                reloj_fin=dt.datetime.combine(fecha,dt.time())+dt.timedelta(hours=ha+(b-segmento_inicio))
                out.append(dict(fecha=fecha.isoformat(),inicio_h=a,fin_h=b,
                                inicio_reloj=reloj_inicio.isoformat(sep=' '),
                                fin_reloj=reloj_fin.isoformat(sep=' '),
                                horas=b-a))
            off += hb-ha
    suma=sum(x['horas'] for x in out)
    if abs(suma-(fin-inicio))>max(EPS,1e-7*(fin-inicio)):
        raise ValueError(f'Cobertura de turnos incompleta: requerido {fin-inicio}, cubierto {suma}')
    return out


def comprobar_jornadas(cal, asignaciones):
    """asignaciones: lista {operacion_id, trabajador_simulado, inicio_h, fin_h}.

    Verifica descansos/jornadas con la jornada de ocho horas MODELADA,
    no comprueba fichaje real, ausentismo, descansos individuales o tareas indirectas.
    """
    por_dia=defaultdict(float)
    filas=[]
    for op in asignaciones:
        try:
            segmentos=segmentar_turnos(cal,float(op['inicio_h']),float(op['fin_h']))
        except ValueError as exc:
            raise ValueError(f'Operación {op["operacion_id"]}: {exc}') from exc
        for sg in segmentos:
            por_dia[(op['trabajador_simulado'],sg['fecha'])] += sg['horas']
            filas.append({**op,**sg,'habilidades':'SIMULADAS_NO_VERIFICADAS',
                          'regla_turno':'07_CALENDARIO_UN_TURNO_8H'})
    for (w,d),h in por_dia.items():
        if h > cal.h_dia + EPS:
            raise ValueError(f'Trabajador {w} excede {cal.h_dia}h el día {d}: {h:.4f}h')
    return filas,dict(
        segmentos=len(filas),
        max_horas_trabajador_dia=max(por_dia.values(),default=0.),
        jornadas_trabajador_observadas=len(por_dia),
        segmentos_sobre_8h=0,
        advertencia_feriados='Las marcas de 07_CALENDARIO se mantienen sin validar con SAGAPI.')
