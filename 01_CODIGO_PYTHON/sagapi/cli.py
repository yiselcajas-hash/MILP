"""Interfaz de línea de comandos de SAGAPI v2.0.

Comandos
  validar       controla la calidad de la base; termina con código 2 si hay errores (no se optimiza).
  programar     simula el año con una combinación plan+reacción y un escenario; guarda programa y KPI.
  caso          compara CONV, EDD y MILP en el subproblema de la primera avería de un escenario.
  experimentos  ejecuta E0–E5 (todas las tablas de 04_RESULTADOS).
  reportes      genera gráficos (05_GRAFICOS) y el libro de resultados a partir de 04_RESULTADOS.
  todo          experimentos + reportes.
Rutas por defecto relativas a la carpeta del proyecto (la que contiene 01_CODIGO_PYTHON).
Códigos de salida: 0 correcto; 2 datos inválidos; 3 programa infactible o violación de verificación; 1 otro error.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path

from . import __version__

RAIZ = Path(__file__).resolve().parents[2]
BASE = RAIZ / "02_BASE_DATOS" / "SAGAPI_BASE_CORREGIDA_FINAL.xlsx"
RESULTADOS = RAIZ / "04_RESULTADOS"
GRAFICOS = RAIZ / "05_GRAFICOS"

log = logging.getLogger("sagapi")


def _configurar_log(nivel, archivo=None):
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s", "%H:%M:%S")
    log.handlers.clear()
    log.setLevel(getattr(logging, nivel.upper(), logging.INFO))
    h = logging.StreamHandler(sys.stdout)
    h.setFormatter(fmt)
    log.addHandler(h)
    if archivo:
        Path(archivo).parent.mkdir(parents=True, exist_ok=True)
        f = logging.FileHandler(archivo, encoding="utf-8")
        f.setFormatter(fmt)
        log.addHandler(f)


def cmd_validar(a):
    from .datos import cargar_base
    from .experimentos import escribir_csv
    d, inf = cargar_base(a.base, estricto=False)
    log.info("Base: %s", a.base)
    log.info("Calidad: %s", json.dumps(inf.resumen(), ensure_ascii=False))
    if inf.problemas:
        log.info("\n%s", inf.texto(60))
    if a.salida:
        escribir_csv(Path(a.salida) / "informe_calidad_datos.csv", inf.filas())
    if not inf.ok:
        log.error("La base tiene %d errores: no se optimiza.", len(inf.errores))
        return 2
    log.info("Base válida: %d pedidos, %d recursos, %d trabajadores (habilidades %s).", len(d.pedidos), len(d.maquinas),
             len(d.operarios), d.procedencia["habilidades"])
    return 0


def cmd_programar(a):
    from . import escenarios as esc, indicadores as K
    from .experimentos import Experimentos, escribir_csv
    E = Experimentos(a.base, a.salida, tl=a.tl, regla_objetivo=a.regla_objetivo, log=log.info)
    if a.congelar is not None:
        E.H = a.congelar
    evs, pol = ([], "A") if a.escenario == "S00" else esc.eventos_escenario(E.d, a.escenario)
    res, fila = E.correr(a.plan, a.reaccion, evs, asignar=not a.sin_personal, politica=pol)
    etiqueta = f"{a.escenario}_{a.plan}_{a.reaccion}"
    E.guardar_corrida(res, etiqueta)
    escribir_csv(E.ruta("kpi", f"KPI_{etiqueta}.csv"), [fila])
    for k in ("atrasados", "otd_pct", "tardanza_ponderada", "tardanza_total_h", "penalidad_estimada", "makespan_h",
              "eventos_optimos", "eventos_milp", "tiempo_total_s"):
        if k in fila:
            log.info("%-22s %s %s", k, f"{fila[k]:.2f}" if isinstance(fila[k], float) else fila[k], K.DEFINICIONES.get(k, ("", ""))[1])
    log.info("Verificación independiente: %s", res.verificacion)
    log.info("Personal: %s; asignación %s", res.modo_personal, res.asignacion_info.get("estado"))
    return 0


def cmd_caso(a):
    from .experimentos import Experimentos
    E = Experimentos(a.base, a.salida, tl=a.tl, regla_objetivo=a.regla_objetivo, log=log.info)
    filas = E.e2b_casos([a.escenario])
    return 0 if all(f["violaciones"] == 0 for f in filas) else 3


def cmd_experimentos(a):
    from .experimentos import Experimentos
    E = Experimentos(a.base, a.salida, tl=a.tl, regla_objetivo=a.regla_objetivo, log=log.info)
    solo = {x.strip().upper() for x in a.solo.split(",")} if a.solo else None
    pasos = [("E0", E.e0_validacion), ("E1", E.e1_anual), ("E2", E.e2_fallas), ("E2B", E.e2b_casos),
             ("E3", E.e3_operativos), ("E4", E.e4_sensibilidad), ("E5", E.e5_rendimiento)]
    t = time.perf_counter()
    for nombre, f in pasos:
        if solo and nombre not in solo:
            continue
        t1 = time.perf_counter()
        f()
        log.info("%s terminado en %.0f s", nombre, time.perf_counter() - t1)
    log.info("Experimentos terminados en %.0f s", time.perf_counter() - t)
    return 0


def cmd_reportes(a):
    from .reportes import excel, graficos
    graficos.generar_todos(a.salida, a.graficos, log=log.info)
    excel.libro_resultados(a.salida, Path(a.salida) / "Resultados_SAGAPI_v2.xlsx", log=log.info)
    return 0


def cmd_todo(a):
    r = cmd_experimentos(a)
    return r or cmd_reportes(a)


def construir_parser():
    p = argparse.ArgumentParser(prog="Programa_principal.py", description=f"SAGAPI {__version__}: programación MILP")
    p.add_argument("--version", action="version", version=__version__)
    sp = p.add_subparsers(dest="comando", required=True)

    def comunes(s, salida=True):
        s.add_argument("--base", default=str(BASE), help="libro Excel de la base de datos")
        if salida:
            s.add_argument("--salida", default=str(RESULTADOS), help="carpeta de resultados")
        s.add_argument("--log", default="INFO", help="nivel de registro (DEBUG, INFO, WARNING)")
        s.add_argument("--log-archivo", default=None, help="archivo de registro adicional")

    def solver(s):
        s.add_argument("--tl", type=float, default=None,
                       help="límite de tiempo por fase de HiGHS (s); por defecto limite_computo_s de la base")
        s.add_argument("--regla-objetivo", default=None,
                       choices=["TARDANZA_PONDERADA", "PENALIDAD_FIJA", "PENALIDAD_DIARIA_CON_TOPE"],
                       help="jerarquía de objetivos (por defecto, 28_CONFIG_MODELO)")

    s = sp.add_parser("validar", help="controles de calidad de la base")
    comunes(s, salida=False)
    s.add_argument("--salida", default=None)
    s = sp.add_parser("programar", help="simular el año con una combinación")
    comunes(s); solver(s)
    s.add_argument("--plan", default="MILP", choices=["FIFO", "EDD", "MILP"])
    s.add_argument("--reaccion", default="MILP", choices=["CONV", "EDD", "MILP"])
    s.add_argument("--escenario", default="S20A", help="escenario de 24_ESCENARIOS_FALLA_SIM (S00 = sin averías)")
    s.add_argument("--congelar", type=float, default=None, help="horizonte congelado (h productivas)")
    s.add_argument("--sin-personal", action="store_true", help="no calcular la asignación de trabajadores")
    s = sp.add_parser("caso", help="comparar reacciones ante una avería")
    comunes(s); solver(s)
    s.add_argument("--escenario", default="S06A")
    for nombre in ("experimentos", "todo"):
        s = sp.add_parser(nombre, help="ejecutar experimentos E0–E5" + (" y reportes" if nombre == "todo" else ""))
        comunes(s); solver(s)
        s.add_argument("--solo", default=None, help="lista separada por comas, p. ej. E0,E1")
        s.add_argument("--graficos", default=str(GRAFICOS))
    s = sp.add_parser("reportes", help="gráficos y libro de resultados")
    s.add_argument("--salida", default=str(RESULTADOS))
    s.add_argument("--graficos", default=str(GRAFICOS))
    s.add_argument("--log", default="INFO")
    s.add_argument("--log-archivo", default=None)
    return p


def main(argv=None):
    a = construir_parser().parse_args(argv)
    _configurar_log(a.log, a.log_archivo)
    from .datos.problemas import ErrorDatos
    from .simulacion import ErrorSimulacion
    cmd = {"validar": cmd_validar, "programar": cmd_programar, "caso": cmd_caso, "experimentos": cmd_experimentos,
           "reportes": cmd_reportes, "todo": cmd_todo}[a.comando]
    try:
        return cmd(a)
    except ErrorDatos as ex:
        log.error("%s", ex)
        return 2
    except ErrorSimulacion as ex:
        log.error("Programa infactible o violación detectada: %s", ex)
        return 3
    except FileNotFoundError as ex:
        log.error("No se encontró el archivo: %s", ex)
        return 1
    except Exception:  # noqa: BLE001 - se registra la traza completa y se informa el fallo con código 1
        log.exception("Error no previsto")
        return 1
