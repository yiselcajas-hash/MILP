"""Lectura y validación de la base Excel de SAGAPI.

Todo se lee por nombre de hoja y de encabezado (no por posición), y los valores que en el
libro son fórmulas se recalculan aquí a partir de sus datos de origen. Así el programa
funciona aunque el archivo haya sido guardado sin valores en caché (p. ej. generado por
openpyxl) y cualquier cambio de cantidades, tiempos o disponibilidad en el Excel se
propaga al modelo sin reorganizar datos a mano.
"""
from __future__ import annotations
import datetime as dt
import math
from dataclasses import dataclass, field
import openpyxl

from .calendario import Calendario

H = {  # nombres de hojas
    "prod": "01_PRODUCTOS", "maq": "04_MAQUINAS", "rut": "05_RUTAS", "ope": "06_OPERARIOS",
    "hab": "06B_HABILIDADES", "cal": "07_CALENDARIO", "ped": "08_PEDIDOS", "pre": "12_PRECIOS",
    "ele": "13_ELEGIBILIDAD", "fal": "14_FALLAS_ESC", "rec": "15_RECUPERACION",
    "base": "16_PROGRAMA_BASE", "esc": "18_ESCENARIOS", "par": "19_PARAMETROS",
    "mat": "03_DESPIECE", "sen": "27_SENSIBILIDAD",
}


class ErrorDatos(Exception):
    pass


def _tabla(wb, hoja, obligatoria=True):
    if hoja not in wb.sheetnames:
        if obligatoria:
            raise ErrorDatos(f"Falta la hoja obligatoria {hoja}")
        return []
    ws = wb[hoja]
    filas = list(ws.iter_rows(values_only=True))
    if not filas:
        return []
    enc = [str(c).strip() if c is not None else f"_c{j}" for j, c in enumerate(filas[0])]
    out = []
    for f in filas[1:]:
        if f is None or all(v is None for v in f):
            continue
        out.append({enc[j]: f[j] for j in range(min(len(enc), len(f)))})
    return out


def _num(v, defecto=None):
    if v is None or v == "":
        return defecto
    if isinstance(v, str) and v.startswith("="):
        return defecto
    try:
        return float(v)
    except (TypeError, ValueError):
        return defecto


def _col(fila, *nombres, defecto=None):
    for n in nombres:
        if n in fila and fila[n] is not None:
            return fila[n]
    return defecto


@dataclass
class Maquina:
    nombre: str
    clave: str
    cantidad: float
    costo_h: float
    potencia_kw: float = 0.0
    factor_carga: float = 0.0
    grupo_operario: str = ""


@dataclass
class Datos:
    archivo: str
    productos: dict
    maquinas: dict              # nombre -> Maquina
    rutas: dict                 # producto -> lista de pasos (dict)
    elegibilidad: dict          # (producto, paso) -> [(maquina, tipo, factor)]
    pedidos: list
    calendario: Calendario
    fallas: dict
    recuperacion: list
    escenarios: list
    parametros: dict
    habilidades: dict = field(default_factory=dict)   # operario -> set(maquinas)
    operarios: list = field(default_factory=list)
    programa_base: list = field(default_factory=list)
    masa_chapa: dict = field(default_factory=dict)    # producto -> kg de chapa por unidad
    sensibilidad: list = field(default_factory=list)
    avisos: list = field(default_factory=list)

    def maquina_critica(self):
        return self.parametros.get("Máquina de la avería", "Plegadora hidráulica de chapa metálica")


def _fecha(v):
    if isinstance(v, dt.datetime):
        return v
    if isinstance(v, dt.date):
        return dt.datetime.combine(v, dt.time())
    raise ErrorDatos(f"Fecha no válida: {v!r}")


