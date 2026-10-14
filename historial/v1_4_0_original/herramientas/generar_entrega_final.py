#!/usr/bin/env python3
"""Una sola ejecución reproducible: pruebas + dos pilotos rodantes + auditoría + diagnóstico global.

Desde la raíz del proyecto:
  .venv\\Scripts\\python.exe -X utf8 herramientas\\generar_entrega_final.py --tl 60
El diagnóstico anual NO certifica una solución conjunta de 96 pedidos.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from sagapi.diagnostico_global import diagnosticar
from sagapi.experimentos import Experimentos, _ventanas
from sagapi import reglas, __version__
from herramientas.auditar_rodante_csv import auditar_carpeta


def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as fh:
        for buf in iter(lambda:fh.read(1024*1024),b''):
            h.update(buf)
    return h.hexdigest()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--salida', default='EVIDENCIA_FINAL')
    p.add_argument('--tl',type=float,default=60.0)
    p.add_argument('--omitir-pruebas', action='store_true',help='solo si ya se ejecutaron tests; se informa en el reporte')
    a=p.parse_args()
    out=(ROOT/a.salida).resolve()
    out.mkdir(parents=True, exist_ok=True)
    logs=out/'logs'; logs.mkdir(exist_ok=True)
    mapa=[]

    def correr(nombre,args):
        cmd=[sys.executable,'-X','utf8',*args]
        print(f'[{nombre}] Ejecutando...',flush=True)
        tic=time.monotonic()
        r=subprocess.run(cmd,cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
                         text=True,encoding='utf-8',errors='replace')
        (logs/f'{nombre}.txt').write_text('COMANDO: '+subprocess.list2cmdline(cmd)+'\n\n'+r.stdout, encoding='utf-8')
        mapa.append(dict(paso=nombre,correcto=r.returncode==0,segundos=round(time.monotonic()-tic,2),
                         log=f'logs/{nombre}.txt'))
        print(f'[{nombre}] '+('OK' if r.returncode==0 else 'ERROR')+f' ({mapa[-1]["segundos"]}s)',flush=True)
        if r.returncode:
            print(r.stdout[-2400:],flush=True)
            raise RuntimeError(f'{nombre} no superó la validación; ver {logs/nombre}.txt')

    base_py=['Optimizacion_MILP_SAGAPI.py']
    correr('01_validar',base_py+['validar','--salida',str(out/'validacion')])
    if not a.omitir_pruebas:
        correr('02_unitarias',['-m','unittest','discover','-s','tests','-p','test_*.py','-v'])
        correr('03_enumeracion',['-m','tests.test_enumeracion','40'])
    escenarios=[('S08A',3,5),('S13A',2,3)]
    auditorias={}
    resultados={}
    for esc,pedidos,ventanas in escenarios:
        destino=out/f'RODANTE_{esc}'
        correr('04_rodante_'+esc,base_py+['rodante-personal','--escenario',esc,
            '--pedidos',str(pedidos),'--ventanas',str(ventanas),
            '--paso-rodante','8','--max-operaciones','36',
            '--horizonte-externos','120','--tl',str(a.tl),'--salida',str(destino)])
        auditoria=auditar_carpeta(destino,esc)
        (destino/f'rodante_{esc}_auditoria_independiente.json').write_text(
            json.dumps(auditoria,indent=2,ensure_ascii=False),encoding='utf-8')
        if auditoria['errores'] or not auditoria['valido_solo_para_alcance_exportado']:
            raise RuntimeError(f'Auditoría independiente rechaza {esc}: {auditoria["errores"][:3]}')
        auditorias[esc]=auditoria
        resumen=json.loads((destino/f'rodante_{esc}_resumen.json').read_text(encoding='utf-8-sig'))
        if resumen['ventanas_resueltas'] != ventanas or resumen.get('cobertura_anual_validada'):
            raise RuntimeError(f'Estado inesperado en {esc}; no generar un éxito ambiguo.')
        with (destino/f'rodante_{esc}_compromisos.csv').open(encoding='utf-8-sig',newline='') as f:
            compromisos={int(x['operacion_id']):(
                x['maquina'],float(x['inicio_h']),float(x['fin_h']),x['trabajador_simulado'])
                for x in csv.DictReader(f)}
        resultados[esc]=resumen
        # Diagnóstico de fusión hipotética FIFO anual + operaciones realmente comprometidas:
        # muy distinto a una optimización global o factibilidad anual certificada.
        e=Experimentos(str(ROOT/'Base_Datos_SAGAPI_25_TRABAJADORES_SIMULADOS_v1_2.xlsx'),
                       str(destino),tl=(a.tl,)*3,log=lambda _:None)
        programa_fifo=reglas.fifo_plan(e.I,range(len(e.I.jobs)))[0]
        configuracion={r['id']:r for r in e.d.escenarios}[esc]
        eventos=[v for v in configuracion['eventos'].split('+') if v]
        ventana_fallas=_ventanas(e.d,eventos)
        diagnostico,incidencias=diagnosticar(e.I,programa_fifo,compromisos,ventana_fallas)
        (destino/f'rodante_{esc}_diagnostico_global_referencial.json').write_text(
            json.dumps(diagnostico,indent=2,ensure_ascii=False),encoding='utf-8')
        with (destino/f'rodante_{esc}_incidencias_globales.csv').open('w',encoding='utf-8-sig',newline='') as f:
            cols=['tipo','operacion_a','operacion_b','recurso','inicio_h','fin_h']
            w=csv.DictWriter(f,fieldnames=cols);w.writeheader();w.writerows(incidencias)
        resultados[esc]['diagnostico_global_referencial']=diagnostico
        print(f'[{esc}] {resumen["operaciones_comprometidas"]} compromisos; '+
              f'{auditoria["reservas_externas_unicas"]} reservas únicas; '+
              f'{diagnostico["total_incidencias_diagnosticas"]} incidencias del ENSAMBLAJE hipotético.',flush=True)
    datos=[]
    for esc, _, _ in escenarios:
        r=resultados[esc]; aud=auditorias[esc]; diag=r['diagnostico_global_referencial']
        datos.append(dict(escenario=esc,ventanas=r['ventanas_resueltas'],
          pedidos_piloto=len(r['pedidos_incluidos']),compromisos=r['operaciones_comprometidas'],
          operaciones_totales=diag['operaciones_totales'],porcentaje_cobertura=diag['porcentaje_operaciones_comprometidas_milp'],
          reservas_unicas=aud['reservas_externas_unicas'],auditoria_errores=len(aud['errores']),
          max_horas_trabajador_dia=round(aud['max_horas_por_trabajador_dia'],2),
          incidencias_fusion_fifo=diag['total_incidencias_diagnosticas'],
          validacion_global=False))
    with (out/'RESUMEN_COMPARATIVO.csv').open('w',newline='',encoding='utf-8-sig') as fh:
        w=csv.DictWriter(fh,fieldnames=list(datos[0]));w.writeheader();w.writerows(datos)
    reporte=['# SAGAPI — Informe técnico final del prototipo MILP (v1.4.0)', '',
      '**Estado:** ENTREGA ACADÉMICA DEL PROTOTIPO; **no** certifica factibilidad anual ni despliegue real.', '',
      '## Alcance y datos', '',
      '- 96 pedidos y 1.152 operaciones de base modelada, cuatro familias y 15 máquinas.',
      '- Empresa: 25 trabajadores de producción y un turno de 8 h (declaración real).',
      '- Matriz de habilidades, pedidos, penalidades y fallas: contienen supuestos/simulaciones.',
      '- El MILP asigna trabajador–operación y reprograma subproblemas mediante ventanas de 8 h.',
      '- Las reservas FIFO externas solo quedan protegidas dentro del horizonte definido (120 h).',
      '- No se modificó el Excel original ni se asumió que SAGAPI trabaja en feriados.', '',
      '## Resultados reproducidos', '',
      '| Escenario | Ventanas | Pedidos piloto | Operaciones comprometidas / 1.152 | Reservas externas únicas | Errores de auditoría | Incidencias del ensamblaje FIFO hipotético |',
      '|---|---:|---:|---:|---:|---:|---:|']
    for x in datos:
        reporte.append(f'| {x["escenario"]} | {x["ventanas"]} | {x["pedidos_piloto"]} | '+
          f'{x["compromisos"]} / {x["operaciones_totales"]} ({x["porcentaje_cobertura"]}%) | '+
          f'{x["reservas_unicas"]} | {x["auditoria_errores"]} | {x["incidencias_fusion_fifo"]} |')
    reporte.extend(['', '**Interpretación:** La auditoría independiente no encontró errores en los '+
      'compromisos y reservas exportados. El diagnóstico adicional inserta los compromisos en '+
      'un FIFO anual **hipotético** y busca choques: no es un plan anual optimizado. '+
      'Un resultado con cero choques tampoco certifica la disponibilidad laboral anual.', '',
      '## Limitaciones que deben declararse', '',
      '1. **Cobertura global anual NO VALIDADA.** No se reoptimizaron simultáneamente los 96 pedidos.',
      '2. Las habilidades de los 25 trabajadores no han sido comprobadas con SAGAPI.',
      '3. No se dispone de certificación del trabajo en feriados ni de tareas indirectas.',
      '4. Penalidades y ahorros son resultados de supuestos modelados, **no beneficios económicos realizados**.',
      '5. Diferentes ventanas tienen distintos conjuntos pendientes: sus penalidades P1 no son ahorros acumulativos.',
      '6. Los horarios FIFO congelados y la fusión global son escenarios de referencia, no órdenes de producción autorizadas.', '',
      '## Declaración académica sugerida', '',
      '> Se desarrolló y verificó computacionalmente un prototipo MILP predictivo-reactivo '+
      'con asignación integrada de operarios simulados y reprogramación mediante horizonte rodante. '+
      'Los subproblemas evaluados alcanzaron soluciones certificadas por el solucionador y '+
      'superaron auditorías independientes de compromisos, jornadas y reservas externas. '+
      'Los resultados no constituyen una validación operativa anual de toda la planta y requieren '+
      'verificación de competencias del personal y calendario productivo.', '',
      '## Reproducibilidad', '',
      '- Comando único: `.venv\\Scripts\\python.exe -X utf8 herramientas\\generar_entrega_final.py --tl 60`',
      '- Resultados individuales: `RODANTE_S08A/` y `RODANTE_S13A/`.',
      '- Registros detallados de ejecución: `logs/`.',
      '- Diagnóstico global y sus incidencias: `rodante_*_diagnostico_global_referencial.json` y `*_incidencias_globales.csv`.',
      '- Resumen de verificación: `RESUMEN_COMPARATIVO.csv`.', '',
      '## Criterio de aceptación', '',
      '**APROBADO:** Pruebas unitarias, enumeración matemática, ventanas piloto y auditoría independiente.',
      '**PENDIENTE:** Cobertura global de 96 pedidos, habilidades reales y calendario feriado.', ''])
    (out/'INFORME_TECNICO_ENTREGA.md').write_text('\n'.join(reporte),encoding='utf-8')
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        for esc,_,_ in escenarios:
            ventanas=resultados[esc]['ventanas']
            fig,ax=plt.subplots(figsize=(8.0,4.0))
            ax.plot([v['ventana'] for v in ventanas],
                    [v['operaciones_comprometidas_acumuladas'] for v in ventanas],marker='o')
            ax.set(xlabel='Ventana rodante (turnos de 8 h)',ylabel='Operaciones comprometidas acumuladas',
                   title=f'SAGAPI: continuidad de compromisos — {esc}')
            ax.set_xticks([v['ventana'] for v in ventanas]);ax.grid(alpha=.25)
            fig.tight_layout();fig.savefig(out/f'FIG_COMPROMISOS_{esc}.png',dpi=160);plt.close(fig)
    except ImportError:
        print('Matplotlib no disponible: se omiten gráficos opcionales.')
    manifests=[]
    for path in sorted(list(out.rglob('*'))+[ROOT/'Optimizacion_MILP_SAGAPI.py',
                            ROOT/'Base_Datos_SAGAPI_25_TRABAJADORES_SIMULADOS_v1_2.xlsx']):
        if path.is_file() and path.name!='MANIFIESTO_SHA256.csv':
            manifests.append(dict(archivo=str(path.relative_to(ROOT)),sha256=digest(path)))
    with (out/'MANIFIESTO_SHA256.csv').open('w',encoding='utf-8-sig',newline='') as fh:
        w=csv.DictWriter(fh,fieldnames=['archivo','sha256']);w.writeheader();w.writerows(manifests)
    ejecucion=dict(version=__version__,python=sys.version.split()[0],sistema=platform.platform(),
        timestamp=time.strftime('%Y-%m-%d %H:%M:%S'),pruebas_omitidas=a.omitir_pruebas,
        pasos=mapa,escenarios=datos,resultado='PILOTOS_AUDITADOS_COBERTURA_ANUAL_NO_VALIDADA')
    (out/'RESULTADO_EJECUCION.json').write_text(json.dumps(ejecucion,indent=2,ensure_ascii=False),encoding='utf-8')
    print('\nENTREGA COMPUTACIONAL GENERADA:',out)
    print('ESTADO: pilotos auditados; COBERTURA ANUAL NO VALIDADA. Revisar INFORME_TECNICO_ENTREGA.md')

if __name__=='__main__':
    try: main()
    except Exception as exc:
        print('ERROR DE VALIDACIÓN FINAL:',exc,file=sys.stderr)
        sys.exit(1)
