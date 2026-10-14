"""Construcción del modelo de datos del sistema a partir de las tablas leídas y validadas.

Punto de entrada: ``cargar_base(ruta, ajustes=None, estricto=True) -> (Datos, InformeCalidad)``.
Si ``estricto`` y la base tiene ERRORES, lanza ``ErrorDatos`` y no se construye nada: el programa
nunca optimiza sobre datos inválidos.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

from ..calendario import Calendario
from .calidad import controlar
from .lector import leer_libro
from .problemas import ErrorDatos, InformeCalidad


@dataclass
class Maquina:
    id: str
    nombre: str
    tipo_recurso: str
    cantidad: int
    costo_h: float
    potencia_kw: float
    factor_carga: float
    grupo: str = ""
    critico: int = 0


@dataclass
class Datos:
    archivo: str
    familias: dict
    productos: dict
    maquinas: dict
    rutas: dict
    elegibilidad: dict
    pedidos: list
    calendario: Calendario
    fallas: dict
    recuperacion: list
    escenarios: list
    escenarios_operativos: list
    sensibilidad: dict
    parametros: dict
    habilidades: dict
    operarios: list
    masa_chapa: dict = field(default_factory=dict)
    procedencia: dict = field(default_factory=dict)
    avisos: list = field(default_factory=list)

    def p(self, clave, defecto=None):
        return self.parametros.get(clave, defecto)

    def maquina_critica(self):
        return self.parametros.get("maquina_critica", "PLE-01")

    def nombre_maquina(self, m):
        base = str(m).split("#")[0]
        return self.maquinas[base].nombre if base in self.maquinas else str(m)


def _hora(txt, defecto):
    try:
        h, m = str(txt).strip().split(":")[:2]
        return dt.time(int(h), int(m))
    except (ValueError, AttributeError):
        return defecto


def tramos_jornada(txt):
    return [tuple(x.strip().split("-")) for x in str(txt).split(" y ")]


def parametros(tablas):
    par = {}
    for hoja in ("11_PARAMETROS", "28_CONFIG_MODELO"):
        for f in tablas.get(hoja, []):
            par[f["parametro_id"]] = f.get("valor_num") if f.get("valor_num") is not None else f.get("valor_txt")
    return par


def construir_datos(tablas, archivo, ajustes=None):
    par = parametros(tablas)
    par.update(ajustes or {})
    # ---------------- calendario
    aplicar_fer = int(par.get("aplicar_feriados") or 0) == 1
    dias = []
    for f in sorted(tablas["09_CALENDARIO"], key=lambda x: x["fecha"]):
        prod = f["laborable_base"] == 1 and not (aplicar_fer and f.get("feriado_nacional"))
        dias.append((f["fecha"].date(), prod))
    cal = Calendario(dias, tramos_jornada(par.get("jornada_productiva", "08:00-12:00 y 13:00-17:00")))
    # ---------------- maestros
    familias = {}
    for f in tablas["01_FAMILIAS"]:
        familias[f["familia_id"]] = dict(nombre=f["familia"], unidades=f["unidades_vendidas_2025"], ventas=f["ventas_2025_soles"],
                                         precio=f["ventas_2025_soles"] / f["unidades_vendidas_2025"],
                                         pen_fija=f["penalidad_fija_frac"], pen_diaria=f["penalidad_diaria_frac"])
    productos = {f["producto_id"]: dict(nombre=f["producto"], familia=f["familia_id"], tipo=f.get("tipo"), lote=f["lote_guia_und"])
                 for f in tablas["02_PRODUCTOS"]}
    maquinas = {f["recurso_id"]: Maquina(f["recurso_id"], f["recurso"], f["tipo_recurso"], f["cantidad"],
                                         f.get("costo_uso_soles_h") or 0.0, f["potencia_kw_ref"], f["factor_carga"],
                                         f.get("grupo_operarios") or "", f["recurso_critico"]) for f in tablas["05_RECURSOS"]}
    rutas = {}
    for f in tablas["06_RUTAS"]:
        rutas.setdefault(f["producto_id"], []).append(dict(
            paso=f["paso"], operacion=f["operacion"], maquina=f["recurso_id"], setup_min=f["min_fijos_lote"],
            min_unidad=f["min_por_unidad"], trato=f["tratamiento_tiempo"], predecesor=f.get("paso_predecesor"),
            interrumpible=f["interrumpible_en_pausas"], trabajadores=f["trabajadores_requeridos"], origen=f["origen_tiempo"]))
    for p in rutas:
        rutas[p].sort(key=lambda r: r["paso"])
    eleg = {}
    for f in tablas["07_ELEGIBILIDAD"]:
        if f["elegible"] != 1:
            continue
        eleg.setdefault((f["producto_id"], f["paso"]), []).append((f["recurso_id"], f["tipo_asignacion"], f["factor_tiempo"]))
    # ---------------- masa de chapa por producto (indicador de reproceso; misma fórmula que el Excel)
    mats = {f["material_id"]: f for f in tablas.get("03_MATERIALES", [])}
    masa = {}
    for f in tablas.get("04_DESPIECE", []):
        if f["tipo_calculo"] == "CHAPA_AREA" and f.get("area_chapa_m2_pieza") is not None:
            esp = (mats.get(f["material_id"]) or {}).get("espesor_mm") or 0.0
            masa[f["producto_id"]] = masa.get(f["producto_id"], 0.0) + \
                f["piezas_por_unidad"] * f["area_chapa_m2_pieza"] * esp / 1000 * float(par.get("densidad_acero", 7850))
    # ---------------- pedidos (simulados o reales)
    hl = _hora(par.get("hora_liberacion"), dt.time(8, 0))
    hv = _hora(par.get("hora_vencimiento"), dt.time(17, 0))
    fuente_ped = str(par.get("fuente_pedidos") or "SIMULADA")
    pedidos = []
    if fuente_ped == "REAL":
        for f in tablas.get("12_REG_ENTREGAS", []):
            fam = productos[f["producto_id"]]["familia"]
            precio = (f["precio_venta_soles"] / f["unidades"]) if f.get("precio_venta_soles") else familias[fam]["precio"]
            pen = f.get("penalidad_contractual_frac")
            pedidos.append(dict(id=f["pedido_real_id"], producto=f["producto_id"], familia=fam, q=f["unidades"],
                                lote=productos[f["producto_id"]]["lote"], recepcion=f["fecha_recepcion"],
                                liberacion=f["fecha_liberacion"], compromiso=f["fecha_compromiso"], precio=precio,
                                pen_frac=pen if pen is not None else familias[fam]["pen_fija"], naturaleza="REAL"))
    else:
        for f in tablas["20_PEDIDOS_SIM"]:
            fam = productos[f["producto_id"]]["familia"]
            pedidos.append(dict(id=f["pedido_id"], producto=f["producto_id"], familia=fam, q=f["unidades"], lote=f["lote_und"],
                                recepcion=f["fecha_recepcion"], liberacion=f["fecha_liberacion"],
                                compromiso=f["fecha_compromiso"], precio=familias[fam]["precio"],
                                pen_frac=familias[fam]["pen_fija"], naturaleza=f.get("naturaleza") or "SIMULADO"))
    for p in pedidos:
        p["liberacion_h"] = dt.datetime.combine(p["liberacion"].date(), hl)
        p["vencimiento_h"] = dt.datetime.combine(p["compromiso"].date(), hv)
    recalcular_pesos(pedidos)
    # ---------------- personal y habilidades
    operarios = [f["operario_id"] for f in tablas["08_PERSONAL"]]
    fuente_hab = str(par.get("fuente_habilidades") or "SIMULADA")
    hab = {w: set() for w in operarios}
    if fuente_hab == "REAL":
        for f in tablas.get("16_REG_HABILIDADES", []):
            if f["nivel_0_3"] >= 2 and f["opera_solo_1_0"] == 1 and f["operario_id"] in hab:
                hab[f["operario_id"]].add(f["recurso_id"])
    else:
        for f in tablas["22_HABILIDADES_SIM"]:
            w = f["operario_id"]
            hab.setdefault(w, set())
            for k, v in f.items():
                if k in maquinas and v == 1:
                    hab[w].add(k)
    # ---------------- eventos, escenarios, recuperación
    fallas = {}
    for f in tablas["23_EVENTOS_SIM"]:
        fallas[f["evento_id"]] = dict(evento=f["evento_id"], tipo=f["tipo_evento"], maquina=f["recurso_id"], inicio=f["inicio"],
                                      fin=f["inicio"] + dt.timedelta(hours=f["horas_reloj"]), horas_reloj=f["horas_reloj"],
                                      horas_turno=f["horas_turno_afectadas"], pedido=f.get("pedido_ref"), paso=f.get("paso_ref"),
                                      motivo=f.get("motivo"), naturaleza=f.get("naturaleza") or "SIMULADO")
    escenarios = [dict(id=f["escenario_id"], caso=f["caso"], eventos=[x for x in (f.get("eventos") or "").split("+") if x],
                       politica=f.get("politica_recuperacion") or "A", semilla=f["semilla"],
                       naturaleza=f.get("naturaleza") or "SIMULADO") for f in tablas["24_ESCENARIOS_FALLA_SIM"]]
    ope = [dict(id=f["escenario_id"], descripcion=f["descripcion"], factor_cantidad=f["factor_cantidad"],
                factor_plazo=f["factor_plazo"], ausentes=[x.strip() for x in (f.get("operarios_ausentes") or "").split(";") if x.strip()],
                eventos=[x for x in (f.get("eventos") or "").split("+") if x], politica=f.get("politica_recuperacion") or "A",
                naturaleza=f.get("naturaleza") or "SIMULADO") for f in tablas["27_ESCENARIOS_OPERATIVOS_SIM"]]
    recup = [dict(ambito=f["ambito"], producto=f.get("producto_id"), paso=f.get("paso"), politica=f["politica"],
                  conserva=f["conserva_piezas"], reinicia=f["reinicia_lote"], repite_setup=f["repite_setup"],
                  repetir=f.get("piezas_a_repetir") or 0, verif_min=f["min_verificacion"]) for f in tablas["25_RECUPERACION_SIM"]]
    sens = {f["factor_id"]: dict(factor=f["factor"], niveles=[x.strip() for x in str(f["niveles"]).split(";") if x.strip()],
                                 aplicado_a=f["aplicado_a"]) for f in tablas["26_SENSIBILIDAD_SIM"]}
    procedencia = dict(pedidos="REAL" if fuente_ped == "REAL" else "SIMULADO",
                       habilidades="REAL" if fuente_hab == "REAL" else "SIMULADO",
                       fallas="SIMULADO", tiempos_ruta=_naturaleza_tiempos(tablas))
    return Datos(archivo, familias, productos, maquinas, rutas, eleg, pedidos, cal, fallas, recup, escenarios, ope, sens, par,
                 hab, operarios, masa, procedencia)


def recalcular_pesos(pedidos):
    """valor_j, w_j (valor / valor medio), P_j (penalidad fija), penalidad diaria de sensibilidad y tope (fórmulas v1.4)."""
    for p in pedidos:
        p["valor"] = p["precio"] * p["q"]
        p["pen_fija"] = p["pen_frac"] * p["valor"]
    vm = sum(p["valor"] for p in pedidos) / max(1, len(pedidos))
    for p in pedidos:
        p["w"] = p["valor"] / vm if vm else 1.0
        p["plazo_dias"] = (p["compromiso"] - p["recepcion"]).days
        F = 0.40 if p["plazo_dias"] <= 60 else 0.25
        p["pen_dia_sens"] = p["pen_frac"] * p["valor"] / (F * max(1, p["plazo_dias"]))
        p["tope"] = p["pen_frac"] * p["valor"]


def _naturaleza_tiempos(tablas):
    origen = {f["origen_tiempo"] for f in tablas["06_RUTAS"]}
    return "REAL (cronometrado)" if origen == {"CRONOMETRADO"} else "ESTIMADO"


def cargar_base(ruta, ajustes=None, estricto=True):
    """Lee, valida y construye. ``ajustes`` reemplaza parámetros (p. ej. desde la línea de comandos)."""
    tablas, informe = leer_libro(ruta)
    if informe.ok:
        controlar(tablas, informe, ajustes or {})
    if estricto and not informe.ok:
        raise ErrorDatos(informe)
    if not informe.ok:
        return None, informe
    return construir_datos(tablas, ruta, ajustes), informe
