"""Modelo MILP de (re)programación de máquinas — formulación v2.0 (ver 03_MODELO_MATEMATICO).

Variables
  S_o ≥ 0      inicio de la operación o ∈ O^R (h productivas)            continua
  x_om ∈ {0,1} o se asigna a la unidad m ∈ M_o                            binaria
  y_ab ∈ {0,1} a precede a b si comparten unidad                          binaria
  z_ow ∈ {0,1} o se procesa después de la ventana futura w                 binaria
  k_o ∈ ℤ≥0    tramo continuo en que se procesa o ∈ O^N (no interrumpible) entera
  T_j ≥ 0      tardanza del pedido j (h)                                   continua
  U_j ∈ {0,1}  el pedido j se entrega tarde                                binaria
  g_j ≥ 0, v_j ∈ {0,1}  penalidad diaria con tope (solo regla DIARIA)
  dp_o, dm_o ≥ 0  desviación respecto del inicio vigente S0_o              continuas

Restricciones
  R1  Σ_m x_om = 1                                         asignación única
  R2  S_o ≥ a_m · x_om                                     recurso ocupado o caído al decidir
  R3  S_b ≥ S_a + Σ_m p_am x_am                            precedencia de ruta (a → b)
  R4–R5 disyunción en unidad común (big-M = UB + p_a − lb_b)
  R6  S_o + p_om ≤ a_w + M(1 − x_om) + M z_ow ;  S_o ≥ lb_o + (b_w − lb_o) z_ow     (M = UB + p_om − a_w)
  R7  T_j ≥ C_j − d_j ;  R8  C_j − d_j ≤ M_j U_j ;  R9 g_j ≥ a_j T_j − M v_j, g_j ≥ tope_j v_j
  R10 S_o − dp_o + dm_o = S0_o
  R12 L·k_o ≤ S_o ;  S_o + Σ_m p_om x_om ≤ L·k_o + L      (o ∈ O^N: no cruza refrigerio ni cierre)

Objetivos (jerarquía lexicográfica configurable, ver `fases`)
  f_tard = Σ_j w_j T_j   (h ponderadas)      f_pen = Σ_j P_j U_j  (S/, penalidad ESTIMADA)
  f_dia  = Σ_j g_j       (S/)                f_est = Σ (dp+dm) + β Σ (1 − x_{o,m0})   (h equivalentes)

Cambios respecto de v1.4: se elimina R11 (no contenía variables de programación; ver personal.py); se corrige
el big-M de R6 (antes UB, insuficiente si a_w < p_om); se añade R12; la jerarquía de objetivos es configurable
y por defecto prioriza la tardanza ponderada.
"""
from __future__ import annotations

import math

import numpy as np

from ..solver import INF, LinModel

REGLAS_OBJETIVO = ("TARDANZA_PONDERADA", "PENALIDAD_FIJA", "PENALIDAD_DIARIA_CON_TOPE")


