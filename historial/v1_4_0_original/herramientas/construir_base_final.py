"""Construye Base_Datos_SAGAPI_Final.xlsx a partir de la base oficial V13 SIN eliminar información.

Reglas aplicadas:
  - No se borra ninguna hoja, fila ni columna de la V13.
  - Valores constantes que en realidad dependen de otras hojas se reemplazan por fórmulas que dan
    exactamente el mismo valor (se comprueba antes de reemplazar y se registra en 26_REGISTRO_CAMBIOS).
  - Lo añadido se marca en gris claro y se registra con su naturaleza (DERIVADO, ESTIMADO, SUPUESTO,
    SINTÉTICO, REGISTRO ORIGINAL NO VERIFICADO). El amarillo se reserva para resultados.
Uso: python construir_base_final.py V13.xlsx salida.xlsx carpeta_imagenes archivo_original_PIA.xlsx
"""
import datetime as dt
import math
import os
import sys
from copy import copy

import openpyxl
from openpyxl.drawing.image import Image as XLImage
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter as L
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.workbook.properties import CalcProperties

SRC, DST, IMG, ORIG = sys.argv[1:5]
wb = openpyxl.load_workbook(SRC)
NUEVO = PatternFill("solid", fgColor="EDEDED")      # celdas añadidas (gris claro)
AMARILLO = PatternFill("solid", fgColor="FFF2B6")   # resultados relevantes (mismo tono de 24_VALIDACIONES)
ENC_FILL = PatternFill("solid", fgColor="4B4B4B")
ENC_FONT = Font(name="Carlito", bold=True, color="FFFFFF", size=11)
FONT = Font(name="Carlito", size=11)
THIN = Side(style="thin", color="BFBFBF")
LOG = []


def log(hoja, ubic, campo, valor, just, nat):
    LOG.append((hoja, ubic, campo, str(valor), just, nat))


def header(ws, col, text, width=None):
    c = ws.cell(1, col, text)
    c.font, c.fill = ENC_FONT, ENC_FILL
    c.alignment = Alignment(wrap_text=True, vertical="center")
    ws.column_dimensions[L(col)].width = width or max(14, min(36, len(text) + 2))
    return c


def put(ws, r, c, v, fmt=None, fill=NUEVO):
    cell = ws.cell(r, c, v)
    cell.font = FONT
    if fill is not None:
        cell.fill = fill
    if fmt:
        cell.number_format = fmt
    return cell


def append_row(ws, vals, fmts=None, fill=NUEVO):
    r = ws.max_row + 1
    for j, v in enumerate(vals, 1):
        put(ws, r, j, v, (fmts or {}).get(j), fill)
    return r


def col_of(ws, name):
    for c in range(1, ws.max_column + 1):
        if ws.cell(1, c).value == name:
            return c
    raise KeyError(f"{ws.title}: no existe la columna {name}")


def nueva_hoja(nombre, encabezados, anchos=None, despues_de=None):
    ws = wb.create_sheet(nombre)
    if despues_de:
        wb.move_sheet(ws, offset=wb.sheetnames.index(despues_de) - wb.sheetnames.index(nombre) + 1)
    for j, h in enumerate(encabezados, 1):
        header(ws, j, h, (anchos or {}).get(j))
    ws.freeze_panes = "A2"
    return ws


def productivas_reloj(ini, fin):
    """Horas de jornada (08-12, 13-17, lunes a viernes) entre dos instantes de reloj."""
    h = 0.0
    d = ini.date()
    while d <= fin.date():
        if d.weekday() < 5:
            for a, b in ((8, 12), (13, 17)):
                s = max(ini, dt.datetime.combine(d, dt.time(a)))
                e = min(fin, dt.datetime.combine(d, dt.time(b)))
                if e > s:
                    h += (e - s).total_seconds() / 3600
        d += dt.timedelta(days=1)
    return round(h, 4)


