"""Audita los CSV generados por el piloto SAGAPI 1.3.4 sin ejecutar MILP.

Ejemplo (CMD, desde carpeta del proyecto):
  .venv\\Scripts\\python.exe -X utf8 herramientas\\auditar_rodante_csv.py --carpeta resultados_rodante_134 --escenario S08A
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sagapi.auditoria_rodante import auditar_cruces

EPS=1e-5


def leer_csv(archivo):
    with open(archivo, 'r', encoding='utf-8-sig', newline='') as fh:
        return list(csv.DictReader(fh))


def auditar_carpeta(carpeta, escenario):
    pref=Path(carpeta)/f'rodante_{escenario}'
    resumen=json.loads(Path(f'{pref}_resumen.json').read_text(encoding='utf-8-sig'))
    filas_comp=leer_csv(f'{pref}_compromisos.csv')
    reservas=leer_csv(f'{pref}_reservas_externas_por_ventana.csv')
    arrastres=leer_csv(f'{pref}_arrastres_entre_turnos.csv')
    jornadas=leer_csv(f'{pref}_compromisos_jornadas.csv')
    decisiones=leer_csv(f'{pref}_decisiones.csv')

    comp={}
    errores=[]
    for f in filas_comp:
        o=int(f['operacion_id'])
        if o in comp:
            errores.append(f'Operación comprometida duplicada {o}')
        comp[o]=(f['maquina'],float(f['inicio_h']),float(f['fin_h']),f['trabajador_simulado'])
    aud,errs=auditar_cruces(comp,reservas)
    errores.extend(errs)
    # Todas las operaciones transferidas deben existir con iguales valores
    # en los compromisos y la ventana registrada.
    for f in arrastres:
        o=int(f['operacion_id'])
        actual=(f['maquina'],float(f['inicio_h']),float(f['fin_h']),f['trabajador_simulado'])
        if o not in comp or (actual[0] != comp[o][0] or actual[3] != comp[o][3]
                             or abs(actual[1]-comp[o][1])>EPS or abs(actual[2]-comp[o][2])>EPS):
            errores.append(f'Arrastre {o} cambió de máquina, horario o trabajador')
        if float(f['horas_pendientes_al_abrir']) <= 0:
            errores.append(f'Arrastre {o} sin duración pendiente')
    # Las filas definitivas deben corresponder a exactamente una decisión
    # marcada como comprometida en alguna ventana.
    comprometidas=defaultdict(list)
    for f in decisiones:
        if f['comprometida_en_esta_ventana'].lower() == 'true':
            comprometidas[int(f['operacion_id'])].append(f)
    for o,dato in comp.items():
        if len(comprometidas[o])!=1:
            errores.append(f'Compromiso {o} no tiene exactamente un origen ({len(comprometidas[o])})')
        else:
            f=comprometidas[o][0]
            if (f['maquina']!=dato[0] or f['trabajador_simulado'] != dato[3]
                or abs(float(f['inicio_h'])-dato[1])>EPS
                or abs(float(f['fin_h'])-dato[2])>EPS):
                errores.append(f'Compromiso {o} difiere del plan de su ventana de origen')
    for o in comprometidas:
        if o not in comp:
            errores.append(f'Compromiso {o} falta en CSV definitivo')
    # Cobertura en jornadas de todas las operaciones comprometidas.
    horas_por_operacion=defaultdict(float)
    horas_por_persona_dia=defaultdict(float)
    for f in jornadas:
        o=int(f['operacion_id'])
        horas=float(f['horas'])
        horas_por_operacion[o]+=horas
        horas_por_persona_dia[(f['trabajador_simulado'],f['fecha'])]+=horas
        if o not in comp:
            errores.append(f'Segmento de operación {o} ausente de compromisos')
        elif f['trabajador_simulado']!=comp[o][3]:
            errores.append(f'Segmento {o} con trabajador distinto')
        if horas < -EPS:
            errores.append(f'Segmento {o} con horas negativas')
    for o,(m,s,c,w) in comp.items():
        if abs(horas_por_operacion[o]-(c-s))>1e-4:
            errores.append(f'Operación {o} no está cubierta por segmentos de jornadas')
    max_horas=max(horas_por_persona_dia.values(),default=0.0)
    if max_horas>8.0+EPS:
        errores.append(f'Una persona excede 8h en un día: {max_horas:.3f}h')
    if len(filas_comp)!=resumen['operaciones_comprometidas']:
        errores.append('Cantidad de compromisos no coincide con resumen')
    if len(reservas)!=resumen.get('filas_reservas_externas_exportadas'):
        errores.append('Cantidad de reservas no coincide con resumen')
    if len(arrastres)!=resumen.get('filas_arrastres_exportadas'):
        errores.append('Cantidad de arrastres no coincide con resumen')
    if len(resumen['ventanas'])!=resumen['ventanas_resueltas']:
        errores.append('Historial de ventanas incompleto')
    salida=dict(version='1.3.4-auditoria-csv-independiente',
                escenario=escenario,estado_piloto=resumen['estado'],
                operaciones_comprometidas=len(comp),
                reservas_externas_observaciones=len(reservas),
                reservas_externas_unicas=aud['reservas_externas_unicas'],
                arrastres_registrados=len(arrastres),
                max_horas_por_trabajador_dia=max_horas,
                errores=errores,
                valido_solo_para_alcance_exportado=not errores,
                cobertura_anual_validada=False,
                advertencia='Sin validación de operaciones externas nunca protegidas, competencias reales ni feriados.')
    return salida


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--carpeta',required=True)
    p.add_argument('--escenario',default='S08A')
    a=p.parse_args()
    resultado=auditar_carpeta(a.carpeta,a.escenario)
    dest=Path(a.carpeta)/f'rodante_{a.escenario}_auditoria_independiente.json'
    dest.write_text(json.dumps(resultado,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(resultado,ensure_ascii=False,indent=2))
    print('Reporte guardado en:',dest)
    if resultado['errores']:
        sys.exit(1)

if __name__=='__main__':main()
