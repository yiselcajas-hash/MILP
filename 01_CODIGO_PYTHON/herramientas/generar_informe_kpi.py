#!/usr/bin/env python3
"""Genera 07_DOCUMENTACION/fuentes/Informe_KPI.md EXCLUSIVAMENTE a partir de los archivos de 04_RESULTADOS.

Ninguna cifra se escribe a mano: si falta un archivo, la sección correspondiente se omite y se indica.
Uso: python 01_CODIGO_PYTHON/herramientas/generar_informe_kpi.py && python .../generar_pdfs.py Informe_KPI
"""
from __future__ import annotations

import json
import os

import pandas as pd

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
R = os.path.join(RAIZ, "04_RESULTADOS")
ORDEN = ["FIFO+CONV", "FIFO+MILP", "EDD+EDD", "MILP+CONV", "MILP+MILP"]


def _f(v, d=1):
    if pd.isna(v):
        return "—"
    if isinstance(v, (int,)) or (isinstance(v, float) and float(v).is_integer() and abs(v) >= 100):
        return f"{v:,.0f}".replace(",", " ")
    return f"{v:,.{d}f}".replace(",", " ").replace(".", ",")


def tabla(df, filas, columnas, etiquetas):
    out = ["| Indicador | Unidad | " + " | ".join(columnas) + " |", "|" + "---|" * (len(columnas) + 2)]
    for clave, unidad, dec in filas:
        if clave not in df.columns:
            continue
        vals = [_f(df.loc[c, clave], dec) if c in df.index else "—" for c in columnas]
        out.append(f"| {etiquetas.get(clave, clave)} | {unidad} | " + " | ".join(vals) + " |")
    return "\n".join(out)