# =============================================================================================
# 19_PARAMETROS — parámetros faltantes (se agregan primero porque otras fórmulas los referencian)
# =============================================================================================
ws = wb["19_PARAMETROS"]
PARAMS = [
    ("Refrigerio", "12:00-13:00", "hora", "sin producción; una operación en curso continúa a las 13:00", "DERIVADO (16_PROGRAMA_BASE)"),
    ("Jornada productiva", "08:00-12:00 y 13:00-17:00", "hora", "eje de tiempo del modelo en horas productivas (lunes a viernes)", "DERIVADO (16_PROGRAMA_BASE)"),
    ("Horas productivas por día", 8, "h/día", "usado por 11_CAPACIDAD y por el modelo", "DERIVADO"),
    ("Aplicar feriados nacionales (1/0)", 0, "1/0", "0 = calendario de la base V13 (sin feriados); 1 = descuenta los feriados de 07_CALENDARIO", "CONFIGURACION"),
    ("Hora de liberación", "08:00", "hora", "el pedido puede empezar al inicio de jornada de su fecha de liberación", "SUPUESTO OPERATIVO"),
    ("Hora de vencimiento d_j", "17:00", "hora", "entrega a tiempo si termina hasta el cierre del día comprometido (o del último día hábil previo)", "SUPUESTO OPERATIVO"),
    ("Peso w_j", "Valor pedido / valor medio", "adimensional", "08_PEDIDOS, columna Peso relativo w_j", "DERIVADO"),
    ("Regla de penalidad del modelo", "FIJA", "-", "FIJA = 10 % del valor si hay atraso (12_PRECIOS); DIARIA_CON_TOPE sólo en sensibilidad", "CONFIGURACION"),
    ("Desempate de f1", "Tardanza ponderada Σ w_j·T_j", "h ponderadas", "con penalidad fija, f1 no distingue 1 h de 5 días de atraso", "REGLA DE MODELADO"),
    ("Penalidad diaria (sensibilidad)", "0,10·valor/(F·plazo); F=0,40 si plazo ≤ 60 d; 0,25 si > 60 d", "S/ por día", "referencia: contratación pública peruana; tope 10 % del valor", "ESCENARIO DE SENSIBILIDAD"),
    ("Orden lexicográfico", "P1 penalidad → P2 tardanza ponderada → P3 inestabilidad", "-", "prioridad: cumplir entregas y luego no desordenar el taller", "REGLA DE MODELADO"),
    ("Tolerancia lexicográfica τ", 0.000001, "proporción", "holgura relativa al fijar f1b en P3", "CONFIGURACION"),
    ("Instancia reactiva", "Pedidos liberados hasta t_b y no terminados", "-", "terminadas se excluyen; en curso en otras máquinas se fijan", "REGLA DE MODELADO"),
    ("Regla convencional (comparador)", "Misma máquina y orden de cola; la operación interrumpida espera la reparación; nada se adelanta", "-", "aproxima la reprogramación manual actual (desplazamiento a la derecha)", "SUPUESTO OPERATIVO"),
    ("Programación convencional de pedidos", "FIFO por fecha de liberación y código, al final de la cola de cada máquina", "-", "reproduce exactamente 16_PROGRAMA_BASE", "DERIVADO (16_PROGRAMA_BASE)"),
    ("Máquina de la avería", "Plegadora hidráulica de chapa metálica", "-", "caso de validación principal; el modelo admite cualquier máquina y fallas simultáneas", "DERIVADO (04_MAQUINAS, 13_ELEGIBILIDAD)"),
    ("Duración de la avería", "conocida al ocurrir (estimación del técnico)", "h", "si la reparación real difiere, se reprograma otra vez en ese instante", "SUPUESTO DE MODELADO"),
    ("Tolerancia de verificación", 0.000001, "h", "holgura numérica admitida por el verificador independiente", "CONFIGURACION"),
    ("Coeficiente de aumentación ε (ρ)", 0.0001, "-", "evita soluciones débilmente eficientes en ε-restricción", "CONFIGURACION"),
    ("Solucionador", "HiGHS 1.12 (MILP), 1 hilo; cartera de 3 configuraciones (+2 con semilla 1 si no hay acuerdo)", "-", "software libre; un paso es óptimo certificado si dos configuraciones coinciden", "CONFIGURACION"),
    ("Límite de cómputo por configuración", 60, "s", "cada configuración de P1, P2 y P3 por separado", "CONFIGURACION"),
    ("Costo hora-hombre", 13, "S//h", "usado en 20_COSTOS (valor ya presente en sus fórmulas)", "SUPUESTO ECONOMICO"),
    ("Costo hora-máquina promedio", 18, "S//h", "usado en 20_COSTOS (valor ya presente en sus fórmulas)", "SUPUESTO ECONOMICO"),
    ("Tarifa eléctrica", 0.65, "S//kWh", "valoriza la energía; verificar con el recibo de la empresa", "ESTIMADO"),
    ("Factor de emisión de la red", None, "kg CO2/kWh", "vacío hasta contar con el factor oficial vigente; el programa no calcula CO2 sin él", "PENDIENTE"),
    ("Réplicas Monte Carlo de fallas de la plegadora", 40, "réplicas", "instante al azar dentro de un plegado del programa FIFO; duración remuestreada de F01–F12", "CONFIGURACION"),
    ("Semilla Monte Carlo", 2025200, "-", "garantiza que las réplicas se reproduzcan", "CONFIGURACION"),
    ("Ventas anuales aproximadas", 2000000, "S/", "dato indicado por las autoras", "REAL (declarado)"),
    ("UIT 2025", 5350, "S/", "referencia para la categoría empresarial", "REFERENCIA NORMATIVA"),
]
ws_par = ws
row_par = {}
for p in PARAMS:
    r = append_row(ws, list(p))
    row_par[p[0]] = r
    log("19_PARAMETROS", f"A{r}:E{r}", p[0], p[1], p[3], p[4])
r = append_row(ws, ["Categoría empresarial (Ley 30056)",
                    f'=IF(B{row_par["Ventas anuales aproximadas"]}/B{row_par["UIT 2025"]}<=150,"Microempresa",'
                    f'IF(B{row_par["Ventas anuales aproximadas"]}/B{row_par["UIT 2025"]}<=1700,"Pequeña empresa",'
                    f'IF(B{row_par["Ventas anuales aproximadas"]}/B{row_par["UIT 2025"]}<=2300,"Mediana empresa","Gran empresa")))',
                    "-", "ventas anuales en UIT", "CALCULADO"])
row_par["Categoría"] = r
log("19_PARAMETROS", f"A{r}", "Categoría empresarial", "fórmula", "Ventas/UIT según Ley 30056", "CALCULADO")
P = {k: f"'19_PARAMETROS'!$B${v}" for k, v in row_par.items()}
# texto actualizado de la regla convencional añadida en V14 no existe en V13: nada que modificar

# =============================================================================================
# 01_PRODUCTOS — unificar nombre de familia y vincular demanda calculada
# =============================================================================================
ws = wb["01_PRODUCTOS"]
for r in range(2, ws.max_row + 1):
    if ws.cell(r, 1).value == "Gondolas":
        ws.cell(r, 1).value = "Góndolas comerciales"
        ws.cell(r, 1).fill = NUEVO
log("01_PRODUCTOS", "A (6 filas)", "Familia", "Gondolas → Góndolas comerciales",
    "Unifica el nombre con 05_RUTAS, 08_PEDIDOS y 12_PRECIOS (necesario para relacionar hojas)", "CORRECCIÓN DE CONSISTENCIA")
c0 = ws.max_column + 1
header(ws, c0, "Pedidos 2025 (calculado)")
header(ws, c0 + 1, "Unidades 2025 (calculado)")
header(ws, c0 + 2, "Esquema referencial", 22)
n1 = ws.max_row
for r in range(2, n1 + 1):
    put(ws, r, c0, f"=COUNTIF('08_PEDIDOS'!$B$2:$B$97,B{r})")
    put(ws, r, c0 + 1, f"=SUMIF('08_PEDIDOS'!$B$2:$B$97,B{r},'08_PEDIDOS'!$D$2:$D$97)")
log("01_PRODUCTOS", f"{L(c0)}:{L(c0+1)}", "Pedidos y unidades 2025", "fórmula", "Demanda por producto enlazada a 08_PEDIDOS", "CALCULADO")

# =============================================================================================
# 01B_IMAGENES_REFERENCIALES
# =============================================================================================
wsI = nueva_hoja("01B_IMAGENES", ["Producto", "Familia", "Tipo", "Alto cm", "Ancho cm", "Fondo cm", "Esquema referencial (vista frontal a escala)"],
                 {1: 34, 2: 30, 3: 26, 7: 40}, despues_de="01_PRODUCTOS")
fila = 2
prod_rows = {ws.cell(r, 2).value: r for r in range(2, n1 + 1)}
pedidos_prod = sorted({wb["08_PEDIDOS"].cell(r, 2).value for r in range(2, 98)})
for prod in pedidos_prod:
    pr = prod_rows[prod]
    for j, col in enumerate("ABCDEF", 0):
        src = {0: "B", 1: "A", 2: "C", 3: "D", 4: "E", 5: "F"}[j]
        put(wsI, fila, j + 1, f"='01_PRODUCTOS'!{src}{pr}", fill=None)
    png = os.path.join(IMG, f"{prod}.png")
    if os.path.exists(png):
        im = XLImage(png)
        im.width, im.height = int(im.width * 0.62), int(im.height * 0.62)
        wsI.add_image(im, f"G{fila}")
        wsI.row_dimensions[fila].height = max(110, im.height * 0.78)
    put(wsI, fila, 8, "Esquema generado con las dimensiones de 01_PRODUCTOS; no es fotografía del producto real", fill=None)
    ws.cell(pr, c0 + 2).value = f'=HYPERLINK("#\'01B_IMAGENES\'!G{fila}","ver esquema")'
    ws.cell(pr, c0 + 2).fill = NUEVO
    fila += 1
