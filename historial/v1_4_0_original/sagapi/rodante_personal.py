"""Piloto predictivo-reactivo de horizonte rodante, con personal MILP integrado.

Este comando NO evalúa el año completo. Reoptimiza pedidos seleccionados
sucesivamente y compromete solo operaciones cuyo inicio se produce en el
siguiente turno. Mantiene el FIFO de pedidos externos como reserva hipotética
por un horizonte finito. Capacidades/habilidades externas NO verificadas.
"""
from __future__ import annotations

from collections import defaultdict

from .auditoria_rodante import auditar_cruces, verificar_arrastres

EPS = 1e-6


class CompromisoRoto(RuntimeError):
    """Se alteró una operación cuyo inicio ya se había comprometido."""


def verificar_compromisos(compromisos, programa, asignaciones=None, tol=1e-5):
    """Independiente del solucionador: inmutabilidad y no solapamientos."""
    asignaciones = asignaciones or {}
    errores = []
    por_m = defaultdict(list)
    por_w = defaultdict(list)
    for o, dato in compromisos.items():
        m, s, c, w = dato
        if o not in programa:
            errores.append(f'Operación comprometida {o} ausente del programa')
        else:
            mm, ss, cc = programa[o]
            if mm != m or abs(ss-s) > tol or abs(cc-c) > tol:
                errores.append(f'Operación comprometida {o} modificada')
        if o in asignaciones and w is not None and asignaciones[o] != w:
            errores.append(f'Operación comprometida {o} cambió de trabajador')
        if c <= s + tol:
            errores.append(f'Duración inválida en operación {o}')
        por_m[m].append((s,c,o))
        if w is not None:
            por_w[w].append((s,c,o))
    for tipo, coleccion in (('máquina', por_m), ('trabajador', por_w)):
        for ident, intervalos in coleccion.items():
            intervalos.sort()
            for (_, anterior_fin, anterior_o), (s, _, o) in zip(intervalos, intervalos[1:]):
                if s < anterior_fin - tol:
                    errores.append(f'Solapamiento comprometido de {tipo} {ident}: {anterior_o} y {o}')
    return errores


def resolver_lex(mdl, tl):
    from .solver import solve
    fases = []
    elegido = None
    for numero, (nombre, objetivo) in enumerate((
        ('P1_penalidad', mdl.f1_terms()),
        ('P2_tardanza', mdl.f1b_terms()),
        ('P3_estabilidad', mdl.f2_terms()),
    )):
        if numero == 2 and not mdl.sub.S0:
            break
        mdl.M.set_objective(objetivo)
        r = solve(mdl.M, time_limit=tl)
        fases.append(dict(fase=nombre, estado=r['status'], certificado=r['certificado'],
                          tiempo_s=r['time'], brecha=r['gap'], objetivo=r['obj']))
        if r['x'] is None or not r['certificado']:
            return None, fases
        elegido = r['x']
        if numero == 0:
            cap = r['obj'] + max(1e-4, 1e-7 * abs(r['obj']))
            mdl.M.row(mdl.f1_terms(), -float('inf'), cap)
        elif numero == 1:
            cap = r['obj'] * (1 + 1e-6) + 1e-4
            mdl.M.row(mdl.f1b_terms(), -float('inf'), cap)
    return elegido, fases