def leer(archivo: str) -> Datos:
    wb = openpyxl.load_workbook(archivo, data_only=False)
    avisos = []

    # ---------------- parámetros ----------------
    par = {}
    for f in _tabla(wb, H["par"]):
        par[str(f.get("Parámetro")).strip()] = f.get("Valor")

    # ---------------- calendario ----------------
    aplicar_fer = _num(par.get("Aplicar feriados nacionales (1/0)"), 0) == 1
    dias = []
    for f in _tabla(wb, H["cal"]):
        d = _fecha(f["Fecha"]).date()
        p = _num(f.get("Productivo (1/0)"), 0) == 1
        fer = str(_col(f, "Feriado nacional Perú", defecto="") or "").strip()
        if aplicar_fer and fer and fer.lower() not in ("no", "-", "0"):
            p = False
        dias.append((d, p))
    dias.sort()
    ini = str(par.get("Jornada productiva") or "08:00-12:00 y 13:00-17:00")
    try:
        tramos = [tuple(x.strip().split("-")) for x in ini.split(" y ")]
        cal = Calendario(dias, tramos)
    except Exception:
        cal = Calendario(dias)
        avisos.append("Jornada productiva no interpretable; se usa 08:00-12:00 y 13:00-17:00")

    # ---------------- productos ----------------
    productos = {}
    for f in _tabla(wb, H["prod"]):
        nombre = f["Nombre completo"]
        if not nombre or nombre in productos:
            raise ErrorDatos(f"01_PRODUCTOS: producto vacío o duplicado: {nombre!r}")
        lote_guia = _num(f.get("Lote guía"), 10)
        if lote_guia is None or lote_guia <= 0:
            raise ErrorDatos(f"01_PRODUCTOS: lote guía inválido para {nombre!r}")
        productos[nombre] = dict(familia=f["Familia"], tipo=f.get("Tipo"),
                                               lote=lote_guia,
                                               alto=_num(f.get("Alto cm")), ancho=_num(f.get("Ancho cm")),
                                               fondo=_num(f.get("Fondo cm")))

    # ---------------- máquinas ----------------
    maquinas = {}
    for f in _tabla(wb, H["maq"]):
        n = f["Equipo o recurso completo"]
        cant = _num(f.get("Cantidad de escenario"), 0) or 0
        maquinas[n] = Maquina(n, f.get("Clave interna") or n, cant, _num(f.get("Costo de uso S//h"), 0) or 0,
                              _num(_col(f, "Potencia nominal kW (referencia)"), 0) or 0,
                              _num(_col(f, "Factor de carga medio"), 0) or 0,
                              str(_col(f, "Grupo de operarios", defecto="") or ""))

    # ---------------- rutas ----------------
    rutas = {}
    for f in _tabla(wb, H["rut"]):
        prod, paso = f["Producto"], int(f["Paso"])
        setup = _num(f.get("Min fijos por lote"))
        unidad = _num(f.get("Minutos por unidad"))
        if setup is None or unidad is None or setup < 0 or unidad < 0 or setup + unidad <= 0:
            raise ErrorDatos(f"05_RUTAS: tiempo vacío, negativo o nulo en {prod}, paso {paso}")
        rutas.setdefault(prod, []).append(dict(
            paso=paso, operacion=f["Operación"], maquina=f["Equipo principal"],
            setup_min=setup, min_unidad=unidad,
            prec=f.get("Precedencia"), trato=f.get("Tratamiento del tiempo"), origen=f.get("Origen de duración")))
    for p in rutas:
        rutas[p].sort(key=lambda r: r["paso"])
        for k, r in enumerate(rutas[p]):
            esperado = "Inicio" if k == 0 else rutas[p][k - 1]["paso"]
            pr = r["prec"]
            if not (pr == esperado or (_num(pr) is not None and _num(pr) == esperado)):
                raise ErrorDatos(f"Precedencia no lineal en {p} paso {r['paso']}: {pr}")

    # ---------------- elegibilidad ----------------
    ele = {}
    for f in _tabla(wb, H["ele"]):
        if _num(f.get("Elegible 1/0"), 1) != 1:
            continue
        fac = _num(_col(f, "Factor de tiempo relativo"), 1.0)
        if fac is None or fac <= 0:
            raise ErrorDatos(f"13_ELEGIBILIDAD: factor de tiempo no positivo en {f['Producto']}, paso {f['Paso']}")
        ele.setdefault((f["Producto"], int(f["Paso"])), []).append((f["Máquina elegible"], f.get("Tipo de asignación"), fac))

    # ---------------- precios y pedidos ----------------
    precios = {}
    for f in _tabla(wb, H["pre"]):
        u, v = _num(f.get("Unidades agregadas 2025")), _num(f.get("Ventas agregadas S/"))
        if u is None or v is None or u <= 0 or v < 0:
            raise ErrorDatos(f"12_PRECIOS: unidades o ventas inválidas para {f['Familia']}")
        precios[f["Familia"]] = dict(precio=v / u, pen_fija=_num(f.get("Penalidad fija %"), 0.10),
                                     pen_diaria=_num(f.get("Penalidad diaria %"), 0.0))
    pedidos = []
    for f in _tabla(wb, H["ped"]):
        fam = f["Familia"]
        prod = f["Producto"]
        q_raw = _num(f["Unidades"])
        if q_raw is None or q_raw <= 0 or not float(q_raw).is_integer():
            raise ErrorDatos(f"08_PEDIDOS: unidades inválidas en pedido {f['Pedido']}: {f['Unidades']!r}")
        q = int(q_raw)
        lote = _num(f.get("Lote"), None)
        if lote is None:
            lote = productos.get(prod, {}).get("lote")
        if lote is None or lote <= 0 or not float(lote).is_integer():
            raise ErrorDatos(f"08_PEDIDOS: tamaño de lote inválido en pedido {f['Pedido']}")
        rec = _fecha(f["Recepción 2025"]); lib = _fecha(f["Liberación 2025"]); com = _fecha(f["Compromiso 2025"])
        if fam not in precios:
            raise ErrorDatos(f"08_PEDIDOS: no se encontró precio de familia {fam!r}")
        pr = precios[fam]
        valor = pr["precio"] * q
        pedidos.append(dict(id=f["Pedido"], producto=prod, familia=fam, q=q, lote=int(lote), recepcion=rec,
                            liberacion=lib, compromiso=com, precio=pr["precio"], valor=valor,
                            pen_fija=pr["pen_fija"] * valor, pen_diaria_pct=pr["pen_diaria"],
                            clasificacion=f.get("Clasificación")))
    vm = sum(p["valor"] for p in pedidos) / len(pedidos)
    for p in pedidos:
        p["w"] = p["valor"] / vm
        p["plazo_dias"] = (p["compromiso"] - p["recepcion"]).days
        F = 0.40 if p["plazo_dias"] <= 60 else 0.25
        p["pen_dia_sens"] = 0.10 * p["valor"] / (F * max(1, p["plazo_dias"]))
        p["tope"] = 0.10 * p["valor"]

    # ---------------- fallas, recuperación, escenarios ----------------
    fallas = {}
    for f in _tabla(wb, H["fal"]):
        ini_f = _fecha(f["Inicio"])
        dur = _num(f["Horas de reloj"])
        if dur is None or dur <= 0:
            raise ErrorDatos(f"14_FALLAS_ESC: duración inválida en evento {f['Evento']!r}")
        if f["Evento"] in fallas:
            raise ErrorDatos(f"14_FALLAS_ESC: evento duplicado {f['Evento']!r}")
        fallas[f["Evento"]] = dict(evento=f["Evento"], inicio=ini_f, fin=ini_f + dt.timedelta(hours=dur), horas_reloj=dur,
                                   maquina=f["Equipo"], motivo=f.get("Motivo hipotético"),
                                   pedido=f.get("Pedido potencialmente afectado"), paso=f.get("Paso"),
                                   tipo=f.get("Tipo de dato"), horas_turno_excel=_num(f.get("Horas de turno afectadas")))
    recup = []
    for f in _tabla(wb, H["rec"]):
        recup.append(dict(producto=f["Producto"], paso=f.get("Paso"), operacion=f.get("Operación"), politica=str(f["Política"])[0],
                          conserva=_num(f.get("Conserva piezas"), 1), reinicia=_num(f.get("Reinicia lote"), 0),
                          repite_setup=_num(f.get("Repite setup"), 0),
                          repetir=_col(f, "Piezas a repetir por interrupción", defecto=0),
                          verif_min=_num(_col(f, "Min de verificación tras reparación"), 0) or 0))
    escenarios = []
    for f in _tabla(wb, H["esc"]):
        escenarios.append(dict(id=f["Escenario"], caso=f.get("Caso"), momento=f.get("Momento de falla"),
                               duracion=_num(f.get("Duración (h)"), 0), eventos=str(f.get("Evento") or ""),
                               politica=str(f.get("Recuperación") or "")[:1], semilla=f.get("Semilla"),
                               clasificacion=f.get("Clasificación")))

    # ---------------- operarios y habilidades (opcional) ----------------
    operarios = [f["Operario (seudónimo)"] for f in _tabla(wb, H["ope"])]
    hab = {}
    if H["hab"] in wb.sheetnames:
        ws = wb[H["hab"]]
        filas = list(ws.iter_rows(values_only=True))
        maqs = [c for c in filas[0][1:] if c and c not in ("Máquinas habilitadas", "Naturaleza")]
        for fila in filas[1:]:
            if not fila or not fila[0] or str(fila[0]).startswith(("Operarios habilitados", "=")):
                continue
            hab[fila[0]] = {maqs[j] for j in range(len(maqs)) if _num(fila[j + 1], 0) == 1}

    # ---------------- programa base (para comparar la regla convencional) ----------------
    base = []
    for f in _tabla(wb, H["base"], obligatoria=False):
        base.append(dict(pedido=f["Pedido"], paso=int(f["Paso"]), maquina=f["Máquina"],
                         inicio=_fecha(f["Inicio"]), fin=_fecha(f["Fin"]), dur=_num(f.get("Duración h"))))

    # ---------------- masa de chapa por producto (sostenibilidad) ----------------
    masa = {}
    for f in _tabla(wb, H["mat"], obligatoria=False):
        if "chapa" in str(f.get("Material", "")).lower() or "plancha" in str(f.get("Material", "")).lower() \
                or (_num(f.get("Área de chapa m²"), 0) or 0) > 0:
            masa[f["Producto"]] = masa.get(f["Producto"], 0.0) + (_num(f.get("Masa kg / producto"), 0) or 0)

    sens = _tabla(wb, H["sen"], obligatoria=False)

    d = Datos(archivo, productos, maquinas, rutas, ele, pedidos, cal, fallas, recup, escenarios, par,
              hab, operarios, base, masa, sens, avisos)
    validar(d)
    return d