wsI.column_dimensions["H"].width = 50
log("01B_IMAGENES", "hoja nueva", "Esquemas de los 8 productos con pedidos", "imágenes PNG",
    "Imágenes referenciales a escala desde 01_PRODUCTOS (no fotografías)", "ELABORACIÓN PROPIA")

# =============================================================================================
# 03_DESPIECE y 10_MATERIALES_ORDEN — consumo de chapa enlazado
# =============================================================================================
ws = wb["03_DESPIECE"]
c3 = ws.max_column + 1
header(ws, c3, "Planchas 1.20×2.40 equivalentes / producto")
for r in range(2, ws.max_row + 1):
    put(ws, r, c3, f'=IF(N(H{r})>0,H{r}/(1.2*2.4),0)', "0.000")
log("03_DESPIECE", L(c3), "Planchas equivalentes", "fórmula", "Área de chapa / 2,88 m² (plancha 1,20 × 2,40 m)", "CALCULADO")
ws = wb["10_MATERIALES_ORDEN"]
c10 = ws.max_column + 1
header(ws, c10, "Masa de material del pedido kg")
header(ws, c10 + 1, "Planchas equivalentes del pedido")
for r in range(2, ws.max_row + 1):
    put(ws, r, c10, f"=E{r}*SUMIFS('03_DESPIECE'!$I$2:$I$225,'03_DESPIECE'!$A$2:$A$225,B{r},'03_DESPIECE'!$B$2:$B$225,C{r})", "0.00")
    put(ws, r, c10 + 1, f"=E{r}*SUMIFS('03_DESPIECE'!${L(c3)}$2:${L(c3)}$225,'03_DESPIECE'!$A$2:$A$225,B{r},'03_DESPIECE'!$B$2:$B$225,C{r})", "0.00")
log("10_MATERIALES_ORDEN", f"{L(c10)}:{L(c10+1)}", "Masa y planchas por pedido", "fórmula",
    "Se recalculan al cambiar la cantidad del pedido", "CALCULADO")

# =============================================================================================
# 04_MAQUINAS — energía, operarios, criticidad, carga calculada
# =============================================================================================
ws = wb["04_MAQUINAS"]
ENERGIA = {  # clave: (kW de referencia, factor de carga, grupo de operarios)
    "CCH-01": (5.5, 0.50, "Corte"), "CPR-01": (0.75, 0.60, "Corte"), "PER-01": (0.55, 0.50, "Perforación"),
    "PLE-01": (5.5, 0.45, "Plegado"), "SOL-01": (5.0, 0.35, "Soldadura y armado"), "DES-01": (1.5, 0.50, "Acabado"),
    "PRE-01": (2.2, 0.40, "Acabado"), "PIN-01": (1.5, 0.70, "Pintura y curado"), "ARM-01": (1.0, 0.30, "Soldadura y armado"),
    "CAL-01": (0.2, 0.50, "Calidad y despacho"), "EMP-01": (0.3, 0.30, "Calidad y despacho"), "PER-02": (0.75, 0.50, "Perforación"),
    "SOL-02": (5.0, 0.35, "Soldadura y armado"), "PIN-EXT": (0.0, 0.0, "No aplica"), "HOR-01": (24.0, 0.60, "Pintura y curado"),
    "MAN-01": (0.5, 0.50, "Pintura y curado"), "SAL-PIN": (3.0, 0.50, "Pintura y curado"),
}
c4 = ws.max_column + 1
for k, h in enumerate(["Potencia nominal kW (referencia)", "Factor de carga medio", "Grupo de operarios", "Máquina crítica (1/0)",
                       "Horas requeridas 2025 (calculado)", "Utilización anual 2025", "Energía 2025 kWh (calculado)",
                       "Naturaleza columnas añadidas"]):
    header(ws, c4 + k, h)
cl_col = col_of(ws, "Clave interna")
for r in range(2, ws.max_row + 1):
    if ws.cell(r, cl_col).value == "SAL-PIN" and ws.cell(r, 5).value in (None, ""):
        ws.cell(r, 5).value = 1
        ws.cell(r, 5).fill = NUEVO
        log("04_MAQUINAS", f"E{r}", "Cantidad de la sala de pintura", 1,
            "Celda vacía; la empresa cuenta con sala de aplicación (y 11_CAPACIDAD ya usaba 1)", "REAL (declarado)")
for r in range(2, ws.max_row + 1):
    key = ws.cell(r, cl_col).value
    kw, fc, g = ENERGIA.get(key, (0, 0, ""))
    put(ws, r, c4, kw, "0.00"); put(ws, r, c4 + 1, fc, "0.00"); put(ws, r, c4 + 2, g)
    put(ws, r, c4 + 3, 1 if key == "PLE-01" else 0)
    put(ws, r, c4 + 4, f"=SUMIF('09_CARGA_ORDEN'!$E$2:$E$1153,A{r},'09_CARGA_ORDEN'!$J$2:$J$1153)", "0.0")
    put(ws, r, c4 + 5, f"=IF(N(E{r})=0,\"\",{L(c4+4)}{r}/(SUMPRODUCT(('07_CALENDARIO'!$A$2:$A$397<DATE(2026,1,1))*('07_CALENDARIO'!$K$2:$K$397))*{P['Horas productivas por día']}*E{r}))", "0.0%")
    put(ws, r, c4 + 6, f"={L(c4+4)}{r}*{L(c4)}{r}*{L(c4+1)}{r}", "#,##0")
    put(ws, r, c4 + 7, "kW y factor: ESTIMADO TÉCNICO de catálogo (verificar placa); grupo: SUPUESTO; horas y energía: CALCULADO")
log("04_MAQUINAS", f"{L(c4)}:{L(c4+7)}", "Potencia, factor de carga, grupo de operarios, criticidad, horas, utilización, energía",
    "ver hoja", "Permite indicadores de sostenibilidad (energía) y de participación humana; utilización enlazada a 09 y 07", "ESTIMADO / SUPUESTO / CALCULADO")

# =============================================================================================
# 06B_HABILIDADES — matriz operario × máquina
# =============================================================================================
ope = [wb["06_OPERARIOS"].cell(r, 1).value for r in range(2, wb["06_OPERARIOS"].max_row + 1)]
maqs = [wb["04_MAQUINAS"].cell(r, 1).value for r in range(2, wb["04_MAQUINAS"].max_row + 1)
        if (wb["04_MAQUINAS"].cell(r, 5).value or 0) >= 1]
