"""Modelo MILP de (re)programación — formulación del Capítulo 3, ecuaciones (R1)–(R10).

Variables
  S_o   inicio de la operación o ∈ O^R                         (continua, h productivas)
  x_om  1 si o se asigna a la máquina m ∈ M_o                   (binaria)
  y_ab  1 si a precede a b cuando comparten máquina             (binaria)
  z_ow  1 si o se procesa después de la ventana futura w        (binaria)
  T_j   tardanza del pedido j                                   (continua ≥ 0)
  U_j   1 si el pedido j se entrega tarde                       (binaria)
  g_j, v_j  penalidad con tope (sólo regla DIARIA_CON_TOPE)     (continua ≥ 0, binaria)
  dp_o, dm_o  desviación positiva/negativa respecto del inicio vigente S0_o (continuas ≥ 0)

Objetivos
  f1  = Σ_j P_j U_j                      (penalidad económica, S/; regla FIJA)
        Σ_j g_j                          (regla DIARIA_CON_TOPE, sensibilidad)
  f1b = Σ_j w_j T_j                      (tardanza ponderada, h — desempate de f1)
  f2  = Σ_{o∈O^P} (dp_o + dm_o) + β Σ_{o∈O^R} (1 − x_{o,m0(o)})   (inestabilidad, h equivalentes)
"""
from __future__ import annotations
import numpy as np
from .solver import LinModel, INF
from .personal import emparejar


