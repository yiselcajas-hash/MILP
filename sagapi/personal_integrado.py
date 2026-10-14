"""MILP piloto con asignación trabajador–operación realmente integrada.

Escenario de competencias SIMULADAS (25 perfiles) y supuesto experimental
1 trabajador por operación activa, sin relevo dentro de esa operación.
Los tiempos usan horas productivas; no representan horario contractual real.

La combinación de variables x[o,m], q[o,w] y precedencia r[a,b] impide que dos
operaciones asignadas al mismo trabajador se solapen, aunque usen máquinas
distintas. Las operaciones en curso y fijas consumen personal hasta finalizar.
No representa tareas indirectas, ausencia, supervisión ni competencias reales.
"""
from __future__ import annotations

from collections import defaultdict
from .modelo import ModeloMILP
from .solver import INF, validar_vector


class LimitePiloto(ValueError):
    pass


class ModeloPersonalOperaciones(ModeloMILP):
    def __init__(self, sub, max_operaciones=24, personal_fijo=None, **kwargs):
        if len(sub.free) > max_operaciones:
            raise LimitePiloto(
                f"Piloto limitado a {max_operaciones} operaciones libres; recibido {len(sub.free)}. "
                "Reduce --pedidos o valida escalabilidad antes de ampliar.")
        super().__init__(sub, reservar_personal=False, **kwargs)
        M, inst = self.M, sub.inst
        habilidades = getattr(inst.datos, 'habilidades', None) or {}
        if not habilidades:
            raise ValueError('La matriz de habilidades está vacía. No se asignarán competencias implícitas.')
        self.habilidades = habilidades
        self.personal_fijo = personal_fijo or {}
        self.q = {}
        self.qf = {}
        self.yp = {}
        self.operarios_posibles = {}
        # Un trabajador asignado a cada operación libre, condicionado a la máquina elegida.
        ini = M.nrow
        for o in sub.free:
            opciones = [w for w in sorted(habilidades)
                        if set(sub.eligR[o]) & set(habilidades[w])]
            self.operarios_posibles[o] = opciones
            if not opciones:
                raise ValueError(f'Operación {o}: no tiene personal habilitado en el escenario simulado')
            for w in opciones:
                self.q[(o, w)] = M.var(f'q_trabajador[{o},{w}]', 0, 1, integer=True)
                compatibles = [(self.x[(o, m)], -1) for m in sub.eligR[o]
                               if m in habilidades[w]]
                M.row([(self.q[(o, w)], 1)] + compatibles, -INF, 0)
            M.row([(self.q[(o, w)], 1) for w in opciones], 1, 1)
        self.bloques['R11_TRABAJADOR_OPERACION'] = [ini, M.nrow]

        # Operaciones fijadas en ejecución en t0 también ocupan trabajadores.
        ini = M.nrow
        self.fijas_activas = sorted(o for o, (m, s, c) in sub.fixed.items()
                                    if s < sub.t0 + 1e-7 and c > sub.t0 + 1e-7)
        self.externas_activas = sorted(sub.externas_activas)
        self.ocupadas_en_t0 = {o: sub.fixed[o] for o in self.fijas_activas}
        self.ocupadas_en_t0.update(sub.externas_activas)
        for o in sorted(self.ocupadas_en_t0):
            m, s, c = self.ocupadas_en_t0[o]
            opciones = sorted(w for w, h in habilidades.items() if m in h)
            if not opciones:
                raise ValueError(f'Operación fija {o}: máquina {m} sin trabajador habilitado')
            for w in opciones:
                self.qf[(o, w)] = M.var(f'q_fijo[{o},{w}]', 0, 1, integer=True)
            M.row([(self.qf[(o, w)], 1) for w in opciones], 1, 1)
            if o in self.personal_fijo:
                elegido = self.personal_fijo[o]
                if elegido not in opciones:
                    raise ValueError(f'Trabajador comprometido {elegido} no habilitado para {o} en {m}')
                M.row([(self.qf[(o, elegido)], 1)], 1, 1)
        ocupadas = sorted(self.ocupadas_en_t0)
        for i, oa in enumerate(ocupadas):
            ma, sa, ca = self.ocupadas_en_t0[oa]
            for ob in ocupadas[i+1:]:
                mb, sb, cb = self.ocupadas_en_t0[ob]
                if sa < cb - 1e-7 and sb < ca - 1e-7:
                    for w in habilidades:
                        if (oa, w) in self.qf and (ob, w) in self.qf:
                            M.row([(self.qf[(oa, w)], 1), (self.qf[(ob, w)], 1)], -INF, 1)
        self.bloques['R12_PERSONAL_FIJO'] = [ini, M.nrow]

        # Operaciones de pedidos distintos podrían coincidir; la disyunción
        # afecta a cada trabajador habilitado para ambas. Para un mismo pedido,
        # las precedencias de ruta ya impiden el solape.
        ini = M.nrow
        maxp = max(sub.pR.values()) if sub.pR else 0.0
        bigM = self.UB + maxp + 1.0
        self.bigM_personal = bigM
        for ia, oa in enumerate(sub.free):
            ea = set(self.operarios_posibles[oa])
            for ob in sub.free[ia+1:]:
                if inst.ops[oa]['job'] == inst.ops[ob]['job']:
                    continue
                comunes = ea & set(self.operarios_posibles[ob])
                if not comunes:
                    continue
                y = self.y.get((oa, ob))
                if y is None:
                    y = M.var(f'r_trabajador[{oa},{ob}]', 0, 1, integer=True)
                self.yp[(oa, ob)] = y
                # Las p(o,m) dependen de la máquina seleccionada.
                pa = [(self.x[(oa, m)], -sub.pR[(oa, m)]) for m in sub.eligR[oa]]
                pb = [(self.x[(ob, m)], -sub.pR[(ob, m)]) for m in sub.eligR[ob]]
                for w in sorted(comunes):
                    qa, qb = self.q[(oa, w)], self.q[(ob, w)]
                    # y=1 => oa precede a ob si comparten trabajador.
                    M.row([(self.S[ob], 1), (self.S[oa], -1)] + pa +
                          [(qa, -bigM), (qb, -bigM), (y, -bigM)], -3*bigM, INF)
                    # y=0 => ob precede a oa.
                    M.row([(self.S[oa], 1), (self.S[ob], -1)] + pb +
                          [(qa, -bigM), (qb, -bigM), (y, bigM)], -2*bigM, INF)
        self.bloques['R13_SIN_SOLAPAMIENTO_PERSONAL'] = [ini, M.nrow]

        ini = M.nrow
        for of in sorted(self.ocupadas_en_t0):
            mf, sf, cf = self.ocupadas_en_t0[of]
            for o in sub.free:
                # Free sólo inicia desde t0. Si comparte operario con la fija,
                # debe esperar su finalización, incluso si va a otra máquina.
                for w in self.operarios_posibles[o]:
                    if (of, w) in self.qf:
                        M.row([(self.S[o], 1), (self.q[(o, w)], -bigM),
                               (self.qf[(of, w)], -bigM)], cf - 2*bigM, INF)
        self.bloques['R14_PERSONAL_EN_CURSO'] = [ini, M.nrow]

        # (R15) Trabajadores ocupados en operaciones FUTURAS excluidas y
        # congeladas por el escenario de referencia. Cada disyunción se activa
        # solamente si se elige a ese trabajador para la operación libre.
        ini = M.nrow
        self.yp_externa = {}
        reservas = getattr(sub, 'trabajadores_externos', {})
        por_trabajador = defaultdict(list)
        for oe, (mm, a, b, w) in reservas.items():
            por_trabajador[w].append((a,b,oe))
        # Operaciones en curso no pueden elegir a alguien ya comprometido
        # con una reserva futura que empiece antes de que finalice el trabajo.
        for of,(mf,sf,cf) in self.ocupadas_en_t0.items():
            for w in habilidades:
                if (of,w) in self.qf and any(sf < b-1e-7 and a < cf-1e-7
                                             for a,b,oe in por_trabajador[w]):
                    M.row([(self.qf[(of,w)],1.0)],-INF,0.0)
        for o in sub.free:
            for w in self.operarios_posibles[o]:
                if not por_trabajador[w]:
                    continue
                q = self.q[(o,w)]
                pterms = [(self.x[(o,m)], sub.pR[(o,m)]) for m in sub.eligR[o]]
                for a,b,oe in por_trabajador[w]:
                    if b <= sub.lbR[o]+1e-7:
                        continue
                    z = M.var(f'z_externo_personal[{o},{oe},{w}]',0,1,integer=True)
                    self.yp_externa[(o,oe,w)] = z
                    # z=0: la libre termina antes del externo (S+p<=a).
                    # z=1: la libre comienza después del externo (S>=b).
                    M.row([(self.S[o],1.0)]+pterms+[(q,bigM),(z,-bigM)],
                          -INF,a+bigM)
                    M.row([(self.S[o],1.0),(q,-bigM),(z,-bigM)],
                          b-2*bigM,INF)
        self.bloques['R15_RESERVAS_FUTURAS_PERSONAL']=[ini,M.nrow]

    def tamano(self):
        t = super().tamano()
        t.update(trabajador_operacion_binarias=len(self.q), trabajadores_fijos_binarias=len(self.qf),
                 pares_potencial_conflicto=len(self.yp), personal_integrado=True,
                 externas_activas_fijadas=len(self.externas_activas),
                 disyunciones_personal_externo=len(getattr(self,'yp_externa',{})),
                 operaciones_externas_congeladas=len(getattr(self.sub,'trabajadores_externos',{})))
        return t

    def asignaciones(self, xv):
        if xv is None:
            return {}
        d = {}
        for o in self.sub.free:
            w = max(self.operarios_posibles[o], key=lambda x: xv[self.q[(o, x)]])
            if xv[self.q[(o, w)]] > .5:
                d[o] = w
        for of in sorted(self.ocupadas_en_t0):
            ww = [w for (o, w) in self.qf if o == of]
            if ww:
                w = max(ww, key=lambda x: xv[self.qf[(of, x)]])
                if xv[self.qf[(of, w)]] > .5:
                    d[of] = w
        return d

    def verificar_personal(self, xv, tol=1e-5):
        errores = list(validar_vector(self.M, xv, tol=tol))
        if xv is None:
            return errores
        assigned = self.asignaciones(xv)
        from .verificacion import verificar
        sol = self.decode(xv)
        errores.extend(verificar(self.sub, sol, tol=tol))
        porw = defaultdict(list)
        for o, w in assigned.items():
            if o in sol:
                m, s = sol[o]
                c = s + self.sub.pR[(o, m)]
            else:
                m, s, c = self.ocupadas_en_t0[o]
            if m not in self.habilidades[w]:
                errores.append(f'{o}: trabajador {w} no habilitado para {m}')
            porw[w].append((s, c, o))
        # Máquina ocupada externamente no puede solaparse con máquina libre o
        # fijada del subconjunto. No basta revisar la asignación de personal.
        por_maquina = defaultdict(list)
        for o in assigned:
            if o in sol:
                m, s = sol[o]; c = s + self.sub.pR[(o,m)]
            else:
                m, s, c = self.ocupadas_en_t0[o]
            por_maquina[m].append((s,c,o))
        for m, rows in por_maquina.items():
            rows.sort()
            for (s1,c1,o1),(s2,c2,o2) in zip(rows,rows[1:]):
                if s2 < c1-tol:
                    errores.append(f'Solapamiento máquina {m} entre {o1} y {o2}')
        for w, rows in porw.items():
            rows.sort()
            for (s1, c1, o1), (s2, c2, o2) in zip(rows, rows[1:]):
                if s2 < c1 - tol:
                    errores.append(f'Solapamiento de trabajador {w} entre {o1} y {o2}')
        # Verificador independiente sobre reservas futuras externas.
        for oe,(me,se,ce,we) in getattr(self.sub,'trabajadores_externos',{}).items():
            for o,ww in assigned.items():
                if o in sol:
                    mo,so = sol[o]; co=so+self.sub.pR[(o,mo)]
                else:
                    mo,so,co=self.ocupadas_en_t0[o]
                if so < ce-tol and se < co-tol:
                    if mo==me:
                        errores.append(f'Cruce máquina con reserva externa {o}/{oe}')
                    if ww==we:
                        errores.append(f'Cruce trabajador con reserva externa {o}/{oe}: {ww}')
        if len(assigned) != len(self.sub.free) + len(self.ocupadas_en_t0):
            errores.append('Faltan asignaciones trabajador–operación')
        return errores