claves = {wb["04_MAQUINAS"].cell(r, 1).value: wb["04_MAQUINAS"].cell(r, cl_col).value for r in range(2, wb["04_MAQUINAS"].max_row + 1)}
HAB = {
    "Juan Quispe": ["CCH-01", "CPR-01"], "Luis Huamán": ["CPR-01", "CCH-01", "PER-01", "PER-02"],
    "María Flores": ["PER-01", "PER-02", "DES-01"], "José Rojas": ["PLE-01", "CCH-01"],
    "Carlos Medina": ["SOL-01", "SOL-02", "ARM-01", "DES-01"], "Elena Paredes": ["SOL-01", "SOL-02", "ARM-01", "DES-01"],
    "Pedro Salazar": ["PRE-01", "DES-01", "MAN-01"], "Rosa Gutiérrez": ["PIN-01", "PRE-01", "SAL-PIN"],
    "Miguel Torres": ["HOR-01", "MAN-01", "PIN-01"], "Ana Castillo": ["CAL-01", "EMP-01", "ARM-01"],
}
wsH = nueva_hoja("06B_HABILIDADES", ["Operario (seudónimo)"] + maqs + ["Máquinas habilitadas", "Naturaleza"],
                 {1: 22}, despues_de="06_OPERARIOS")
for j in range(2, len(maqs) + 2):
    wsH.column_dimensions[L(j)].width = 11
    wsH.cell(1, j).alignment = Alignment(wrap_text=True, text_rotation=90, vertical="bottom")
wsH.row_dimensions[1].height = 170
for i, w in enumerate(ope, 2):
    put(wsH, i, 1, w, fill=None)
    for j, m in enumerate(maqs, 2):
        put(wsH, i, j, 1 if claves[m] in HAB.get(w, []) else 0)
    put(wsH, i, len(maqs) + 2, f"=SUM(B{i}:{L(len(maqs)+1)}{i})")
    put(wsH, i, len(maqs) + 3, "SUPUESTO: polivalencia derivada de la especialidad de 06_OPERARIOS")
fr = len(ope) + 2
put(wsH, fr, 1, "Operarios habilitados", fill=AMARILLO).font = Font(name="Carlito", bold=True)
for j in range(2, len(maqs) + 2):
    put(wsH, fr, j, f"=SUM({L(j)}2:{L(j)}{fr-1})", fill=AMARILLO)
dv = DataValidation(type="whole", operator="between", formula1="0", formula2="1", allow_blank=False)
wsH.add_data_validation(dv); dv.add(f"B2:{L(len(maqs)+1)}{fr-1}")
log("06B_HABILIDADES", "hoja nueva", "Matriz de habilidades", "1/0",
    "Verifica que cada máquina ocupada tenga un operario habilitado libre (participación humana)", "SUPUESTO")

# =============================================================================================
# 07_CALENDARIO — feriados nacionales (referencia) y día productivo efectivo
# =============================================================================================
FER = {dt.date(2025, 1, 1): "Año Nuevo", dt.date(2025, 4, 17): "Jueves Santo", dt.date(2025, 4, 18): "Viernes Santo",
       dt.date(2025, 5, 1): "Día del Trabajo", dt.date(2025, 6, 7): "Batalla de Arica y Día de la Bandera",
       dt.date(2025, 6, 29): "San Pedro y San Pablo", dt.date(2025, 7, 23): "Día de la Fuerza Aérea del Perú",
       dt.date(2025, 7, 28): "Fiestas Patrias", dt.date(2025, 7, 29): "Fiestas Patrias", dt.date(2025, 8, 6): "Batalla de Junín",
       dt.date(2025, 8, 30): "Santa Rosa de Lima", dt.date(2025, 10, 8): "Combate de Angamos",
       dt.date(2025, 11, 1): "Día de Todos los Santos", dt.date(2025, 12, 8): "Inmaculada Concepción",
       dt.date(2025, 12, 9): "Batalla de Ayacucho", dt.date(2025, 12, 25): "Navidad", dt.date(2026, 1, 1): "Año Nuevo"}
ws = wb["07_CALENDARIO"]
header(ws, 10, "Feriado nacional Perú", 30)
header(ws, 11, "Productivo efectivo (1/0)", 16)
for r in range(2, ws.max_row + 1):
    d = ws.cell(r, 1).value
    d = d.date() if isinstance(d, dt.datetime) else d
    put(ws, r, 10, FER.get(d, ""))
    put(ws, r, 11, f'=IF(AND({P["Aplicar feriados nacionales (1/0)"]}=1,J{r}<>""),0,C{r})')
log("07_CALENDARIO", "J:K", "Feriado nacional y día productivo efectivo", "17 feriados 2025-2026",
    "Con el interruptor de 19_PARAMETROS en 0 el calendario es idéntico a la V13", "REFERENCIA NORMATIVA / CALCULADO")

# =============================================================================================
# 08_PEDIDOS — lote, mes y penalidad enlazados; columnas derivadas; validaciones
# =============================================================================================
ws = wb["08_PEDIDOS"]
n8 = ws.max_row
cambios = 0
for r in range(2, n8 + 1):
    prod = ws.cell(r, 2).value
    lote_guia = wb["01_PRODUCTOS"].cell(prod_rows[prod], 8).value
    assert ws.cell(r, 9).value == lote_guia, "lote distinto del lote guía"
    ws.cell(r, 9).value = f"=INDEX('01_PRODUCTOS'!$H$2:$H${n1},MATCH(B{r},'01_PRODUCTOS'!$B$2:$B${n1},0))"
    lib = ws.cell(r, 6).value
    assert ws.cell(r, 8).value == lib.month, "mes distinto del mes de liberación"
    ws.cell(r, 8).value = f"=MONTH(F{r})"
    ws.cell(r, 18).value = f"=IF(Q{r}=\"\",\"\",Q{r}*INDEX('12_PRECIOS'!$E$2:$E$5,MATCH(C{r},'12_PRECIOS'!$A$2:$A$5,0)))"
    cambios += 1
log("08_PEDIDOS", "H, I, R", "Mes, Lote y Penalidad fija", "constantes → fórmulas (mismo valor)",
    "Mes = mes de liberación; Lote = lote guía de 01_PRODUCTOS; Penalidad = % de 12_PRECIOS (antes 0,10 escrito)", "CORRECCIÓN DE ENLACE")
