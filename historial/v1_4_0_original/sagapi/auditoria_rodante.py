"""Auditoría independiente del piloto rodante frente a reservas externas.

Alcance deliberadamente PARCIAL: comprueba el conjunto exportado de operaciones
comprometidas y las reservas FIFO externas vistas durante las ventanas resueltas.
No certifica operaciones futuras nunca incluidas, habilidades reales ni feriados.
"""
from collections import defaultdict

EPS = 1e-5


def auditar_cruces(compromisos, reservas_por_ventana, tol=EPS):
    """Verifica invariancia y compatibilidad temporal global de filas observadas.

    compromisos: {operacion_id: (maquina,inicio,fin,trabajador)}.
    reservas_por_ventana: iterable de dicts con operacion_id, maquina, inicio_h,
      fin_h, trabajador_simulado y ventana. Las observaciones repetidas de una
      reserva entre ventanas deben preservar sus datos. 

    Retorna (resumen, errores); funciona sin solucionador ni acceso al Excel.
    """
    errores = []
    unicas = {}
    observadas = 0
    for fila in reservas_por_ventana:
        observadas += 1
        op = int(fila['operacion_id'])
        dato = (str(fila['maquina']), float(fila['inicio_h']),
                float(fila['fin_h']), str(fila['trabajador_simulado']))
        if dato[2] <= dato[1] + tol:
            errores.append(f'Reserva {op} con intervalo inválido')
        if not dato[3] or dato[3] == 'None':
            errores.append(f'Reserva {op} sin trabajador asignado')
        if op in unicas:
            anterior = unicas[op]
            if (anterior[0] != dato[0] or anterior[3] != dato[3]
                or abs(anterior[1]-dato[1]) > tol
                or abs(anterior[2]-dato[2]) > tol):
                errores.append(f'Reserva externa {op} cambió máquina, horario o trabajador entre ventanas')
        else:
            unicas[op] = dato

    def comprobar_pares(datos, nombre):
        por_m, por_w = defaultdict(list), defaultdict(list)
        for o,(m,s,c,w) in datos.items():
            if c <= s + tol:
                errores.append(f'{nombre} {o} con duración no positiva')
            por_m[m].append((s,c,o))
            if w is not None:
                por_w[w].append((s,c,o))
        for titulo, bloques in (('máquina', por_m), ('trabajador', por_w)):
            for clave, intervalos in bloques.items():
                intervalos.sort()
                for (s1,c1,o1),(s2,c2,o2) in zip(intervalos,intervalos[1:]):
                    if s2 < c1 - tol:
                        errores.append(f'{nombre}: solapamiento {titulo} {clave} ({o1}, {o2})')
    comprobar_pares(unicas, 'Reserva FIFO externa')
    comprobar_pares(compromisos, 'Compromiso MILP')

    cruces_m, cruces_w = 0, 0
    for o,(m,s,c,w) in compromisos.items():
        if o in unicas:
            errores.append(f'Operación {o} figura a la vez como reserva externa y compromiso MILP')
        for oe,(me,se,ce,we) in unicas.items():
            if s < ce-tol and se < c-tol:
                if m == me:
                    cruces_m += 1
                    errores.append(f'Cruce de máquina entre compromiso {o} y reserva {oe}: {m}')
                if w is not None and w == we:
                    cruces_w += 1
                    errores.append(f'Cruce de trabajador entre compromiso {o} y reserva {oe}: {w}')

    # Ordenar y eliminar repeticiones para que el JSON sea reproducible.
    errores = list(dict.fromkeys(errores))
    resumen = dict(
        reservas_observaciones=observadas,
        reservas_externas_unicas=len(unicas),
        compromisos_auditados=len(compromisos),
        cruces_maquina_compromiso_externa=cruces_m,
        cruces_trabajador_compromiso_externa=cruces_w,
        errores=len(errores),
        correcto_en_alcance_exportado=not errores,
        cobertura_anual_certificada=False,
        advertencia='Solo se auditó el conjunto de reservas FIFO EXTERNAS visto en las ventanas; '
                    'no incluye el año completo ni competencias laborales verificadas.')
    return resumen, errores


def verificar_arrastres(previos, en_curso, tol=EPS):
    """Comprueba que las operaciones en curso sigan con su misma identidad.

    `en_curso` contiene asignaciones de la ventana siguiente para esas operaciones.
    No exige reoptimizar un tramo que ya fue comprometido.
    """
    errores=[]
    for o, esperado in previos.items():
        si = en_curso.get(o)
        if si is None:
            errores.append(f'La operación transferida {o} no aparece activa en la nueva ventana')
            continue
        if (si[0] != esperado[0] or si[3] != esperado[3]
                            or abs(si[1]-esperado[1]) > tol
                            or abs(si[2]-esperado[2]) > tol):
            errores.append(f'La operación transferida {o} cambió su asignación')
    return errores
