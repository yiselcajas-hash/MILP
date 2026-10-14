"""Gráficos de resultados. Cada figura se construye EXCLUSIVAMENTE a partir de archivos de 04_RESULTADOS
escritos por corridas reales; si falta un archivo, la figura se omite y se informa (nunca se inventa).

Convenciones (paleta validada con el validador de daltonismo): el color sigue a la combinación de métodos en
todas las figuras; estados (a tiempo / atrasado) usan la paleta de estado con etiqueta; un único eje y por panel;
rejillas finas; leyenda siempre que haya ≥ 2 series.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"
SERIE = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
COLOR = {"FIFO+CONV": SERIE[0], "FIFO+MILP": SERIE[1], "EDD+EDD": SERIE[2], "MILP+CONV": SERIE[3], "MILP+MILP": SERIE[4]}
ORDEN = list(COLOR)
METODO = {"CONV": COLOR["FIFO+CONV"], "EDD": COLOR["EDD+EDD"], "MILP": COLOR["FIFO+MILP"]}
BUENO, CRITICO = "#0ca30c", "#d03b3b"
GRIS = "#c3c2b7"
NOTA = "Datos SIMULADOS (pedidos, averías, habilidades); tiempos de ruta ESTIMADOS. No son resultados históricos."

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "font.family": "DejaVu Sans", "font.size": 9, "axes.edgecolor": AXIS, "axes.labelcolor": INK2,
    "axes.titlesize": 10, "axes.titleweight": "bold", "axes.titlecolor": INK, "xtick.color": MUTED, "ytick.color": MUTED,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6, "grid.linestyle": "-", "axes.axisbelow": True,
    "axes.spines.top": False, "axes.spines.right": False, "legend.frameon": False, "legend.fontsize": 8,
    "figure.dpi": 110, "savefig.dpi": 150,
})


def _leer(ruta):
    ruta = Path(ruta)
    return pd.read_csv(ruta) if ruta.exists() else None


def _guardar(fig, ruta, nota=NOTA):
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    if nota:   # la nota va debajo de todo lo dibujado (ejes, rótulos y leyendas), nunca encima
        fig.canvas.draw()
        caja = fig.get_tightbbox(fig.canvas.get_renderer())
        fig.text(caja.x0 / fig.get_figwidth(), caja.y0 / fig.get_figheight() - 0.012, nota, fontsize=7, color=MUTED,
                 ha="left", va="top")
    fig.savefig(ruta, bbox_inches="tight")
    plt.close(fig)
    return ruta


def _barras_agrupadas(ax, df, x, serie, valor, orden_series, colores, etiquetas=False, fmt="{:.0f}"):
    xs = list(dict.fromkeys(df[x]))
    n = len(orden_series)
    ancho = 0.8 / max(1, n)
    for i, s in enumerate(orden_series):
        sub = df[df[serie] == s].set_index(x).reindex(xs)
        pos = np.arange(len(xs)) + (i - (n - 1) / 2) * ancho
        b = ax.bar(pos, sub[valor].values, width=ancho * 0.92, color=colores.get(s, SERIE[i % 8]), label=s)
        if etiquetas:
            for r, v in zip(b, sub[valor].values):
                if pd.notna(v):
                    ax.annotate(fmt.format(v), (r.get_x() + r.get_width() / 2, r.get_height()), ha="center", va="bottom",
                                fontsize=7, color=INK2, xytext=(0, 2), textcoords="offset points")
    ax.set_xticks(np.arange(len(xs)))
    ax.set_xticklabels(xs)


def _dias(res):
    cal = _leer(Path(res) / "Resultados_MILP" / "calendario_productivo.csv")
    return cal


def _eje_fechas(ax, cal, h0, h1, paso_dias=None):
    if cal is None:
        ax.set_xlabel("horas productivas")
        return
    k0, k1 = int(h0 // 8), int(np.ceil(h1 / 8))
    paso = paso_dias or max(1, (k1 - k0) // 10)
    ks = list(range(k0, k1 + 1, paso))
    ax.set_xticks([k * 8 for k in ks])
    fechas = cal.set_index("dia")["fecha"]
    ax.set_xticklabels([str(fechas.get(k, ""))[5:10] for k in ks], rotation=0)
    ax.set_xlabel("fecha (día productivo; 8 h por día)")


# ------------------------------------------------------------------------------------------- Gantt
def gantt_maquinas(res, etiqueta, h0, h1, ruta, titulo):
    prog = _leer(Path(res) / "Resultados_MILP" / f"programa_{etiqueta}.csv")
    if prog is None:
        return None
    ven = _leer(Path(res) / "Resultados_MILP" / f"ventanas_{etiqueta}.csv")
    cal = _dias(res)
    unidades = sorted(prog["unidad"].unique())
    fams = sorted(prog["familia"].unique())
    cfam = {f: SERIE[i] for i, f in enumerate(fams)}
    fig, ax = plt.subplots(figsize=(12, 0.42 * len(unidades) + 1.6))
    y = {u: i for i, u in enumerate(unidades)}
    vis = prog[(prog["fin_h"] > h0) & (prog["inicio_h"] < h1)]
    for _, r in vis.iterrows():
        parcial = r["tramo"] != "FINAL"
        ax.barh(y[r["unidad"]], r["fin_h"] - r["inicio_h"], left=r["inicio_h"], height=0.62,
                color=GRIS if parcial else cfam[r["familia"]], edgecolor=SURFACE, linewidth=1.0)
    if ven is not None:
        for _, w in ven[(ven["fin_h"] > h0) & (ven["inicio_h"] < h1)].iterrows():
            if w["unidad"] in y:
                ax.barh(y[w["unidad"]], w["fin_h"] - w["inicio_h"], left=w["inicio_h"], height=0.9, color="none",
                        edgecolor=CRITICO, linewidth=1.2, hatch="////")
    for k in range(int(h0 // 8), int(h1 // 8) + 1):
        ax.axvline(k * 8, color=GRID, linewidth=0.6, zorder=0)
    ax.set_yticks(range(len(unidades)))
    ax.set_yticklabels(unidades)
    ax.invert_yaxis()
    ax.set_xlim(h0, h1)
    ax.grid(axis="y", visible=False)
    _eje_fechas(ax, cal, h0, h1, paso_dias=1 if (h1 - h0) <= 120 else None)
    from matplotlib.patches import Patch
    leg = [Patch(color=cfam[f], label=f) for f in fams] + [Patch(color=GRIS, label="tramo interrumpido (parcial)"),
                                                          Patch(facecolor="none", edgecolor=CRITICO, hatch="////",
                                                                label="unidad indisponible (avería)")]
    ax.legend(handles=leg, ncol=6, loc="lower left", bbox_to_anchor=(0, 1.0))
    ax.set_title(titulo, loc="left", pad=26)
    return _guardar(fig, ruta)


def gantt_pedidos(res, etiqueta, ruta, titulo):
    ped = _leer(Path(res) / "Indicadores_KPI" / f"pedidos_{etiqueta}.csv")
    if ped is None:
        return None
    ped = ped.sort_values("r_h").reset_index(drop=True)
    cal = _dias(res)
    fig, ax = plt.subplots(figsize=(12, 0.13 * len(ped) + 1.8))
    for i, r in ped.iterrows():
        c = CRITICO if r["atrasado"] else BUENO
        ax.plot([r["r_h"], r["inicio_h"]], [i, i], color=GRID, linewidth=2, solid_capstyle="round")
        ax.plot([r["inicio_h"], r["fin_h"]], [i, i], color=c, linewidth=2.2, solid_capstyle="round")
        ax.plot([r["d_h"]], [i], marker="|", color=INK, markersize=6, markeredgewidth=1.2)
    ax.set_yticks(range(len(ped)))
    ax.set_yticklabels(ped["pedido"], fontsize=5.5)
    ax.invert_yaxis()
    ax.grid(axis="y", visible=False)
    _eje_fechas(ax, cal, 0, ped["fin_h"].max(), paso_dias=21)
    from matplotlib.lines import Line2D
    leg = [Line2D([], [], color=GRID, lw=2, label="espera desde la liberación"),
           Line2D([], [], color=BUENO, lw=2.2, label="en proceso — termina a tiempo"),
           Line2D([], [], color=CRITICO, lw=2.2, label="en proceso — termina atrasado"),
           Line2D([], [], color=INK, marker="|", lw=0, markersize=7, label="vencimiento d_j")]
    ax.legend(handles=leg, ncol=4, loc="lower left", bbox_to_anchor=(0, 1.0))
    n_t = int(ped["atrasado"].sum())
    ax.set_title(f"{titulo} — {len(ped) - n_t} a tiempo, {n_t} atrasados", loc="left", pad=24)
    return _guardar(fig, ruta)


def gantt_caso(res, sid, ruta):
    base = Path(res) / "Resultados_MILP"
    dfs = {m: _leer(base / f"caso_{sid}_{m}.csv") for m in ("CONV", "EDD", "MILP")}
    if any(v is None for v in dfs.values()):
        return None
    ven = _leer(base / f"caso_{sid}_ventanas.csv")
    e2b = _leer(Path(res) / "Comparacion_MILP_FIFO" / "E2b_reaccion_evento.csv")
    cal = _dias(res)
    libres = pd.concat([d[d["libre"] == 1] for d in dfs.values()])
    h0 = float(ven["inicio_h"].min()) - 8 if ven is not None and len(ven) else float(libres["inicio_h"].min())
    h1 = float(libres["fin_h"].max()) + 4
    unidades = sorted(set().union(*[set(d[(d["fin_h"] > h0)]["unidad"]) for d in dfs.values()]))
    fig, axs = plt.subplots(3, 1, figsize=(12, 3 * (0.3 * len(unidades) + 0.9)), sharex=True)
    for ax, (m, d) in zip(axs, dfs.items()):
        y = {u: i for i, u in enumerate(unidades)}
        for _, r in d[(d["fin_h"] > h0) & (d["unidad"].isin(unidades))].iterrows():
            ax.barh(y[r["unidad"]], r["fin_h"] - r["inicio_h"], left=r["inicio_h"], height=0.6,
                    color=METODO[m] if r["libre"] else GRIS, edgecolor=SURFACE, linewidth=0.8)
        if ven is not None:
            for _, w in ven.iterrows():
                if w["unidad"] in y:
                    ax.barh(y[w["unidad"]], w["fin_h"] - w["inicio_h"], left=w["inicio_h"], height=0.9, color="none",
                            edgecolor=CRITICO, linewidth=1.2, hatch="////")
        ax.set_yticks(range(len(unidades)))
        ax.set_yticklabels(unidades, fontsize=7)
        ax.invert_yaxis()
        ax.grid(axis="y", visible=False)
        txt = ""
        if e2b is not None:
            f = e2b[(e2b["escenario"] == sid) & (e2b["metodo"] == m)]
            if len(f):
                f = f.iloc[0]
                txt = (f" — atrasados {f['atrasados']:.0f}/{f['pedidos']:.0f}, Σw·T {f['tardanza_ponderada']:.1f} h, "
                       f"desviación {f['desviacion_total_h']:.1f} h, estado {f['estado']}")
        ax.set_title(f"{sid} · reacción {m}{txt}", loc="left", fontsize=9)
    axs[-1].set_xlim(h0, h1)
    _eje_fechas(axs[-1], cal, h0, h1)
    from matplotlib.patches import Patch
    axs[0].legend(handles=[Patch(color=GRIS, label="operación fija (completada o en curso)"),
                           Patch(color=METODO["CONV"], label="reprogramada CONV"),
                           Patch(color=METODO["EDD"], label="reprogramada EDD"),
                           Patch(color=METODO["MILP"], label="reprogramada MILP"),
                           Patch(facecolor="none", edgecolor=CRITICO, hatch="////", label="avería")],
                  ncol=5, loc="lower left", bbox_to_anchor=(0, 1.12))
    return _guardar(fig, ruta)


# ------------------------------------------------------------------------------------------- comparaciones
def e1_kpis(res, ruta, escenario="S20A"):
    df = _leer(Path(res) / "Comparacion_MILP_FIFO" / "E1_anual.csv")
    if df is None:
        return None
    df = df[df["escenario"] == escenario]
    combos = [c for c in ORDEN if c in set(df["combinacion"])]
    df = df.set_index("combinacion").reindex(combos).reset_index()
    met = [("atrasados", "pedidos atrasados", "{:.0f}"), ("otd_pct", "OTD (%)", "{:.1f}"),
           ("tardanza_ponderada", "Σ w·T (h ponderadas)", "{:.0f}"), ("tardanza_total_h", "Σ T (h productivas)", "{:.0f}"),
           ("penalidad_estimada", "penalidad ESTIMADA (S/)", "{:,.0f}"), ("desviacion_total_h", "desviación por averías (h)", "{:.0f}")]
    met = [m for m in met if m[0] in df]
    fig, axs = plt.subplots(2, 3, figsize=(13, 6.5))
    for ax, (c, t, fmt) in zip(axs.flat, met):
        b = ax.bar(range(len(combos)), df[c], color=[COLOR[x] for x in combos], width=0.7)
        for r, v in zip(b, df[c]):
            ax.annotate(fmt.format(v), (r.get_x() + r.get_width() / 2, r.get_height()), ha="center", va="bottom",
                        fontsize=7, color=INK2, xytext=(0, 2), textcoords="offset points")
        ax.set_xticks(range(len(combos)))
        ax.set_xticklabels(combos, rotation=30, ha="right", fontsize=7.5)
        ax.set_title(t, loc="left")
    for ax in list(axs.flat)[len(met):]:
        ax.axis("off")
    fig.suptitle(f"E1 · año 2025 por eventos, escenario {escenario}: comparación bajo las mismas restricciones",
                 x=0.01, ha="left", fontweight="bold", color=INK)
    fig.tight_layout(rect=(0, 0.02, 1, 0.96))
    return _guardar(fig, ruta)


def e1_otd(res, ruta):
    df = _leer(Path(res) / "Comparacion_MILP_FIFO" / "E1_anual.csv")
    if df is None:
        return None
    combos = [c for c in ORDEN if c in set(df["combinacion"])]
    fig, ax = plt.subplots(figsize=(9, 4))
    piv = df.pivot_table(index="escenario", columns="combinacion", values="otd_pct")
    _barras_agrupadas(ax, df[["escenario", "combinacion", "otd_pct"]], "escenario", "combinacion", "otd_pct",
                      [c for c in combos if c in piv.columns], COLOR, etiquetas=True, fmt="{:.0f}")
    ax.set_ylim(0, 105)
    ax.set_ylabel("pedidos entregados a tiempo (%)")
    ax.legend(ncol=5, loc="lower left", bbox_to_anchor=(0, 1.0))
    ax.set_title("OTD por combinación: S00 sin averías y S20A con 12 averías de la plegadora\n"
                 "(en S00 la reacción no interviene: FIFO+MILP ≡ FIFO+CONV y MILP+MILP ≡ MILP+CONV)", loc="left", pad=24)
    return _guardar(fig, ruta)


def evolucion_tardanza(res, ruta, escenario="S20A"):
    base = Path(res) / "Indicadores_KPI"
    cal = _dias(res)
    fig, ax = plt.subplots(figsize=(11, 4.6))
    hmax = 0
    finales = []
    for c in ORDEN:
        df = _leer(base / f"pedidos_{escenario}_{c.replace('+', '_')}.csv")
        if df is None:
            continue
        df = df.sort_values("fin_h")
        y = (df["w"] * df["tardanza_h"]).cumsum()
        ax.step(df["fin_h"], y, where="post", color=COLOR[c], linewidth=2, label=c)
        finales.append([float(y.iloc[-1]), float(df["fin_h"].iloc[-1]), c])
        hmax = max(hmax, df["fin_h"].max())
    if hmax == 0:
        plt.close(fig)
        return None
    # rótulos finales sin superposición: separación mínima del 4 % del rango vertical
    finales.sort()
    sep = 0.04 * max(f[0] for f in finales)
    pos = []
    for v, x, c in finales:
        pos.append(max(v, pos[-1] + sep) if pos else v)
    for (v, x, c), yp in zip(finales, pos):
        ax.annotate(f"{c}: {v:.0f}", (x, v), xytext=(x + 6, yp), textcoords="data", fontsize=7.5, color=INK2,
                    va="center", annotation_clip=False)
    _eje_fechas(ax, cal, 0, hmax, paso_dias=21)
    ax.set_ylabel("Σ w·T acumulada (h ponderadas)")
    ax.legend(ncol=5, loc="upper left")
    ax.set_title(f"Evolución de la tardanza ponderada acumulada a lo largo del año ({escenario})", loc="left")
    return _guardar(fig, ruta)


def distribucion_tardanza(res, ruta, escenario="S20A"):
    base = Path(res) / "Indicadores_KPI"
    datos, nombres = [], []
    for c in ORDEN:
        df = _leer(base / f"pedidos_{escenario}_{c.replace('+', '_')}.csv")
        if df is not None:
            datos.append(df["tardanza_h"].values)
            nombres.append(c)
    if not datos:
        return None
    fig, ax = plt.subplots(figsize=(10, 4.2))
    rng = np.random.default_rng(0)       # dispersión horizontal solo visual (no altera los datos)
    for i, (v, c) in enumerate(zip(datos, nombres)):
        x = i + rng.uniform(-0.18, 0.18, len(v))
        ax.scatter(x, v, s=14, color=COLOR[c], edgecolor=SURFACE, linewidth=0.6, label=c)
        q = np.percentile(v, [50, 90])
        ax.plot([i - 0.3, i + 0.3], [q[0], q[0]], color=INK, linewidth=1.2)
        ax.annotate(f"mediana {q[0]:.1f} h · P90 {q[1]:.1f} h", (i, max(v)), xytext=(0, 6), textcoords="offset points",
                    ha="center", fontsize=7, color=INK2)
    ax.set_xticks(range(len(nombres)))
    ax.set_xticklabels(nombres)
    ax.set_ylim(bottom=-2, top=max(float(np.max(v)) for v in datos) * 1.15 + 1)
    ax.set_ylabel("tardanza por pedido T_j (h productivas)")
    ax.set_title(f"Distribución de la tardanza por pedido ({escenario}; cada punto es un pedido, línea = mediana)",
                 loc="left")
    return _guardar(fig, ruta)


def impacto_fallas(res, ruta):
    df = _leer(Path(res) / "Comparacion_MILP_FIFO" / "E2_escenarios_falla.csv")
    if df is None:
        return None
    escs = list(dict.fromkeys(df["escenario"]))
    combos = [c for c in ("FIFO+CONV", "EDD+EDD", "FIFO+MILP") if c in set(df["combinacion"])]
    fig, axs = plt.subplots(1, 2, figsize=(13, 0.28 * len(escs) + 2), sharey=True)
    for ax, (col, t) in zip(axs, (("delta_tardanza_ponderada", "Δ Σ w·T frente al año sin averías (h ponderadas)"),
                                  ("delta_atrasados", "Δ pedidos atrasados frente al año sin averías"))):
        n = len(combos)
        h = 0.8 / n
        for i, c in enumerate(combos):
            sub = df[df["combinacion"] == c].set_index("escenario").reindex(escs)
            ax.barh(np.arange(len(escs)) + (i - (n - 1) / 2) * h, sub[col], height=h * 0.9, color=COLOR[c], label=c)
        ax.axvline(0, color=INK2, linewidth=0.8)
        ax.set_title(t, loc="left", fontsize=9)
        ax.grid(axis="y", visible=False)
    axs[0].set_yticks(range(len(escs)))
    axs[0].set_yticklabels(escs, fontsize=7)
    axs[0].invert_yaxis()
    axs[0].legend(ncol=3, loc="lower left", bbox_to_anchor=(0, 1.04))
    fig.suptitle("E2 · impacto sistémico de cada escenario de avería (plan FIFO vigente; valores < 0 = mejor que sin "
                 "avería por reoptimizar)", x=0.01, ha="left", fontweight="bold", color=INK, y=1.0)
    fig.tight_layout()
    return _guardar(fig, ruta)


def e2b(res, ruta):
    df = _leer(Path(res) / "Comparacion_MILP_FIFO" / "E2b_reaccion_evento.csv")
    if df is None:
        return None
    df = df.assign(combinacion=df["metodo"].map({"CONV": "FIFO+CONV", "EDD": "EDD+EDD", "MILP": "FIFO+MILP"}))
    fig, axs = plt.subplots(1, 3, figsize=(13, 3.8))
    for ax, (c, t, fmt) in zip(axs, (("tardanza_ponderada", "Σ w·T de los pedidos del subproblema", "{:.0f}"),
                                     ("atrasados", "pedidos atrasados", "{:.0f}"),
                                     ("desviacion_total_h", "desviación de inicios Σ|S−S0| (h)", "{:.0f}"))):
        _barras_agrupadas(ax, df, "escenario", "combinacion", c, ["FIFO+CONV", "EDD+EDD", "FIFO+MILP"], COLOR,
                          etiquetas=True, fmt=fmt)
        ax.set_title(t, loc="left", fontsize=9)
    axs[0].legend(["CONV (desplazar)", "EDD", "MILP lexicográfico"], ncol=3, loc="lower left", bbox_to_anchor=(0, 1.08))
    fig.suptitle("E2b · reacción a la avería sobre el MISMO subproblema", x=0.01, ha="left", fontweight="bold",
                 color=INK, y=1.08)
    fig.tight_layout()
    return _guardar(fig, ruta)


def e3(res, ruta):
    df = _leer(Path(res) / "Escenarios" / "E3_escenarios_operativos.csv")
    if df is None:
        return None
    combos = [c for c in ORDEN if c in set(df["combinacion"])]
    fig, axs = plt.subplots(2, 1, figsize=(13, 7.5), sharex=True)
    for ax, (c, t) in zip(axs, (("tardanza_ponderada", "Σ w·T (h ponderadas)"), ("atrasados", "pedidos atrasados"))):
        _barras_agrupadas(ax, df, "escenario", "combinacion", c, combos, COLOR)
        ax.set_title(t, loc="left")
    axs[1].set_xticklabels(list(dict.fromkeys(df["escenario"])), rotation=30, ha="right")
    axs[0].legend(ncol=3, loc="lower right", bbox_to_anchor=(1, 1.0))
    fig.suptitle("E3 · escenarios operativos SIMULADOS (27_ESCENARIOS_OPERATIVOS_SIM)", x=0.01, ha="left",
                 fontweight="bold", color=INK)
    fig.tight_layout()
    return _guardar(fig, ruta)


def e5(res, ruta):
    df = _leer(Path(res) / "Resultados_MILP" / "E5_rendimiento.csv")
    if df is None:
        return None
    df = df[df["presolve"] == 1].copy()
    vers = list(dict.fromkeys(df["version"]))
    cv = {v: SERIE[i] for i, v in enumerate(vers)}
    fig, axs = plt.subplots(1, 3, figsize=(13, 3.8))
    for ax, (c, t) in zip(axs, (("variables", "variables"), ("binarias", "variables enteras"),
                                ("tiempo_solver_s", "tiempo de HiGHS (s)"))):
        _barras_agrupadas(ax, df, "escenario", "version", c, vers, cv, etiquetas=True,
                          fmt="{:.1f}" if c.startswith("tiempo") else "{:.0f}")
        ax.set_title(t, loc="left")
    axs[0].legend(ncol=3, loc="lower left", bbox_to_anchor=(0, 1.08))
    fig.suptitle("E5 · tamaño y tiempo del MILP en el mismo subproblema (mismo equipo, HiGHS vía SciPy)", x=0.01,
                 ha="left", fontweight="bold", color=INK, y=1.08)
    fig.tight_layout()
    return _guardar(fig, ruta, NOTA + " Tiempos de una sola corrida: varían entre equipos.")


# ------------------------------------------------------------------------------------------- recursos
def cuello_botella(res, ruta):
    df = _leer(Path(res) / "Indicadores_KPI" / "E0_diagnostico_cuello_botella.csv")
    if df is None:
        return None
    df = df.sort_values("espera_cola_fifo_h", ascending=True)
    top = df["espera_cola_fifo_h"].idxmax()
    col = [SERIE[0] if i == top else GRIS for i in df.index]
    fig, axs = plt.subplots(1, 2, figsize=(12, 4.6), sharey=True)
    axs[0].barh(df["unidad"], df["espera_cola_fifo_h"], color=col, height=0.66)
    axs[0].set_title("espera en cola ante cada unidad (programa FIFO, h)", loc="left")
    axs[1].barh(df["unidad"], df["utilizacion_fifo_pct"], color=col, height=0.66)
    axs[1].set_title("utilización en [0, makespan] (programa FIFO, %)", loc="left")
    for ax in axs:
        ax.grid(axis="y", visible=False)
    r = df.loc[top]
    fig.suptitle(f"Diagnóstico de cuello de botella: {r['unidad']} concentra la mayor espera "
                 f"({r['espera_cola_fifo_h']:.0f} h) y utilización ({r['utilizacion_fifo_pct']:.0f} %)",
                 x=0.01, ha="left", fontweight="bold", color=INK)
    fig.tight_layout()
    return _guardar(fig, ruta)


def distribucion_tiempo(res, etiqueta, ruta, titulo):
    df = _leer(Path(res) / "Indicadores_KPI" / f"utilizacion_{etiqueta}.csv")
    if df is None:
        return None
    df = df.sort_values("utilizacion_pct")
    fig, ax = plt.subplots(figsize=(11, 4.8))
    izq = np.zeros(len(df))
    for c, nombre, color in (("ocupado_h", "ocupado (proceso)", SERIE[0]), ("indisponible_h", "indisponible (avería)", SERIE[1]),
                             ("ocio_h", "ocioso", SERIE[2])):
        ax.barh(df["unidad"], df[c], left=izq, color=color, height=0.66, label=nombre, edgecolor=SURFACE, linewidth=1)
        izq += df[c].values
    for y, (u, p) in enumerate(zip(df["unidad"], df["utilizacion_pct"])):
        ax.annotate(f"{p:.0f} %", (izq[y], y), xytext=(4, 0), textcoords="offset points", va="center", fontsize=7, color=INK2)
    ax.set_xlabel("horas productivas en [0, makespan]")
    ax.grid(axis="y", visible=False)
    ax.legend(ncol=3, loc="lower left", bbox_to_anchor=(0, 1.0))
    ax.set_title(titulo + " (rótulo = utilización)", loc="left", pad=22)
    return _guardar(fig, ruta)


def carga_trabajadores(res, etiqueta, ruta, titulo):
    df = _leer(Path(res) / "Indicadores_KPI" / f"carga_trabajadores_{etiqueta}.csv")
    if df is None:
        return None
    df = df.sort_values("horas", ascending=False)
    fig, ax = plt.subplots(figsize=(11, 4))
    ax.bar(df["trabajador"], df["horas"], color=SERIE[0], width=0.7)
    media = df["horas"].mean()
    ax.axhline(media, color=INK2, linewidth=1)
    ax.annotate(f"media {media:.0f} h", (len(df) - 0.5, media), xytext=(0, 4), textcoords="offset points", ha="right",
                fontsize=7.5, color=INK2)
    ax.set_ylabel("horas asignadas en el año")
    ax.tick_params(axis="x", rotation=90)
    ax.grid(axis="x", visible=False)
    ax.set_title(titulo, loc="left")
    return _guardar(fig, ruta, NOTA + " Asignación MILP min-max sobre habilidades SIMULADAS.")


# ------------------------------------------------------------------------------------------- sensibilidad
def sensibilidad(res, carpeta):
    df = _leer(Path(res) / "Escenarios" / "E4_sensibilidad.csv")
    if df is None:
        return []
    out = []
    for factor, g in df.groupby("factor", sort=False):
        g = g.copy()
        g["serie"] = g["escenario"] + " · " + g["combinacion"]
        series = list(dict.fromkeys(g["serie"]))
        cs = {s: COLOR.get(s.split(" · ")[1], SERIE[i % 8]) if len(set(g["escenario"])) == 1 else SERIE[i % 8]
              for i, s in enumerate(series)}
        metricas = [("tardanza_ponderada", "Σ w·T (h ponderadas)"), ("atrasados", "pedidos atrasados"),
                    ("penalidad_estimada", "penalidad ESTIMADA (S/)")]
        if g["desviacion_total_h"].abs().sum() > 0:
            metricas.append(("desviacion_total_h", "desviación por averías (h)"))
        fig, axs = plt.subplots(1, len(metricas), figsize=(3.4 * len(metricas) + 1, 3.6))
        for ax, (c, t) in zip(np.atleast_1d(axs), metricas):
            _barras_agrupadas(ax, g.assign(nivel=g["nivel"].astype(str)), "nivel", "serie", c, series, cs)
            ax.set_title(t, loc="left", fontsize=9)
            ax.set_xlabel(f"nivel de {factor}")
        fig.tight_layout()
        leg = np.atleast_1d(axs)[0].legend(ncol=4, loc="lower left", bbox_to_anchor=(0, 1.1), fontsize=7,
                                           title=f"E4 · sensibilidad a {factor}",
                                           title_fontproperties={"weight": "bold", "size": 10})
        leg._legend_box.align = "left"
        out.append(_guardar(fig, Path(carpeta) / f"sensibilidad_{factor}.png"))
    return out


# ------------------------------------------------------------------------------------------- orquestación
def generar_todos(resultados, graficos, log=print):
    R, G = Path(resultados), Path(graficos)
    hechos = []

    def hacer(nombre, f, *a):
        try:
            r = f(*a)
        except Exception as ex:  # noqa: BLE001 - una figura fallida no detiene las demás; se informa
            log(f"Gráfico {nombre}: ERROR {type(ex).__name__}: {ex}")
            return
        if r is None or r == []:
            log(f"Gráfico {nombre}: omitido (faltan resultados de origen)")
        else:
            hechos.extend(r if isinstance(r, list) else [r])

    ev = _leer(R / "Resultados_MILP" / "eventos_S20A_MILP_MILP.csv")
    if ev is not None and (ev["tipo"] == "FALLA").any():
        a = float(ev[ev["tipo"] == "FALLA"]["t"].iloc[5 if (ev["tipo"] == "FALLA").sum() > 5 else 0])
        h0, h1 = 8 * (a // 8) - 16, 8 * (a // 8) + 56
    else:
        h0, h1 = 1280.0, 1360.0
    for c in ("FIFO_CONV", "MILP_MILP"):
        hacer(f"gantt_maquinas_{c}", gantt_maquinas, R, f"S20A_{c}", h0, h1,
              G / "Diagramas_Gantt" / f"gantt_maquinas_S20A_{c}.png",
              f"Gantt por unidad · S20A · {c.replace('_', '+')} · ventana de 9 días productivos alrededor de una avería")
        hacer(f"gantt_pedidos_{c}", gantt_pedidos, R, f"S20A_{c}", G / "Diagramas_Gantt" / f"gantt_pedidos_S20A_{c}.png",
              f"Gantt por pedido · S20A · {c.replace('_', '+')}")
    for sid in ("S06A", "S13A", "S19A"):
        hacer(f"gantt_caso_{sid}", gantt_caso, R, sid, G / "Diagramas_Gantt" / f"gantt_reaccion_{sid}.png")
    hacer("e1_kpis_S20A", e1_kpis, R, G / "Comparaciones" / "E1_kpis_S20A.png", "S20A")
    hacer("e1_kpis_S00", e1_kpis, R, G / "Comparaciones" / "E1_kpis_S00.png", "S00")
    hacer("e1_otd", e1_otd, R, G / "Comparaciones" / "E1_OTD.png")
    hacer("evolucion", evolucion_tardanza, R, G / "Comparaciones" / "evolucion_tardanza_acumulada_S20A.png")
    hacer("distribucion", distribucion_tardanza, R, G / "Comparaciones" / "distribucion_tardanza_S20A.png")
    hacer("impacto_fallas", impacto_fallas, R, G / "Comparaciones" / "E2_impacto_fallas.png")
    hacer("e2b", e2b, R, G / "Comparaciones" / "E2b_reaccion_evento.png")
    hacer("e3", e3, R, G / "Comparaciones" / "E3_escenarios_operativos.png")
    hacer("e5", e5, R, G / "Comparaciones" / "E5_rendimiento_v14_v20.png")
    hacer("cuello", cuello_botella, R, G / "Utilizacion_Recursos" / "diagnostico_cuello_botella.png")
    for c in ("FIFO_CONV", "MILP_MILP"):
        hacer(f"tiempo_{c}", distribucion_tiempo, R, f"S20A_{c}", G / "Utilizacion_Recursos" / f"distribucion_tiempo_S20A_{c}.png",
              f"Distribución del tiempo por unidad · S20A · {c.replace('_', '+')}")
    hacer("carga", carga_trabajadores, R, "S20A_MILP_MILP", G / "Utilizacion_Recursos" / "carga_trabajadores_S20A_MILP_MILP.png",
          "Carga anual por trabajador · S20A · MILP+MILP (asignación equilibrada)")
    hacer("carga_fifo", carga_trabajadores, R, "S20A_FIFO_CONV", G / "Utilizacion_Recursos" / "carga_trabajadores_S20A_FIFO_CONV.png",
          "Carga anual por trabajador · S20A · FIFO+CONV (asignación equilibrada)")
    hacer("sensibilidad", sensibilidad, R, G / "Analisis_Sensibilidad")
    log(f"Gráficos generados: {len(hechos)}")
    return hechos