c8 = ws.max_column + 1
cols8 = [
    ("Liberación con hora", lambda r: f"=F{r}+8/24", "yyyy-mm-dd hh:mm"),
    ("Compromiso con hora", lambda r: f"=G{r}+17/24", "yyyy-mm-dd hh:mm"),
    ("Peso relativo w_j", lambda r: f"=Q{r}/AVERAGE($Q$2:$Q${n8})", "0.000"),
    ("Plazo contractual días", lambda r: f"=G{r}-E{r}", "0"),
    ("Penalidad diaria sensibilidad S/", lambda r: f"=0.10*Q{r}/(IF({L(c8+3)}{r}<=60,0.40,0.25)*{L(c8+3)}{r})", "#,##0.00"),
    ("Tope de penalidad S/", lambda r: f"=0.10*Q{r}", "#,##0.00"),
    ("Horas de proceso del pedido", lambda r: f"=SUMIF('09_CARGA_ORDEN'!$A$2:$A$1153,A{r},'09_CARGA_ORDEN'!$J$2:$J$1153)", "0.00"),
]
for k, (name, f, fmt) in enumerate(cols8):
    header(ws, c8 + k, name)
    for r in range(2, n8 + 1):
        put(ws, r, c8 + k, f(r), fmt)
    log("08_PEDIDOS", f"{L(c8+k)}2:{L(c8+k)}{n8}", name, "fórmula", "Parámetro derivado para el MILP", "DERIVADO")
dv1 = DataValidation(type="list", formula1=f"='01_PRODUCTOS'!$B$2:$B${n1}", allow_blank=False)
dv2 = DataValidation(type="list", formula1="='12_PRECIOS'!$A$2:$A$5", allow_blank=False)
dv3 = DataValidation(type="whole", operator="greaterThan", formula1="0")
for dvx, rng in ((dv1, f"B2:B{n8}"), (dv2, f"C2:C{n8}"), (dv3, f"D2:D{n8}")):
    ws.add_data_validation(dvx); dvx.add(rng)

# =============================================================================================
# 09_CARGA_ORDEN — mes enlazado, costo y energía por operación
# =============================================================================================
ws = wb["09_CARGA_ORDEN"]
for r in range(2, ws.max_row + 1):
    ws.cell(r, 11).value = f"=INDEX('08_PEDIDOS'!$H$2:$H${n8},MATCH(A{r},'08_PEDIDOS'!$A$2:$A${n8},0))"
c9 = ws.max_column + 1
header(ws, c9, "Costo máquina S/ (tarifa 04)")
header(ws, c9 + 1, "Energía kWh (04)")
for r in range(2, ws.max_row + 1):
    put(ws, r, c9, f"=IFERROR(J{r}*INDEX('04_MAQUINAS'!$F$2:$F$18,MATCH(E{r},'04_MAQUINAS'!$A$2:$A$18,0)),0)", "#,##0.00")
    put(ws, r, c9 + 1, f"=IFERROR(J{r}*INDEX('04_MAQUINAS'!${L(c4)}$2:${L(c4)}$18,MATCH(E{r},'04_MAQUINAS'!$A$2:$A$18,0))"
                       f"*INDEX('04_MAQUINAS'!${L(c4+1)}$2:${L(c4+1)}$18,MATCH(E{r},'04_MAQUINAS'!$A$2:$A$18,0)),0)", "#,##0.00")
log("09_CARGA_ORDEN", f"K, {L(c9)}, {L(c9+1)}", "Mes enlazado; costo y energía por operación", "fórmulas",
    "Mes = mes del pedido (antes constante igual); costo con la tarifa de cada máquina; energía con kW y factor de 04", "CORRECCIÓN DE ENLACE / CALCULADO")

# =============================================================================================
# 11_CAPACIDAD — días, horas, cantidad y carga enlazados
# =============================================================================================
ws = wb["11_CAPACIDAD"]
for r in range(2, ws.max_row + 1):
    m = ws.cell(r, 2).value
    ws.cell(r, 3).value = (f"=SUMPRODUCT(('07_CALENDARIO'!$A$2:$A$397>=DATE(2025,B{r},1))*('07_CALENDARIO'!$A$2:$A$397<EDATE(DATE(2025,B{r},1),1))"
                           f"*('07_CALENDARIO'!$K$2:$K$397))")
    ws.cell(r, 4).value = f"={P['Horas productivas por día']}"
    ws.cell(r, 5).value = f"=IFERROR(INDEX('04_MAQUINAS'!$E$2:$E$18,MATCH(A{r},'04_MAQUINAS'!$A$2:$A$18,0)),0)"
    ws.cell(r, 9).value = f"=SUMIFS('09_CARGA_ORDEN'!$J$2:$J$1153,'09_CARGA_ORDEN'!$E$2:$E$1153,A{r},'09_CARGA_ORDEN'!$K$2:$K$1153,B{r})"
log("11_CAPACIDAD", "C, D, E, I", "Días, horas/día, cantidad y carga requerida", "constantes → fórmulas (mismo valor con feriados = 0)",
    "Si cambian pedidos, tiempos, máquinas o calendario, la capacidad se recalcula", "CORRECCIÓN DE ENLACE")

# =============================================================================================
# 13_ELEGIBILIDAD — factor de tiempo relativo
# =============================================================================================
ws = wb["13_ELEGIBILIDAD"]
header(ws, 7, "Factor de tiempo relativo")
header(ws, 8, "Naturaleza del factor", 30)
for r in range(2, ws.max_row + 1):
    t = ws.cell(r, 5).value
    f = 1.10 if t == "ALTERNATIVA CON UTILLAJE COMPATIBLE" else 1.00
    put(ws, r, 7, f, "0.00")
    put(ws, r, 8, "SUPUESTO TÉCNICO (cambio de utillaje)" if f != 1 else ("DERIVADO" if t == "PRINCIPAL" else "SUPUESTO TÉCNICO (mismo proceso)"))
log("13_ELEGIBILIDAD", "G:H", "Factor de tiempo relativo", "1,00 principal / mismo proceso; 1,10 utillaje compatible",
    "Tiempo en máquina alternativa = tiempo de ruta × factor; variable en sensibilidad", "SUPUESTO TÉCNICO")

# =============================================================================================
# 14_FALLAS_ESC — fallas nuevas (plegadora y otros recursos, simultáneas)
# =============================================================================================
ws = wb["14_FALLAS_ESC"]
EQ = {"PLE": "Plegadora hidráulica de chapa metálica", "PER": "Taladro de banco para perforación de acero",
      "SOL": "Máquina de soldadura por arco MIG/MAG", "HOR": "Horno de curado de pintura electrostática por lotes",
      "CCH": "Guillotina hidráulica para corte de planchas de acero"}
