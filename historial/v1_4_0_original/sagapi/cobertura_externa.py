"""Cobertura conservadora de operaciones *en curso* de otros pedidos en t0.

No congela ni optimiza las operaciones FUTURAS de pedidos excluidos. Esta diferencia
es importante para no confundir un piloto local con programación anual verificable.
"""
from __future__ import annotations

from . import estado

EPS = 1e-6


class PedidoExternoInterrumpido(ValueError):
    pass


def preparar_con_cobertura(datos, inst, base, t0, seleccion, ventanas, politica="A", auto_incluir=True):
    """Devuelve subproblema y metadatos de alcance para el piloto integrado.

    Toda operación ajena en proceso en t0 se debe atender de una de dos formas:
    - si opera sobre una máquina que falla en t0, se incorpora el PEDIDO completo
      a la optimización (una operación interrumpida no puede quedar congelada);
    - si opera sobre máquina sana, se congela temporalmente hasta su finalización,
      con capacidad de máquina y un trabajador integrado en el MILP.
    """
    seleccion = list(dict.fromkeys(seleccion))
    if not seleccion:
        raise ValueError('No hay pedidos seleccionados')
    falls = {m for (m,a,b) in ventanas if a <= t0 + EPS and b > t0 + EPS}
    auto = []
    while True:
        externos_activos = {o: abc for o, abc in base.items()
                            if inst.ops[o]['job'] not in seleccion
                            and abc[1] < t0 - EPS and abc[2] > t0 + EPS}
        afectados = sorted({inst.ops[o]['job'] for o,(m,s,c) in externos_activos.items() if m in falls})
        if not afectados:
            break
        if not auto_incluir:
            raise PedidoExternoInterrumpido(
                f'Pedido(s) ajeno(s) {afectados} en máquinas averiadas en t0; '
                'la versión 1.3.0 los omitía. Habilita la inclusión automática.')
        for j in afectados:
            if j not in seleccion:
                seleccion.append(j)
                auto.append(j)
    sub = estado.particionar(datos, inst, base, t0, seleccion, ventanas, politica)
    # Las únicas operaciones externas que podemos congelar con seguridad son las
    # que están físicamente en marcha sobre una máquina sana al decidir en t0.
    sub.externas_activas = dict(externos_activos)
    for _, (m, s, c) in externos_activos.items():
        sub.mavail[m] = max(sub.mavail.get(m,t0),c)
    externas_pendientes = [o for o,(m,s,c) in base.items()
                           if inst.ops[o]['job'] not in seleccion and s >= t0 - EPS]
    info = {
        'pedidos_inicialmente_solicitados': len(seleccion)-len(auto),
        'pedidos_autoincluidos_por_falla': [inst.jobs[j]['id'] for j in auto],
        'pedidos_finalmente_incluidos': [inst.jobs[j]['id'] for j in seleccion],
        'externas_activas_fijadas': len(externos_activos),
        'externas_futuras_no_integradas': len(externas_pendientes),
        'cobertura_global_anual': False,
        'tipo_cobertura': 'PEDIDOS_SELECCIONADOS_MAS_EXTERNAS_ACTIVAS_EN_T0',
    }
    return sub, info


class CoberturaFuturaImposible(ValueError):
    """La reserva futura no admite una asignación laboral estática simulada."""


def preparar_reservas_futuras(sub, base, horizonte_h=96.0, asignaciones_previas=None):
    """Protege el programa de referencia EXTERNO en un horizonte rodante.

    Las operaciones futuras de pedidos excluidos se mantienen como compromisos
    HIPOTÉTICOS de máquina y trabajador (skills simuladas). Sus horarios no son
    decisiones del MILP. Las operaciones de otros pedidos que siguen ejecutándose
    en t0 ya se gestionan por ``preparar_con_cobertura``.

    Este modo NO certifica un programa anual, pues congela un plan de referencia
    que puede ser incompatible con la avería y excluye operaciones posteriores.
    """
    if horizonte_h <= 0:
        raise ValueError('El horizonte de protección externa debe ser positivo')
    inst = sub.inst
    t0 = sub.t0
    limite = t0 + float(horizonte_h)
    jobs = set(sub.jobs)
    futuras = sorted(((o, m, s, c) for o,(m,s,c) in base.items()
                      if inst.ops[o]['job'] not in jobs and s >= t0-1e-6),
                     key=lambda z:(z[2],z[0]))
    seleccionadas = [(o,m,s,c) for o,m,s,c in futuras if s < limite-1e-6]
    habilidades = inst.datos.habilidades
    if not habilidades:
        raise CoberturaFuturaImposible('Matriz de habilidades simuladas ausente')

    # Asignación determinista de una persona POR operación futura, sin relevos.
    # Preferir personal ya asignado previamente a esa máquina reduce el uso
    # artificial de trabajadores diferentes y deja reservas auditables.
    ocupacion = {w:[] for w in habilidades}
    reservas = {}
    asignaciones_previas = asignaciones_previas or {}
    for o,m,s,c in seleccionadas:
        compatibles = [w for w in sorted(habilidades)
                       if m in habilidades[w]
                       and all(s >= fin-1e-6 or c <= ini+1e-6
                               for ini,fin,mm in ocupacion[w])]
        if not compatibles:
            raise CoberturaFuturaImposible(
                f'No se puede reservar trabajador habilitado para operación externa {o} ({m}) '
                f'en [{s:.3f},{c:.3f}]; el plan de referencia podría ser inviable.')
        if o in asignaciones_previas:
            w = asignaciones_previas[o]
            if w not in compatibles:
                raise CoberturaFuturaImposible(
                    f'Operación externa {o} no puede mantener su trabajador {w} previo')
        else:
            w = min(compatibles,
                    key=lambda x:(-sum(mm==m for _,_,mm in ocupacion[x]),
                                  -len(ocupacion[x]),x))
        reservas[o] = (m,s,c,w)
        ocupacion[w].append((s,c,m))

    # El modelo preexistente ya tiene R6 para períodos prohibidos de máquina.
    # Conservamos etiquetas de los intervalos originales para auditoría.
    sub.ventanas_maquina_externas = [(o,m,s,c) for o,m,s,c in seleccionadas]
    sub.trabajadores_externos = reservas
    sub.windows.extend((m,s,c) for o,m,s,c in seleccionadas)

    # La avería puede hacer inviable el horario externo congelado. No se
    # reconcilia automáticamente: se informa como inconsistencia de alcance.
    cruces_falla = []
    for o,m,s,c in seleccionadas:
        for mm, a,b in sub.all_windows:
            if m==mm and s < b-1e-6 and a < c-1e-6:
                cruces_falla.append((o,m,s,c,a,b))
    info = dict(
        horizonte_protegido_h=float(horizonte_h),
        fin_horizonte_protegido_h=limite,
        operaciones_externas_congeladas=len(seleccionadas),
        operaciones_externas_futuras_sin_proteger=len(futuras)-len(seleccionadas),
        reservas_trabajador_distintas=len({w for m,s,c,w in reservas.values()}),
        cruces_reservas_con_averia=len(cruces_falla),
        muestra_reservas_con_averia=[list(row) for row in cruces_falla[:10]],
        es_programa_global_factible=False,
        alcance='RESERVAS_FIJAS_DE_REFERENCIA_SOLO_HORIZONTE_RODANTE',
        advertencia='Se congelan operaciones externas de referencia; no se reoptimizan y '
                    'el resto del horizonte no queda protegido; las habilidades son simuladas.',
    )
    return info