def ejecutar(d, inst, base, ventanas_fallas, politica, seleccion, t0,
             n_ventanas=3, paso_h=8.0, horizonte_externos=120.0,
             max_operaciones=36, limite_s=60.0, beta=8.0, log=None):
    """Ventanas sucesivas: se reoptimiza pero solo se fija el turno siguiente.

    Devuelve (resumen, detalle_ventanas, compromisos, programa). Ante fallo de
    cualquier ventana se DETIENE con estado parcial, nunca declara éxito.
    """
    from .cobertura_externa import preparar_con_cobertura, preparar_reservas_futuras
    from .personal_integrado import ModeloPersonalOperaciones
    from .jornada_piloto import comprobar_jornadas

    if n_ventanas < 1 or paso_h <= 0 or horizonte_externos < paso_h:
        raise ValueError('Ventanas y paso positivos; horizonte externo >= paso de turno')
    if not seleccion:
        raise ValueError('Selecciona al menos un pedido')
    programa = dict(base)
    pedidos = list(dict.fromkeys(seleccion))
    compromisos = {}     # operación -> (maquina, comienzo, fin, trabajador)
    asignaciones_externas = {}  # conservar trabajador externo entre ventanas
    registro = []
    detalle = []
    estado = 'PILOTO_INCOMPLETO'
    warnings = []
    historial_reservas = []  # instantáneas externas, exportables por ventana
    registro_arrastres = []  # operaciones iniciadas antes y activas al abrir un turno
    for k in range(n_ventanas):
        ahora = t0 + k * paso_h
        fin_turno = ahora + paso_h
        arrastres_entrantes = {o: dato for o, dato in compromisos.items()
                                if dato[1] < ahora - EPS and dato[2] > ahora + EPS}
        try:
            sub, cobertura = preparar_con_cobertura(
                d, inst, programa, ahora, pedidos, ventanas_fallas, politica)
            pedidos = list(sub.jobs)
            reservas = preparar_reservas_futuras(
                sub, programa, horizonte_externos,
                asignaciones_previas=asignaciones_externas)
            asignaciones_externas.update({o: w for o, (_, _, _, w)
                                           in sub.trabajadores_externos.items()})
            if reservas['cruces_reservas_con_averia']:
                raise CompromisoRoto('Plan externo de referencia cruza una avería')
            if not sub.free:
                estado = 'SIN_OPERACIONES_PENDIENTES'
                break
            mdl = ModeloPersonalOperaciones(
                sub, max_operaciones=max_operaciones, beta=beta, estabilidad=True,
                personal_fijo={**{o: asignaciones_externas[o] for o in sub.externas_activas
                                  if o in asignaciones_externas},
                               **{o: ddd[3] for o, ddd in compromisos.items()
                                  if o in sub.fixed and ddd[2] > ahora + EPS}})
            x, fases = resolver_lex(mdl, limite_s)
            if x is None:
                raise CompromisoRoto('Una fase no obtuvo optimalidad certificada')
            errores = mdl.verificar_personal(x)
            if errores:
                raise CompromisoRoto(f'Verificación interna: {errores[:3]}')
            nuevas = mdl.decode(x)
            personal = mdl.asignaciones(x)
            # Las operaciones comprometidas que cruzan de turno deben conservar
            # su máquina, inicio, fin y trabajador. Esta comprobación es ajena
            # a la función objetivo y evita falsos "éxitos" por replanificación.
            arrastres_visibles = {}
            for o in arrastres_entrantes:
                if o in sub.fixed and o in personal:
                    arrastres_visibles[o] = (*sub.fixed[o], personal[o])
            errs_arrastre = verificar_arrastres(arrastres_entrantes, arrastres_visibles)
            if errs_arrastre:
                raise CompromisoRoto(str(errs_arrastre[:3]))
            for o in sub.externas_activas:
                if o in asignaciones_externas and personal[o] != asignaciones_externas[o]:
                    raise CompromisoRoto(f'Operación externa activa {o} cambia trabajador')
                asignaciones_externas[o] = personal[o]
            # Los compromisos de turnos anteriores jamás deben alterarse.
            actualizado = dict(programa)
            for o, (m, s) in nuevas.items():
                actualizado[o] = (m, s, s+sub.pR[(o,m)])
            errs = verificar_compromisos(compromisos, actualizado, personal)
            if errs:
                raise CompromisoRoto(str(errs[:3]))
            nuevos_comprometidos = []
            propuesta = dict(compromisos)
            for o, (m,s) in nuevas.items():
                if s < fin_turno-EPS:
                    c = s+sub.pR[(o,m)]
                    if c > ahora + horizonte_externos + EPS:
                        raise CompromisoRoto(
                            f'Operación {o} termina fuera de horizonte externo protegido')
                    propuesta[o] = (m,s,c,personal[o])
                    nuevos_comprometidos.append(o)
            errs = verificar_compromisos(propuesta, actualizado, personal)
            if errs:
                raise CompromisoRoto(str(errs[:3]))
            # Exportar TODAS las reservas externas protegidas en esta ventana,
            # tanto futuras como las que ya estaban ejecutándose al abrirla.
            # No deben confundirse con operaciones reoptimizadas por el MILP.
            reservas_actuales = [
                dict(ventana=k+1, operacion_id=o, maquina=m, inicio_h=s,
                     fin_h=c, trabajador_simulado=w, tipo='FUTURA_FIFO_CONGELADA')
                for o, (m,s,c,w) in sorted(sub.trabajadores_externos.items())]
            for o, (m,s,c) in sorted(sub.externas_activas.items()):
                if o not in personal:
                    raise CompromisoRoto(f'Operación externa activa {o} no tiene trabajador')
                reservas_actuales.append(dict(
                    ventana=k+1, operacion_id=o, maquina=m, inicio_h=s,
                    fin_h=c, trabajador_simulado=personal[o], tipo='ACTIVA_EXTERNA_EN_T0'))
            # Auditoría acumulada e independiente: cualquier conflicto con
            # reservas de ventanas PREVIAS debe detener el piloto.
            aud_externos, errs_ext = auditar_cruces(
                propuesta, historial_reservas + reservas_actuales)
            if errs_ext:
                raise CompromisoRoto('Auditoría externa: ' + '; '.join(errs_ext[:3]))
            filas_jornadas = [dict(operacion_id=o, trabajador_simulado=w,
                                   inicio_h=s,fin_h=c)
                              for o,(m,s,c,w) in propuesta.items()]
            _, aud_jornada = comprobar_jornadas(d.calendario, filas_jornadas)
            # Solo después de pasar las auditorías se comprometen los resultados.
            compromisos = propuesta
            historial_reservas.extend(reservas_actuales)
            for o, (m,s,c,w) in sorted(arrastres_entrantes.items()):
                registro_arrastres.append(dict(
                    ventana=k+1, operacion_id=o, maquina=m, inicio_h=s,
                    fin_h=c, trabajador_simulado=w, horas_pendientes_al_abrir=c-ahora,
                    tipo='ARRASTRE_COMPROMETIDO'))
            # Reserva FIFO no integrada fuera del horizonte: la cobertura no es global.
            programa = actualizado
            registro.append(dict(ventana=k+1, inicio_h=ahora, compromiso_h=fin_turno,
                pedidos=len(pedidos), operaciones_libres=len(sub.free),
                operaciones_comprometidas_nuevas=len(nuevos_comprometidos),
                operaciones_comprometidas_acumuladas=len(compromisos),
                reservas_externas=len(sub.trabajadores_externos),
                externas_pendientes=reservas['operaciones_externas_futuras_sin_proteger'],
                estado='OPTIMO_EN_SUBPROBLEMA', fases=fases,
                auto_incluidos=cobertura['pedidos_autoincluidos_por_falla'],
                personal_usado=len(set(personal.values())),
                horas_maximas_trabajador_dia=aud_jornada['max_horas_trabajador_dia'],
                segmentos_calendario_comprometidos=aud_jornada['segmentos'],
                arrastres_entrantes=len(arrastres_entrantes),
                compromisos_vigentes_al_cerrar=sum(
                    1 for m,s,c,w in compromisos.values() if s < fin_turno-EPS and c > fin_turno+EPS),
                reservas_externas_exportadas=len(reservas_actuales),
                reservas_externas_unicas_auditadas=aud_externos['reservas_externas_unicas'],
                cruces_maquina_con_reservas=aud_externos['cruces_maquina_compromiso_externa'],
                cruces_trabajador_con_reservas=aud_externos['cruces_trabajador_compromiso_externa'],
                penalidad_subproblema=sum(c*x[v] for v,c in mdl.f1_terms()),
                tardanza_subproblema=sum(c*x[v] for v,c in mdl.f1b_terms()),
                inestabilidad_subproblema=sum(c*x[v] for v,c in mdl.f2_terms())+mdl.f2_const(),
                cobertura_global=False))
            for o, (m,s) in sorted(nuevas.items()):
                detalle.append(dict(ventana=k+1, operacion_id=o,
                    pedido=inst.jobs[inst.ops[o]['job']]['id'], maquina=m,
                    trabajador_simulado=personal[o], inicio_h=s,
                    fin_h=s+sub.pR[(o,m)], comprometida_en_esta_ventana=o in nuevos_comprometidos))
            if log:
                log(f'RODANTE ventana {k+1}: {len(pedidos)} pedidos; '
                    f'{len(sub.free)} libres; {len(nuevos_comprometidos)} compromisos nuevos; '
                    f'{len(sub.trabajadores_externos)} reservas; P1={registro[-1]["penalidad_subproblema"]:.2f}')
        except Exception as exc:
            warnings.append(f'Ventana {k+1}: {type(exc).__name__}: {exc}')
            estado = 'DETENIDO_SIN_CERTIFICACION_GLOBAL'
            if log:
                log('RODANTE DETENIDO: '+warnings[-1])
            break
    else:
        estado = 'VENTANAS_SOLUCIONADAS_COBERTURA_PARCIAL'
    auditoria_final, errores_finales = auditar_cruces(compromisos, historial_reservas)
    if errores_finales:
        warnings.extend(errores_finales[:10])
        estado = 'DETENIDO_SIN_CERTIFICACION_GLOBAL'
    resumen = dict(version='1.3.4-piloto-rodante-auditable', estado=estado,
        ventanas_solicitadas=n_ventanas, ventanas_resueltas=len(registro),
        paso_turno_h=paso_h, horizonte_externo_h=horizonte_externos,
        pedidos_incluidos=[inst.jobs[j]['id'] for j in pedidos],
        operaciones_comprometidas=len(compromisos),
        externas_con_trabajador_simulado=len(asignaciones_externas),
        cobertura_anual_validada=False, habilidades_verificadas=False,
        calendario_feriados_verificado=False,
        reservas_externas_referenciales=True, advertencias=warnings,
        auditoria_reservas_y_compromisos=auditoria_final,
        filas_reservas_externas_exportadas=len(historial_reservas),
        filas_arrastres_exportadas=len(registro_arrastres),
        nota='Piloto rodante sobre pedidos seleccionados y reservas FIFO simuladas. No equivale a validación de 96 pedidos.')
    return resumen, registro, detalle, compromisos, programa, historial_reservas, registro_arrastres