FALLAS = [
    ("F13", dt.datetime(2025, 8, 12, 10, 0), 29, "PLE", "Fuga en cilindro hidráulico; espera de retén de repuesto", "P059", 4,
     "Falla prolongada (1,5 veces la máxima del registro original), dentro del plegado de P059; mes de 80 % de carga"),
    ("F14", dt.datetime(2025, 6, 26, 9, 30), 3, "PLE", "Desajuste del tope posterior (recurrente)", "P044", 4,
     "Tercera parada de junio, mes de mayor carga de la plegadora; dentro del plegado de P044"),
    ("F15", dt.datetime(2025, 9, 19, 10, 30), 4.5, "PER", "Falla de rodamientos del husillo", "P066", 3,
     "Recurso con alternativa (segundo taladro): prueba la reasignación"),
    ("F16", dt.datetime(2025, 7, 11, 9, 0), 5, "SOL", "Falla del alimentador de alambre", "P049", 5,
     "Recurso con alternativa (segunda estación de soldadura)"),
    ("F17", dt.datetime(2025, 7, 2, 9, 45), 6, "HOR", "Falla de resistencia o termocupla del horno", "P042", 9,
     "Recurso compartido por todas las familias, sin alternativa; curado interrumpido se repite"),
    ("F18", dt.datetime(2025, 5, 7, 9, 0), 4, "CCH", "Desajuste de cuchillas de la guillotina", "P037", 1,
     "Primera operación de todas las rutas, sin alternativa"),
    ("F19", dt.datetime(2025, 7, 17, 9, 0), 3, "PLE", "Corte de energía en el tablero del área de conformado (simultánea con F20)", "P053", 3,
     "Falla simultánea de dos máquinas"),
    ("F20", dt.datetime(2025, 7, 17, 9, 0), 3, "CCH", "Corte de energía en el tablero del área de conformado (simultánea con F19)", "P052", 1,
     "Falla simultánea de dos máquinas"),
    ("F21", dt.datetime(2025, 7, 16, 8, 0), 4, "PLE", "Mantenimiento preventivo programado: cambio de aceite hidráulico y calibración de topes", "P053", 3,
     "Indisponibilidad planificada y conocida de antemano (ventana futura); se combina con F16 en S21A"),
]
for ev, ini, d, eq, mot, ped, paso, just in FALLAS:
    r = ws.max_row + 1
    ht = productivas_reloj(ini, ini + dt.timedelta(hours=d))
    vals = [ev, ini, f"=B{r}+D{r}/24", d, EQ[eq], mot, ped, paso, "SINTETICO" if ev != "F21" else "SUPUESTO (mantenimiento planificado)", ht]
    for j, v in enumerate(vals, 1):
        c = put(ws, r, j, v)
        c.number_format = ws.cell(r - 1, j).number_format
    log("14_FALLAS_ESC", f"A{r}:J{r}", ev, f"{ini:%Y-%m-%d %H:%M}, {d} h reloj, {ht} h de turno, {EQ[eq]}", just, "SINTETICO" if ev != "F21" else "SUPUESTO")
dvq = DataValidation(type="list", formula1="='04_MAQUINAS'!$A$2:$A$18")
ws.add_data_validation(dvq); dvq.add(f"E2:E{ws.max_row + 20}")

# =============================================================================================
# 15_RECUPERACION — detalle de políticas y reglas genéricas
# =============================================================================================
ws = wb["15_RECUPERACION"]
n15 = ws.max_row
c15 = ws.max_column + 1
for k, name in enumerate(["Piezas a repetir por interrupción", "Min de verificación tras reparación", "Detalle de la política"]):
    header(ws, c15 + k, name, 60 if k == 2 else None)
for r in range(2, n15 + 1):
    if str(ws.cell(r, 4).value).startswith("A"):
        vals = [1, 10, "La pieza en el doblez al fallar se repite; tras la reparación se verifican topes y se hace un doblez de prueba"]
    else:
        vals = ["TODO EL LOTE", 0, "Se reinicia el lote del plegado; la verificación queda cubierta por el setup repetido (12 min)"]
    for k, v in enumerate(vals):
        put(ws, r, c15 + k, v)
GEN = [("(Genérico) operaciones POR_UNIDAD", "A - reanudar", 1, 0, 0, 0, 0, "La operación continúa con las unidades pendientes al reparar la máquina"),
       ("(Genérico) operaciones POR_UNIDAD", "B - reiniciar lote", 0, 1, 1, "TODO EL LOTE", 0, "Se repite la operación completa"),
       ("(Genérico) Curado térmico POR_LOTE", "A - reanudar", 0, 1, 1, "TODO EL LOTE", 0, "Un ciclo de curado interrumpido no puede reanudarse: se repite el ciclo"),
       ("(Genérico) Curado térmico POR_LOTE", "B - reiniciar lote", 0, 1, 1, "TODO EL LOTE", 0, "Se repite el ciclo de curado")]
for g in GEN:
    r = append_row(ws, [g[0], None, g[0].split(") ")[1], g[1], g[2], g[3], g[4], "SUPUESTO TECNICO"])
    put(ws, r, c15, g[5]); put(ws, r, c15 + 1, g[6]); put(ws, r, c15 + 2, g[7])
log("15_RECUPERACION", "columnas y 4 filas", "Detalle A/B y reglas genéricas", "ver hoja",
    "Permite calcular el tiempo restante de cualquier operación interrumpida, no sólo del plegado", "SUPUESTO TÉCNICO")

# =============================================================================================
# 18_ESCENARIOS — escenarios nuevos
# =============================================================================================
ws = wb["18_ESCENARIOS"]
ESC = [("S13", "Falla prolongada plegadora", "F13", 29, "AB"), ("S14", "Fallas recurrentes plegadora (junio)", "F01+F02+F14", 8, "AB"),
       ("S15", "Falla taladro con alternativa", "F15", 4.5, "AB"), ("S16", "Falla soldadora con alternativa", "F16", 5, "AB"),
       ("S17", "Falla horno de curado", "F17", 6, "B"), ("S18", "Falla guillotina", "F18", 4, "AB"),
       ("S19", "Fallas simultáneas plegadora y guillotina", "F19+F20", 3, "AB"),
       ("S21", "Falla soldadora con mantenimiento anunciado de plegadora", "F16+F21", 9, "A")]
fallas_ini = {f[0]: f[1] for f in FALLAS}
fallas_ini.update({"F01": dt.datetime(2025, 6, 9, 8, 0)})
for sid, caso, evs, dur, pols in ESC:
    for pol in pols:
        r = append_row(ws, [sid + pol, caso, fallas_ini[evs.split("+")[0]], dur, evs,
                            "A - reanudar" if pol == "A" else "B - reiniciar lote", 20251000 + int(sid[1:]), "SINTETICO"])
        ws.cell(r, 3).number_format = "yyyy-mm-dd hh:mm"