class ModeloMILP:
    def __init__(self, sub, beta=8.0, regla_pen="FIJA", estabilidad=True, horas_dia=8.0, reservar_personal=True):
        self.sub = sub
        self.beta = beta
        self.regla_pen = regla_pen
        inst = sub.inst
        M = LinModel()
        self.M = M
        free = sub.free
        fs = set(free)
        UB = sub.upper_bound_time()
        self.UB = UB
        self.S, self.x, self.y, self.z, self.T, self.U, self.g, self.v, self.dp, self.dm = ({} for _ in range(10))
        self.bloques = {}

        def bloque(nombre):
            self.bloques.setdefault(nombre, [M.nrow, M.nrow])

        def fin_bloque(nombre):
            self.bloques[nombre][1] = M.nrow

        # (R0) dominios: S_o ∈ [lb_o, UB]; lb_o = max(r_j, t0, fin del predecesor fijo)
        for o in free:
            self.S[o] = M.var(f"S[{o}]", lb=sub.lbR[o], ub=UB)
        for o in free:
            for m in sub.eligR[o]:
                self.x[(o, m)] = M.var(f"x[{o},{m}]", 0, 1, integer=True)
        # (R1) asignación única
        bloque("R1")
        for o in free:
            M.row([(self.x[(o, m)], 1.0) for m in sub.eligR[o]], 1.0, 1.0)
        fin_bloque("R1")
        # (R2) disponibilidad de máquina: ops fijas en curso y avería en curso  S_o ≥ a_m x_om
        bloque("R2")
        for o in free:
            for m in sub.eligR[o]:
                a = sub.mavail.get(m, sub.t0)
                if a > sub.lbR[o] + 1e-9:
                    M.row([(self.S[o], 1.0), (self.x[(o, m)], -a)], 0.0, INF)
        fin_bloque("R2")
        # (R3) precedencia de ruta
        bloque("R3")
        for j, seq in inst.job_ops.items():
            for a, b in zip(seq[:-1], seq[1:]):
                if a in fs and b in fs:
                    terms = [(self.S[b], 1.0), (self.S[a], -1.0)]
                    terms += [(self.x[(a, m)], -sub.pR[(a, m)]) for m in sub.eligR[a]]
                    M.row(terms, 0.0, INF)
        fin_bloque("R3")
        # (R4)-(R5) no solapamiento disyuntivo en máquinas compartidas
        bloque("R4-R5")
        npairs = 0
        for ia in range(len(free)):
            oa = free[ia]
            ja = inst.ops[oa]["job"]
            Ea = set(sub.eligR[oa])
            for ib in range(ia + 1, len(free)):
                ob = free[ib]
                if inst.ops[ob]["job"] == ja:
                    continue
                common = Ea.intersection(sub.eligR[ob])
                if not common:
                    continue
                y = M.var(f"y[{oa},{ob}]", 0, 1, integer=True)
                self.y[(oa, ob)] = y
                npairs += 1
                for m in sorted(common):
                    pa, pb = sub.pR[(oa, m)], sub.pR[(ob, m)]
                    Mab = UB + pa - sub.lbR[ob]
                    Mba = UB + pb - sub.lbR[oa]
                    M.row([(self.S[ob], 1.0), (self.S[oa], -1.0), (self.x[(oa, m)], -Mab), (self.x[(ob, m)], -Mab),
                           (y, -Mab)], pa - 3 * Mab, INF)
                    M.row([(self.S[oa], 1.0), (self.S[ob], -1.0), (self.x[(oa, m)], -Mba), (self.x[(ob, m)], -Mba),
                           (y, Mba)], pb - 2 * Mba, INF)
        self.npairs = npairs
        fin_bloque("R4-R5")
        # (R6) ventanas futuras de indisponibilidad (mantenimiento programado o avería anunciada)
        bloque("R6")
        for w, (mw, a, b) in enumerate(sub.windows):
            for o in free:
                if mw not in sub.eligR[o]:
                    continue
                if sub.lbR[o] >= b:
                    continue
                z = M.var(f"z[{o},{w}]", 0, 1, integer=True)
                self.z[(o, w)] = z
                p = sub.pR[(o, mw)]
                # (R6a) S_o + p_om ≤ a_w + UB(1 − x_om) + UB z_ow
                M.row([(self.S[o], 1.0), (self.x[(o, mw)], UB), (z, -UB)], -INF, a - p + UB)
                # (R6b) S_o ≥ lb_o + (b_w − lb_o) z_ow
                M.row([(self.S[o], 1.0), (z, -(b - sub.lbR[o]))], sub.lbR[o], INF)
        fin_bloque("R6")
        # (R7) tardanza y (R8) pedido atrasado
        bloque("R7-R8")
        self.jobs_free = sorted({inst.ops[o]["job"] for o in free})
        maxp = max(sub.pR.values()) if sub.pR else 0.0
        for j in self.jobs_free:
            last = inst.job_ops[j][-1]
            dj = inst.jobs[j]["d"]
            self.T[j] = M.var(f"T[{j}]", 0.0, INF)
            self.U[j] = M.var(f"U[{j}]", 0, 1, integer=True)
            Cterms = [(self.S[last], 1.0)] + [(self.x[(last, m)], sub.pR[(last, m)]) for m in sub.eligR[last]]
            M.row([(self.T[j], 1.0)] + [(v, -c) for v, c in Cterms], -dj, INF)
            Mj = max(1.0, UB + maxp - dj)
            M.row(Cterms + [(self.U[j], -Mj)], -INF, dj)
        fin_bloque("R7-R8")
        # (R9) penalidad diaria con tope (sólo análisis de sensibilidad)
        bloque("R9")
        if regla_pen == "DIARIA_CON_TOPE":
            for j in self.jobs_free:
                jb = inst.jobs[j]
                a = jb["pdia"] / horas_dia
                tope = 0.10 * jb["valor"]
                self.g[j] = M.var(f"g[{j}]", 0.0, INF)
                self.v[j] = M.var(f"v[{j}]", 0, 1, integer=True)
                Mg = a * (UB + maxp)
                M.row([(self.g[j], 1.0), (self.T[j], -a), (self.v[j], Mg)], 0.0, INF)
                M.row([(self.g[j], 1.0), (self.v[j], -tope)], 0.0, INF)
        fin_bloque("R9")
        # (R10) desviación respecto del programa vigente
        bloque("R10")
        self.estabilidad = estabilidad and bool(sub.S0)
        if self.estabilidad:
            for o in sub.pending:
                self.dp[o] = M.var(f"dp[{o}]", 0.0, INF)
                self.dm[o] = M.var(f"dm[{o}]", 0.0, INF)
                M.row([(self.S[o], 1.0), (self.dp[o], -1.0), (self.dm[o], 1.0)], sub.S0[o], sub.S0[o])
        fin_bloque("R10")
        # (R11) cobertura de personal capacitado por recurso — escenario conservador.
        # Una persona distinta por máquina potencialmente operable durante este subproblema.
        # La reasignación de personas puede cambiar en cada decisión reactiva. No modela relevos
        # dentro de una misma resolución; no se presenta como rotación intraturno óptima.
        self.aw = {}
        self.maquinas_dotacion = []
        habilidades = getattr(inst.datos, "habilidades", None) or {}
        bloque("R11_PERSONAL")
        if habilidades and reservar_personal:
            self.maquinas_dotacion = sorted({m for o in free for m in sub.eligR[o]} |
                                                {m for _, (m, _, _) in sub.fixed.items()})
            for m in self.maquinas_dotacion:
                for w in sorted(habilidades):
                    if m in habilidades[w]:
                        self.aw[(m, w)] = M.var(f"a_personal[{m},{w}]", 0, 1, integer=True)
                # La disponibilidad de un recurso no justifica asignarle un trabajador no habilitado.
                M.row([(var, 1.0) for (mm, w), var in self.aw.items() if mm == m], 1.0, 1.0)
            for w in sorted(habilidades):
                M.row([(var, 1.0) for (m, ww), var in self.aw.items() if ww == w], -INF, 1.0)
        fin_bloque("R11_PERSONAL")
        # constantes de pedidos terminados (no afectan la optimización; se suman al reportar)
        self.f1_const = 0.0

    # ------------------------------------------------------------------ objetivos
    def f1_terms(self):
        inst = self.sub.inst
        if self.regla_pen == "DIARIA_CON_TOPE":
            return [(self.g[j], 1.0) for j in self.jobs_free]
        return [(self.U[j], inst.jobs[j]["P"]) for j in self.jobs_free]

    def f1b_terms(self):
        inst = self.sub.inst
        return [(self.T[j], inst.jobs[j]["w"]) for j in self.jobs_free]

    def f2_terms(self):
        terms = []
        for o in self.sub.pending:
            if o in self.dp:
                terms += [(self.dp[o], 1.0), (self.dm[o], 1.0)]
        for o in self.sub.free:
            m0 = self.sub.m0.get(o)
            if m0 is not None and (o, m0) in self.x:
                terms.append((self.x[(o, m0)], -self.beta))
        return terms

    def f2_const(self):
        return self.beta * sum(1 for o in self.sub.free if self.sub.m0.get(o) is not None and (o, self.sub.m0[o]) in self.x)

    def sumC_terms(self):
        return [(self.S[o], 1.0) for o in self.sub.free]

    # ------------------------------------------------------------------ codificación
    def decode(self, xv):
        sol = {}
        for o in self.sub.free:
            m = max(self.sub.eligR[o], key=lambda mm: xv[self.x[(o, mm)]])
            sol[o] = (m, float(xv[self.S[o]]))
        return sol

    def encode(self, sol):
        """Vector factible completo a partir de {o: (m, S)} (arranque en caliente)."""
        sub, inst = self.sub, self.sub.inst
        v = np.zeros(self.M.nvar)
        for o, (m, S) in sol.items():
            v[self.S[o]] = S
            for mm in sub.eligR[o]:
                v[self.x[(o, mm)]] = 1.0 if mm == m else 0.0
        for (oa, ob), y in self.y.items():
            v[y] = 1.0 if sol[oa][1] <= sol[ob][1] else 0.0
        for (o, w), z in self.z.items():
            mw, a, b = self.sub.windows[w]
            v[z] = 1.0 if sol[o][1] >= b - 1e-9 else 0.0
        for j in self.jobs_free:
            last = inst.job_ops[j][-1]
            m, S = sol[last]
            C = S + sub.pR[(last, m)]
            T = max(0.0, C - inst.jobs[j]["d"])
            v[self.T[j]] = T
            v[self.U[j]] = 1.0 if T > 1e-6 else 0.0          # misma tolerancia que el verificador
            if j in self.g:
                a = inst.jobs[j]["pdia"] / 8.0
                tope = 0.10 * inst.jobs[j]["valor"]
                if a * T > tope:
                    v[self.v[j]] = 1.0; v[self.g[j]] = tope
                else:
                    v[self.v[j]] = 0.0; v[self.g[j]] = a * T
        if self.aw:
            m2w = emparejar(self.maquinas_dotacion, getattr(inst.datos, "habilidades", {}))
            if m2w is not None:
                for m, w in m2w.items():
                    v[self.aw[(m, w)]] = 1.0
        for o in self.dp:
            dlt = sol[o][1] - sub.S0[o]
            v[self.dp[o]] = max(0.0, dlt)
            v[self.dm[o]] = max(0.0, -dlt)
        return v

    def tamano(self):
        return dict(variables=self.M.nvar, restricciones=self.M.nrow, binarias=int(sum(self.M.integer)),
                    pares_disyuntivos=self.npairs, ops_libres=len(self.sub.free), pedidos=len(self.jobs_free),
                    ventanas_futuras=len(self.sub.windows), asignaciones_personal=len(self.aw),
                    recursos_con_reserva=len(self.maquinas_dotacion))