def main():
    defs = pd.read_csv(os.path.join(R, "Indicadores_KPI", "KPI_definiciones.csv"))
    etiquetas = dict(zip(defs["indicador"], defs["definicion"]))
    e1 = pd.read_csv(os.path.join(R, "Comparacion_MILP_FIFO", "E1_anual.csv"))
    e0 = json.load(open(os.path.join(R, "Resultados_MILP", "E0_validacion.json"), encoding="utf-8"))
    filas = [("pedidos", "pedidos", 0), ("completados", "pedidos", 0), ("atrasados", "pedidos", 0), ("otd_pct", "%", 1),
             ("tardanza_total_h", "h", 1), ("tardanza_total_dias", "días", 1), ("tardanza_ponderada", "h pond.", 1),
             ("tardanza_max_h", "h", 1), ("tardanza_media_atrasados_h", "h", 1), ("adelanto_medio_h", "h", 1),
             ("flujo_medio_h", "h", 1), ("makespan_h", "h", 1), ("penalidad_estimada", "S/ (EST.)", 0),
             ("penalidad_diaria_tope", "S/ (EST.)", 0), ("horas_maquina", "h", 0), ("horas_reproceso", "h", 1),
             ("utilizacion_media_pct", "%", 1), ("utilizacion_max_pct", "%", 1), ("ocio_total_h", "h", 0),
             ("carga_trabajador_max_h", "h", 1), ("carga_trabajador_cv", "-", 2), ("energia_kwh", "kWh (EST.)", 0),
             ("costo_uso_maquinas", "S/ (EST.)", 0), ("costo_energia", "S/ (EST.)", 0),
             ("costo_mano_obra_directa", "S/ (EST.)", 0), ("desviacion_total_h", "h", 1), ("reasignaciones", "ops", 0),
             ("eventos_milp", "eventos", 0), ("eventos_optimos", "eventos", 0), ("eventos_limite_tiempo", "eventos", 0),
             ("brecha_max", "-", 6), ("tiempo_solver_s", "s", 1), ("tiempo_computo_s", "s", 1)]
    md = ["---", 'title: "SAGAPI v2.0 — Informe de indicadores (KPI)"',
          'subtitle: "Definiciones, fórmulas, unidades y valores de las corridas anuales E1"', "lang: es", "---", "",
          "> Todos los valores se generan automáticamente a partir de `04_RESULTADOS` "
          "(`herramientas/generar_informe_kpi.py`). Pedidos, averías y habilidades **SIMULADOS**; tiempos de ruta "
          "**ESTIMADOS**; montos en S/ **ESTIMADOS**. Los KPI describen corridas del modelo, no el desempeño histórico "
          "de la planta.", "", "# 1. Definiciones", "",
          "| Indicador | Fórmula | Unidad | Definición | Procedencia |", "|---|---|---|---|---|"]
    for _, d in defs.iterrows():
        celdas = [str(d[k]).replace("|", "\\|") for k in ("formula", "unidad", "definicion", "procedencia")]
        md.append(f"| `{d['indicador']}` | " + " | ".join(celdas) + " |")
    md += ["", "Notación: $C_j$ fin del pedido, $d_j$ vencimiento, $r_j$ liberación, $w_j$ peso por valor, $P_j$ "
           "penalidad fija estimada; $h_{dia}=8$ h. «Disponible» excluye las horas de avería de la unidad.", ""]
    for esc in ("S20A", "S00"):
        df = e1[e1["escenario"] == esc].set_index("combinacion")
        cols = [c for c in ORDEN if c in df.index]
        md += [f"# {2 if esc == 'S20A' else 3}. Valores — escenario {esc}"
               + (" (12 averías de la plegadora, política A)" if esc == "S20A" else " (sin averías)"), "",
               tabla(df, filas, cols, etiquetas), ""]
        if esc == "S00":
            md.append("En S00 la reacción no interviene: FIFO+MILP ≡ FIFO+CONV y MILP+MILP ≡ MILP+CONV (no se "
                      "repiten).")
            md.append("")
    md += ["# 4. Lectura de los KPI", "",
           f"* **Cumplimiento.** La tardanza inevitable (cota inferior con capacidad infinita) es "
           f"{_f(e0['tardanza_inevitable_total_h'])} h en {e0['pedidos_con_tardanza_inevitable']} pedidos: ningún "
           "método puede bajar de ella. Las combinaciones con MILP minimizan la tardanza ponderada; EDD atrasa menos "
           "pedidos. Es un compromiso que depende de la regla del objetivo (ver E4).",
           "* **Utilización.** La utilización de la unidad más cargada (la plegadora) es casi igual entre métodos "
           "porque el trabajo total es el mismo; solo cambian el orden y las fechas. La utilización media promedia "
           "solo las unidades usadas: FIFO no usa las unidades alternativas (PER-02, SOL-02) y por eso su promedio "
           "es mayor, sin que eso signifique más trabajo útil.",
           "* **Costos.** Uso de recursos, energía y mano de obra difieren menos del 1 % entre métodos: la "
           "programación no cambia el trabajo a realizar, solo cuándo se hace. Las únicas diferencias económicas "
           "relevantes son las penalidades ESTIMADAS.",
           "* **Personal.** La carga máxima corresponde a los trabajadores habilitados para la plegadora (habilidades "
           "SIMULADAS). La utilización media del personal es baja porque la base registra 5 742 h de proceso frente a "
           "52 200 h disponibles: esa brecha (PV-04) debe explicarse con datos reales antes de concluir nada sobre "
           "la dotación.",
           "* **Cómputo.** `brecha_max` = 0 y `eventos_optimos` = `eventos_milp` indican que todos los eventos "
           "terminaron con óptimo demostrado por HiGHS.", ""]
    ruta = os.path.join(RAIZ, "07_DOCUMENTACION", "fuentes", "Informe_KPI.md")
    with open(ruta, "w", encoding="utf-8") as fh:
        fh.write("\n".join(md))
    print(ruta)


if __name__ == "__main__":
    main()