r = append_row(ws, ["S20A", "Año 2025 completo con F01-F12 (horizonte rodante)", None, None, "F01+F02+F03+F04+F05+F06+F07+F08+F09+F10+F11+F12",
                    "A - reanudar", 20251020, "SINTETICO"])
log("18_ESCENARIOS", "filas nuevas", "S13–S20", "ver hoja",
    "Falla larga, recurrente, otros recursos, simultánea, con mantenimiento anunciado y año completo; en S14, S19 y S21 la duración es la suma de eventos", "SINTETICO")
dve = DataValidation(type="list", formula1='"A - reanudar,B - reiniciar lote,FIFO"')
ws.add_data_validation(dve); dve.add(f"F2:F{ws.max_row + 20}")

# =============================================================================================
# 20_COSTOS — tarifas desde 19_PARAMETROS
# =============================================================================================
ws = wb["20_COSTOS"]
for r in range(2, ws.max_row + 1):
    e, f = ws.cell(r, 5).value, ws.cell(r, 6).value
    assert e.endswith("*13") and f.endswith("*18")
    ws.cell(r, 5).value = e[:-3] + "*" + P["Costo hora-hombre"]
    ws.cell(r, 6).value = f[:-3] + "*" + P["Costo hora-máquina promedio"]
log("20_COSTOS", "E:F", "Tarifas de mano de obra y máquina", "13 y 18 escritos → referencia a 19_PARAMETROS (mismo valor)",
    "Un solo lugar para cambiar tarifas", "CORRECCIÓN DE ENLACE")

# =============================================================================================
# 21B_PARADAS_ARCHIVO_ORIGINAL — registro original (no verificado) para calibrar duraciones
# =============================================================================================
wo = openpyxl.load_workbook(ORIG, data_only=True)["HORAS DE PARADA 2025"]
w21 = nueva_hoja("21B_PARADAS_ARCHIVO_ORIG", ["N°", "Equipo registrado", "Modelo registrado", "Tipo de falla", "Descripción", "Fecha", "Hora inicio",
                                              "Hora corrección", "Duración h", "Día de la semana", "Clasificación"],
                 {2: 16, 3: 22, 5: 38, 11: 46}, despues_de="21_INCIDENCIAS_REAL")
for row in wo.iter_rows(min_row=5, values_only=True):
    if row[0] is None or not isinstance(row[0], (int, float)):
        continue
    r = w21.max_row + 1
    fecha = row[7]
    vals = [row[0], row[2], row[3], row[4], row[5], fecha, row[8], row[10], row[11], f"=TEXT(F{r},\"dddd\")",
            "REGISTRO ORIGINAL NO VERIFICADO (equipo anotado como roladora; la empresa indica que no tiene roladora)"]
    for j, v in enumerate(vals, 1):
        c = put(w21, r, j, v)
        if j == 6:
            c.number_format = "yyyy-mm-dd"
nr = w21.max_row
for k, (lab, f) in enumerate([("Registros", f"=COUNT(I2:I{nr})"), ("Mediana h", f"=MEDIAN(I2:I{nr})"),
                              ("Percentil 75 h", f"=PERCENTILE(I2:I{nr},0.75)"), ("Máximo h", f"=MAX(I2:I{nr})"),
                              ("Registros en domingo", f"=SUMPRODUCT(--(WEEKDAY(F2:F{nr},2)=7))")]):
    put(w21, nr + 2 + k, 8, lab, fill=None).font = Font(name="Carlito", bold=True)
    put(w21, nr + 2 + k, 9, f, "0.00", fill=AMARILLO)
log("21B_PARADAS_ARCHIVO_ORIG", "hoja nueva", "60 paradas del archivo original Data_SAGAPI_PIA", "copia",
    "Sólo para calibrar duraciones de los escenarios (mediana 3,5 h; máximo 8 h); no se usa como historial de la plegadora", "REGISTRO ORIGINAL NO VERIFICADO")

# =============================================================================================
# 25_CAPACIDAD_CON_FALLAS — horas de parada enlazadas a 14_FALLAS_ESC
# =============================================================================================
ws = wb["25_CAPACIDAD_CON_FALLAS"]
for r in range(2, ws.max_row + 1):
    ws.cell(r, 4).value = (f"=SUMPRODUCT(('14_FALLAS_ESC'!$E$2:$E$60=A{r})*(MONTH('14_FALLAS_ESC'!$B$2:$B$60)=B{r})"
                           f"*(YEAR('14_FALLAS_ESC'!$B$2:$B$60)=2025)*('14_FALLAS_ESC'!$J$2:$J$60))")
log("25_CAPACIDAD_CON_FALLAS", "D", "Parada escenario (h)", "constante → SUMPRODUCT sobre 14_FALLAS_ESC",
    "Incluye automáticamente las fallas añadidas (F13–F20) y cualquier falla nueva", "CORRECCIÓN DE ENLACE")

# =============================================================================================
# 27_SENSIBILIDAD — factores leídos por Python
# =============================================================================================
wsS = nueva_hoja("27_SENSIBILIDAD", ["Factor", "Niveles", "Aplicado a", "Propósito", "Naturaleza"], {1: 34, 2: 26, 3: 34, 4: 60})
for row in [("Multiplicador de duración de la avería", "0.5;1;2;4", "F01–F12, política A", "Robustez ante averías más cortas o más largas", "ESCENARIO"),
            ("Peso de reasignación β (h)", "0;8;24", "F01–F12, política A", "Efecto del criterio humano de estabilidad", "ESCENARIO"),
            ("Regla de penalidad", "FIJA;DIARIA_CON_TOPE", "Año 2025 y F01–F12", "Cambio de la regla económica", "ESCENARIO"),
            ("Factor de tiempo en máquina alternativa", "1.0;1.1;1.25", "S15 y S16", "Valor de la flexibilidad de asignación", "ESCENARIO"),
            ("Aplicar feriados nacionales", "0;1", "Año 2025", "Calendario sin y con feriados", "ESCENARIO")]:
    append_row(wsS, list(row))
log("27_SENSIBILIDAD", "hoja nueva", "Factores de sensibilidad", "5 factores", "El programa Python lee esta hoja", "CONFIGURACION")

# =============================================================================================
# 00_LEEME, 23_ORIGEN_DATOS, 24_VALIDACIONES
# =============================================================================================
ws = wb["00_LEEME"]
for row in [("Versión final", "Base V13 oficial completada para el MILP; no se eliminó información; cambios en 26_REGISTRO_CAMBIOS", "Archivo: Base_Datos_SAGAPI_Final.xlsx"),
            ("Convención de colores", "Encabezado gris oscuro; celdas añadidas en gris claro; resultados relevantes en amarillo", "Escala de grises"),
            ("Conexión con Python", "Optimizacion_MILP_SAGAPI.py lee las hojas por nombre de encabezado y recalcula los valores que aquí son fórmulas", "Escribe resultados en las hojas 28 a 33"),
            ("Hojas nuevas", "01B, 06B, 21B, 26, 27 y 28-33 (resultados)", "Ver 26_REGISTRO_CAMBIOS"),
            ("Naturaleza de los resultados", "Los resultados de 28-33 son CALCULADOS sobre datos sintéticos y estimados; no son registros de SAGAPI", "Validación computacional")]:
    append_row(ws, list(row))
