"""Escenario experimental: dotación polivalente, con capacidad de cobertura conservadora.

Los trabajadores son 25 personas reales en el agregado; sus *habilidades individuales* son
SIMULADAS. Se reserva una persona por recurso de máquina para todo el subproblema. Esta es
una CONDICIÓN SUFICIENTE de factibilidad, no la asignación horaria óptima con relevos.
"""
from __future__ import annotations


def emparejar(maquinas, habilidades):
    """Inyección máquina -> persona con habilidades verificadas EN EL ESCENARIO.

    Devuelve None si no se puede cubrir simultáneamente la lista de recursos.
    Orden determinista: permite reconstruir un vector de arranque completo.
    """
    maqs = sorted(set(maquinas))
    asign = {}  # persona -> máquina
    opciones = {m: [w for w in sorted(habilidades) if m in habilidades[w]] for m in maqs}
    if any(not opciones[m] for m in maqs):
        return None

    def buscar(m, visitados):
        for w in opciones[m]:
            if w in visitados:
                continue
            visitados.add(w)
            if w not in asign or buscar(asign[w], visitados):
                asign[w] = m
                return True
        return False

    # Comenzar por los recursos con menos personas elegibles ayuda a detectar escasez.
    for m in sorted(maqs, key=lambda x: (len(opciones[x]), x)):
        if not buscar(m, set()):
            return None
    return {m: w for w, m in asign.items()}


def resumen_dotacion(habilidades, maquinas):
    match = emparejar(maquinas, habilidades)
    return {
        "trabajadores": len(habilidades),
        "recursos_distintos": len(set(maquinas)),
        "habilidades_por_trabajador": {w: len(ms) for w, ms in habilidades.items()},
        "sin_personal": [m for m in sorted(set(maquinas)) if not any(m in h for h in habilidades.values())],
        "cobertura_total_simultanea": match is not None,
        "emparejamiento_testigo": match,
        "advertencia": "Matriz de habilidades simulada; verificar con responsable de planta."
    }
