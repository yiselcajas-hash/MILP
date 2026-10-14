"""Registro de problemas de calidad de datos (ERROR bloquea la optimización; ADVERTENCIA se informa)."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass
class Problema:
    codigo: str
    severidad: str          # ERROR | ADVERTENCIA | INFO
    hoja: str
    fila: int | None
    columna: str | None
    mensaje: str


@dataclass
class InformeCalidad:
    problemas: list = field(default_factory=list)

    def _add(self, sev, codigo, hoja, fila, columna, mensaje):
        self.problemas.append(Problema(codigo, sev, hoja, fila, columna, mensaje))

    def error(self, codigo, hoja, fila, columna, mensaje):
        self._add("ERROR", codigo, hoja, fila, columna, mensaje)

    def advertencia(self, codigo, hoja, fila, columna, mensaje):
        self._add("ADVERTENCIA", codigo, hoja, fila, columna, mensaje)

    def info(self, codigo, hoja, fila, columna, mensaje):
        self._add("INFO", codigo, hoja, fila, columna, mensaje)

    @property
    def errores(self):
        return [p for p in self.problemas if p.severidad == "ERROR"]

    @property
    def advertencias(self):
        return [p for p in self.problemas if p.severidad == "ADVERTENCIA"]

    @property
    def ok(self):
        return not self.errores

    def resumen(self):
        from collections import Counter
        return dict(errores=len(self.errores), advertencias=len(self.advertencias),
                    info=sum(1 for p in self.problemas if p.severidad == "INFO"),
                    por_codigo=dict(Counter(f"{p.severidad}:{p.codigo}" for p in self.problemas)))

    def filas(self):
        return [asdict(p) for p in self.problemas]

    def texto(self, maximo=40):
        lineas = []
        for p in sorted(self.problemas, key=lambda x: ({"ERROR": 0, "ADVERTENCIA": 1}.get(x.severidad, 2), x.codigo))[:maximo]:
            ubic = p.hoja + (f"!fila {p.fila}" if p.fila else "") + (f" [{p.columna}]" if p.columna else "")
            lineas.append(f"{p.severidad:11s} {p.codigo} {ubic}: {p.mensaje}")
        if len(self.problemas) > maximo:
            lineas.append(f"... y {len(self.problemas) - maximo} problemas más (ver informe completo)")
        return "\n".join(lineas)


class ErrorDatos(Exception):
    """Se lanza cuando la base tiene errores que invalidarían la optimización."""

    def __init__(self, informe: InformeCalidad):
        self.informe = informe
        super().__init__(f"La base de datos tiene {len(informe.errores)} errores; no se optimiza.\n" + informe.texto(25))