def validar(d: Datos):
    """Comprobaciones de integridad referencial; lanza ErrorDatos ante inconsistencias que impiden correr el modelo."""
    err = []
    vistos = set()
    for p in d.pedidos:
        if p["id"] in vistos:
            err.append(f"Pedido duplicado: {p['id']}")
        vistos.add(p["id"])
        if p["producto"] not in d.rutas:
            err.append(f"Pedido {p['id']}: producto sin ruta ({p['producto']})")
        if p["compromiso"] < p["liberacion"]:
            err.append(f"Pedido {p['id']}: compromiso anterior a la liberación")
        if p["q"] <= 0:
            err.append(f"Pedido {p['id']}: cantidad no positiva")
        if p["producto"] in d.productos and p["familia"] != d.productos[p["producto"]]["familia"]:
            err.append(f"Pedido {p['id']}: familia no coincide con producto")
    for prod, pasos in d.rutas.items():
        ids = [r["paso"] for r in pasos]
        if len(ids) != len(set(ids)):
            err.append(f"Ruta {prod}: números de paso duplicados")
        for r in pasos:
            m = r["maquina"]
            if m not in d.maquinas or d.maquinas[m].cantidad < 1:
                err.append(f"Ruta {prod} paso {r['paso']}: recurso no disponible en 04_MAQUINAS ({m})")
            for (mm, _, _) in d.elegibilidad.get((prod, r["paso"]), []):
                if mm not in d.maquinas or d.maquinas[mm].cantidad < 1:
                    err.append(f"Elegibilidad {prod}/{r['paso']}: máquina inexistente ({mm})")
            if (prod, r["paso"]) in d.elegibilidad and m not in [x[0] for x in d.elegibilidad[(prod, r["paso"])]]:
                err.append(f"Elegibilidad {prod}/{r['paso']}: no incluye la máquina principal")
    for e, f in d.fallas.items():
        if f["maquina"] not in d.maquinas:
            err.append(f"Falla {e}: equipo inexistente ({f['maquina']})")
    if err:
        raise ErrorDatos("\n".join(err))
    return True


def duracion_h(paso: dict, q: int, lote: int, factor: float = 1.0) -> float:
    """Tiempo de procesamiento de un pedido en una operación (h) — misma fórmula que 09_CARGA_ORDEN:
    (ROUNDUP(q/lote)·min_fijos + q·min_unidad)/60, multiplicado por el factor de la máquina elegida."""
    return (math.ceil(q / lote) * paso["setup_min"] + q * paso["min_unidad"]) / 60.0 * factor