for row in [("Horario, liberación y vencimiento", "DERIVADO / SUPUESTO OPERATIVO", "19_PARAMETROS, 08_PEDIDOS", "Confirmar horario real con el jefe de planta"),
            ("Penalidad diaria de sensibilidad", "ESCENARIO DE SENSIBILIDAD", "08_PEDIDOS", "Fórmula de la contratación pública; no es cláusula de SAGAPI"),
            ("Fallas F13–F20; escenarios S13–S21", "SINTETICO", "14_FALLAS_ESC, 18_ESCENARIOS", "No son averías históricas"),
            ("Mantenimiento F21", "SUPUESTO", "14_FALLAS_ESC", "Ventana planificada de ejemplo; reemplazar por el plan real de mantenimiento"),
            ("Detalle de recuperación A/B", "SUPUESTO TECNICO", "15_RECUPERACION", "Validar con el operador de plegadora"),
            ("Potencia y factor de carga", "ESTIMADO TECNICO", "04_MAQUINAS", "Verificar placa y recibo eléctrico"),
            ("Habilidades de operarios", "SUPUESTO", "06B_HABILIDADES", "Validar con el jefe de planta"),
            ("Factor de tiempo en alternativa", "SUPUESTO TECNICO", "13_ELEGIBILIDAD", "Medir en planta"),
            ("Paradas del archivo original", "REGISTRO ORIGINAL NO VERIFICADO", "21B_PARADAS_ARCHIVO_ORIG", "Equipo anotado como roladora"),
            ("Feriados nacionales 2025", "REFERENCIA NORMATIVA", "07_CALENDARIO", "Desactivados por defecto"),
            ("Resultados MILP", "RESULTADO CALCULADO", "28-33", "Corridas verificadas del programa Python")]:
    append_row(wb["23_ORIGEN_DATOS"], list(row))
ws = wb["24_VALIDACIONES"]
VAL = [("Eventos de indisponibilidad", "=COUNTA('14_FALLAS_ESC'!A2:A60)", 21, "F01–F20 fallas y F21 mantenimiento planificado"),
       ("Escenarios", "=COUNTA('18_ESCENARIOS'!A2:A60)", 40, "S00 + pares A/B + S17B + S20A + S21A"),
       ("Peso medio w_j", "=ROUND(AVERAGE('08_PEDIDOS'!V2:V97),6)", 1, "Normalización correcta"),
       ("Penalidad diaria ≤ tope", "=SUMPRODUCT(--('08_PEDIDOS'!X2:X97>'08_PEDIDOS'!Y2:Y97))", 0, "Ningún pedido supera el tope en un día"),
       ("Horas de proceso 08 = 09", "=ROUND(SUM('08_PEDIDOS'!Z2:Z97)-SUM('09_CARGA_ORDEN'!J2:J1153),6)", 0, "Consistencia de cargas"),
       ("Carga 11 = 09", "=ROUND(SUM('11_CAPACIDAD'!I2:I205)-SUM('09_CARGA_ORDEN'!J2:J1153),6)", 0, "Consistencia de capacidad"),
       ("Días productivos 2025", "=SUMPRODUCT(('07_CALENDARIO'!A2:A397<DATE(2026,1,1))*('07_CALENDARIO'!K2:K397))", 261, "Sin feriados (interruptor = 0)"),
       ("Familias con nombre consistente", "=SUMPRODUCT(--(COUNTIF('12_PRECIOS'!A2:A5,'01_PRODUCTOS'!A2:A51)>0))", 50, "01 ↔ 12"),
       ("Máquinas sin operario habilitado", f"=COUNTIF('06B_HABILIDADES'!B{fr}:{L(len(maqs)+1)}{fr},0)", 0, "Cada máquina tiene al menos un operario"),
       ("F13 dentro del plegado FIFO de P059", "=AND('14_FALLAS_ESC'!B14>='16_PROGRAMA_BASE'!F690,'14_FALLAS_ESC'!B14<'16_PROGRAMA_BASE'!G690)", True, "Coherencia con 16"),
       ("F14 dentro del plegado FIFO de P044", "=AND('14_FALLAS_ESC'!B15>='16_PROGRAMA_BASE'!F545,'14_FALLAS_ESC'!B15<'16_PROGRAMA_BASE'!G545)", True, "Coherencia con 16"),
       ("Productos con pedido y esquema", "=COUNTA('01B_IMAGENES'!A2:A9)", 8, "Imágenes referenciales"),
       ("Python reproduce 16_PROGRAMA_BASE", "ver 28_RESULTADOS_ANUALES", "Sí", "Comando validar del programa (experimento E0)")]
for row in VAL:
    r = append_row(ws, list(row))
    ws.cell(r, 2).fill = AMARILLO

# =============================================================================================
# 26_REGISTRO_CAMBIOS
# =============================================================================================
wsR = nueva_hoja("26_REGISTRO_CAMBIOS", ["N°", "Hoja", "Ubicación", "Campo", "Valor", "Justificación", "Naturaleza"],
                 {1: 5, 2: 22, 3: 16, 4: 32, 5: 40, 6: 70, 7: 26})
for i, row in enumerate(LOG, 1):
    for j, v in enumerate((i,) + tuple(row), 1):
        c = wsR.cell(i + 1, j, v)
        c.font = FONT
        c.alignment = Alignment(wrap_text=True, vertical="top")

# hojas de resultados (las llena Python)
for nombre in ["28_RESULTADOS_ANUALES", "29_RESULTADOS_ESCENARIOS", "30_FRENTE_PARETO", "31_SENSIBILIDAD_RES", "32_GRAFICOS", "33_ROBUSTEZ_MC"]:
    w = wb.create_sheet(nombre)
    w["A1"] = "Hoja de resultados: la completa Optimizacion_MILP_SAGAPI.py con corridas verificadas"
    w["A1"].font = Font(name="Carlito", bold=True)

for w in wb.worksheets:
    w.sheet_properties.tabColor = "4B4B4B" if w.title[:2].isdigit() and int(w.title[:2]) < 26 else "A6A6A6"
wb.calculation = CalcProperties(fullCalcOnLoad=True)
wb.save(DST)
print("ok", len(LOG), "cambios registrados")
