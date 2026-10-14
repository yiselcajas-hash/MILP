"""Conversión entre fecha-hora de reloj y horas productivas (eje de tiempo del modelo).

El modelo trabaja en horas productivas acumuladas desde el inicio del calendario: sólo
cuentan los tramos de jornada (por defecto 08:00-12:00 y 13:00-17:00) de los días con
'Productivo efectivo' = 1 en la hoja 07_CALENDARIO. Una operación iniciada antes del
refrigerio o del cierre continúa en el siguiente tramo productivo (S-03 en el Capítulo 3).
"""
from __future__ import annotations
import bisect
import datetime as dt


def _hm(s):
    if isinstance(s, dt.time):
        return s.hour + s.minute / 60 + s.second / 3600
    h, m = str(s).strip().split(":")[:2]
    return int(h) + int(m) / 60


class Calendario:
    def __init__(self, dias_productivos, tramos=(("08:00", "12:00"), ("13:00", "17:00"))):
        """dias_productivos: lista ordenada de (fecha: date, productivo: bool) que cubre el horizonte."""
        self.tramos = [(_hm(a), _hm(b)) for a, b in tramos]
        self.h_dia = sum(b - a for a, b in self.tramos)
        self.fechas = [d for d, _ in dias_productivos]
        self.prod = [bool(p) for _, p in dias_productivos]
        self.base = []          # horas productivas acumuladas al inicio de cada fecha
        acc = 0.0
        for p in self.prod:
            self.base.append(acc)
            acc += self.h_dia if p else 0.0
        self.total = acc
        self.f0 = self.fechas[0]
        self.prod_idx = [i for i, p in enumerate(self.prod) if p]
        self.prod_base = [self.base[i] for i in self.prod_idx]

    # ---- reloj -> horas productivas ----
    def a_horas(self, t: dt.datetime) -> float:
        d = t.date() if isinstance(t, dt.datetime) else t
        i = (d - self.f0).days
        if i < 0:
            return 0.0
        if i >= len(self.fechas):
            return self.total
        h = self.base[i]
        if not self.prod[i] or not isinstance(t, dt.datetime):
            return h
        x = t.hour + t.minute / 60 + t.second / 3600 + t.microsecond / 3.6e9
        for a, b in self.tramos:
            if x >= b:
                h += b - a
            elif x > a:
                h += x - a
        return h

    def fin_de_dia(self, d: dt.date) -> float:
        """Horas productivas al cierre del día d (17:00); si d no es productivo, cierre del último día productivo anterior."""
        i = (d - self.f0).days
        if i < 0:
            return 0.0
        if i >= len(self.fechas):
            return self.total
        return self.base[i] + (self.h_dia if self.prod[i] else 0.0)

    # ---- horas productivas -> reloj ----
    def a_fecha(self, h: float, extremo="inicio") -> dt.datetime:
        """extremo='inicio' devuelve el primer instante de reloj con ese valor (p. ej. 13:00 en vez de 12:00);
        extremo='fin' devuelve el último (p. ej. 12:00 o 17:00)."""
        h = max(0.0, min(h, self.total))
        k = bisect.bisect_right(self.prod_base, h + 1e-9) - 1
        if extremo == "fin" and k > 0 and abs(h - self.prod_base[k]) < 1e-9:
            k -= 1
        k = max(k, 0)
        i = self.prod_idx[k]
        r = h - self.prod_base[k]
        d = self.fechas[i]
        for a, b in self.tramos:
            L = b - a
            if r < L - 1e-12 or (extremo == "fin" and r <= L + 1e-9):
                x = a + max(0.0, r)
                break
            r -= L
        else:
            x = self.tramos[-1][1]
        secs = round(x * 3600, 3)
        return dt.datetime.combine(d, dt.time()) + dt.timedelta(seconds=secs)

    def dias_habiles(self, horas: float) -> float:
        return horas / self.h_dia

    # ---- continuidad (operaciones no interrumpibles, R12)
    def longitud_segmento(self, regla: str = "TRAMO") -> float:
        """Longitud L del tramo productivo continuo en el eje de horas productivas.

        TRAMO: entre pausas (refrigerio o cierre); exige tramos de igual duración para que sus límites sean
        múltiplos de L. JORNADA: el día productivo completo (L = h_dia). Los límites de segmento están en
        k·L porque cada día productivo aporta exactamente h_dia = n·L horas al eje.
        """
        largos = [round(b - a, 9) for a, b in self.tramos]
        if regla == "TRAMO" and len(set(largos)) == 1:
            return largos[0]
        return self.h_dia

    @staticmethod
    def ajustar_no_partible(S: float, p: float, L: float, eps: float = 1e-9) -> float:
        """Menor inicio ≥ S tal que [S, S + p) queda dentro de un único segmento [kL, (k+1)L)."""
        if p > L + eps:
            raise ValueError(f"Operación no interrumpible de {p:.3f} h excede el tramo continuo de {L:.3f} h")
        k = int((S + eps) // L)
        if S + p > (k + 1) * L + eps:
            return (k + 1) * L
        return S

    def indice_dia(self, h: float) -> int:
        """Índice de día productivo (0, 1, ...) al que pertenece la hora productiva h (intervalo [k·h_dia, (k+1)·h_dia))."""
        return int((h + 1e-9) // self.h_dia)

    def fecha_de_dia(self, k: int):
        """Fecha del k-ésimo día productivo (o None si excede el calendario)."""
        return self.fechas[self.prod_idx[k]] if 0 <= k < len(self.prod_idx) else None