class ModeloMILP:
    def __init__(self, sub, beta=8.0, regla_objetivo="TARDANZA_PONDERADA", estabilidad=True, horas_dia=8.0):
        if regla_objetivo not in REGLAS_OBJETIVO:
            raise ValueError(f"regla_objetivo desconocida: {regla_objetivo}")
        self.sub, self.beta, self.regla = sub, beta, regla_objetivo
        inst = sub.inst
        M = LinModel()
        self.M = M
        free = sub.free
        fs = set(free)
        UB = sub.upper_bound_time()
        self.UB = UB
        self.L = float(getattr(inst, "L_segmento", 0.0) or 0.0)
        self.S, self.x, self.y, self.z, self.k = {}, {}, {}, {}, {}
        self.T, self.U, self.g, self.v, self.dp, self.dm = {}, {}, {}, {}, {}, {}
        self.bloques = {}

        def bloque(n):
            self.bloques[n] = [M.nrow, M.nrow]

        def fin(n):
            self.bloques[n][1] = M.nrow

        for o in free:
            self.S[o] = M.var(f"S[{o}]", lb=sub.lbR[o], ub=UB)
        for o in free:
            for m in sub.eligR[o]:
                self.x[(o, m)] = M.var(f"x[{o},{m}]", 0, 1, integer=True)
        bloque("R1")
        for o in free:
            M.row([(self.x[(o, m)], 1.0) for m in sub.eligR[o]], 1.0, 1.0)
        fin("R1")
        bloque("R2")
        for o in free:
            for m in sub.eligR[o]:
                a = sub.mavail.get(m, sub.t0)
                if a > sub.lbR[o] + 1e-9:
                    M.row([(self.S[o], 1.0), (self.x[(o, m)], -a)], 0.0, INF)
        fin("R2")
        bloque("R3")
        for j, seq in inst.job_ops.items():
            for a, b in zip(seq[:-1], seq[1:]):
                if a in fs and b in fs:
                    M.row([(self.S[b], 1.0), (self.S[a], -1.0)] + [(self.x[(a, m)], -sub.pR[(a, m)]) for m in sub.eligR[a]],
                          0.0, INF)
        fin("R3")
        bloque("R4-R5")
        npairs = 0
        for ia in range(len(free)):
            oa = free[ia]
            ja = inst.ops[oa]["job"]
            Ea = set(sub.eligR[oa])
            for ib in range(ia + 1, len(free)):
                ob = free[ib]
                if inst.ops[ob]["job"] == ja:      # la cadena de precedencia lineal ya las separa
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
        fin("R4-R5")
        bloque("R6")
        for w, (mw, a, b) in enumerate(sub.windows):
            for o in free:
                if mw not in sub.eligR[o] or sub.lbR[o] >= b:
                    continue
                p = sub.pR[(o, mw)]
                Mw = UB + p - a
                if Mw <= 0:          # la ventana empieza después de UB + p: nunca puede cruzarse
                    continue
                z = M.var(f"z[{o},{w}]", 0, 1, integer=True)
                self.z[(o, w)] = z
                # S + p ≤ a + Mw(1 − x) + Mw z   ⇔   S + Mw x − Mw z ≤ a − p + Mw
                M.row([(self.S[o], 1.0), (self.x[(o, mw)], Mw), (z, -Mw)], -INF, a - p + Mw)
                M.row([(self.S[o], 1.0), (z, -(b - sub.lbR[o]))], sub.lbR[o], INF)
        fin("R6")
        bloque("R12")
        if self.L > 0:
            for o in free:
                if inst.ops[o].get("interrumpible", True):
                    continue
                kmin = math.floor((sub.lbR[o] + 1e-9) / self.L)
                kmax = math.ceil(UB / self.L) + 1
                k = M.var(f"k[{o}]", kmin, kmax, integer=True)
                self.k[o] = k
                M.row([(self.S[o], 1.0), (k, -self.L)], 0.0, INF)
                M.row([(self.S[o], 1.0)] + [(self.x[(o, m)], sub.pR[(o, m)]) for m in sub.eligR[o]] + [(k, -self.L)],
                      -INF, self.L)
        fin("R12")
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
        fin("R7-R8")
        bloque("R9")
        if regla_objetivo == "PENALIDAD_DIARIA_CON_TOPE":
            for j in self.jobs_free:
                jb = inst.jobs[j]
                a = jb["pdia"] / horas_dia
                tope = jb.get("tope", 0.10 * jb["valor"])
                self.g[j] = M.var(f"g[{j}]", 0.0, INF)
                self.v[j] = M.var(f"v[{j}]", 0, 1, integer=True)
                Mg = a * (UB + maxp)
                M.row([(self.g[j], 1.0), (self.T[j], -a), (self.v[j], Mg)], 0.0, INF)
                M.row([(self.g[j], 1.0), (self.v[j], -tope)], 0.0, INF)
        fin("R9")
        bloque("R10")
        self.estabilidad = estabilidad and bool(sub.S0)
        if self.estabilidad:
            for o in sub.pending:
                self.dp[o] = M.var(f"dp[{o}]", 0.0, INF)
                self.dm[o] = M.var(f"dm[{o}]", 0.0, INF)
                M.row([(self.S[o], 1.0), (self.dp[o], -1.0), (self.dm[o], 1.0)], sub.S0[o], sub.S0[o])
        fin("R10")

    # ------------------------------------------------------------------ objetivos
    def f_tardanza(self):
        return [(self.T[j], self.sub.inst.jobs[j]["w"]) for j in self.jobs_free]

    def f_penalidad(self):
        return [(self.U[j], self.sub.inst.jobs[j]["P"]) for j in self.jobs_free]

    def f_penalidad_diaria(self):
        return [(self.g[j], 1.0) for j in self.jobs_free]

    def f_estabilidad(self):
        terms = []
        for o in self.sub.pending:
            if o in self.dp:
                terms += [(self.dp[o], 1.0), (self.dm[o], 1.0)]
        for o in self.sub.free:
            m0 = self.sub.m0.get(o)
            if m0 is not None and (o, m0) in self.x:
                terms.append((self.x[(o, m0)], -self.beta))
        return terms

    def f_estabilidad_const(self):
        return self.beta * sum(1 for o in self.sub.free if self.sub.m0.get(o) is not None and (o, self.sub.m0[o]) in self.x)

    def fases(self):
        """[(nombre, términos)] en orden lexicográfico según la regla configurada."""
        if self.regla == "TARDANZA_PONDERADA":
            f = [("P1_tardanza_ponderada", self.f_tardanza()), ("P2_penalidad_estimada", self.f_penalidad())]
        elif self.regla == "PENALIDAD_FIJA":
            f = [("P1_penalidad_estimada", self.f_penalidad()), ("P2_tardanza_ponderada", self.f_tardanza())]
        else:
            f = [("P1_penalidad_diaria_con_tope", self.f_penalidad_diaria()), ("P2_tardanza_ponderada", self.f_tardanza())]
        if self.estabilidad:
            f.append(("P3_estabilidad", self.f_estabilidad()))
        return f

    # ------------------------------------------------------------------ codificación
    def decode(self, xv):
        sol = {}
        for o in self.sub.free:
            m = max(self.sub.eligR[o], key=lambda mm: xv[self.x[(o, mm)]])
            sol[o] = (m, float(xv[self.S[o]]))
        return sol

    def encode(self, sol):
        """Vector completo a partir de {o: (m, S)} (usado como solución de respaldo verificada)."""
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
        for o, k in self.k.items():
            v[k] = math.floor((sol[o][1] + 1e-9) / self.L)
        for j in self.jobs_free:
            last = inst.job_ops[j][-1]
            m, S = sol[last]
            T = max(0.0, S + sub.pR[(last, m)] - inst.jobs[j]["d"])
            v[self.T[j]] = T
            v[self.U[j]] = 1.0 if T > 1e-6 else 0.0
            if j in self.g:
                a = inst.jobs[j]["pdia"] / 8.0
                tope = inst.jobs[j].get("tope", 0.10 * inst.jobs[j]["valor"])
                v[self.v[j]], v[self.g[j]] = (1.0, tope) if a * T > tope else (0.0, a * T)
        for o in self.dp:
            dlt = sol[o][1] - sub.S0[o]
            v[self.dp[o]] = max(0.0, dlt)
            v[self.dm[o]] = max(0.0, -dlt)
        return v

    def tamano(self):
        return dict(variables=self.M.nvar, restricciones=self.M.nrow, binarias=int(sum(self.M.integer)),
                    pares_disyuntivos=self.npairs, ops_libres=len(self.sub.free), pedidos=len(self.jobs_free),
                    ventanas_futuras=len(self.sub.windows), ops_no_interrumpibles=len(self.k),
                    no_ceros=len(self.M.vals))
