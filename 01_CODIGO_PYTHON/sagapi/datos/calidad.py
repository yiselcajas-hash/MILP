"""Controles automáticos de calidad entre hojas (se ejecutan antes de cualquier optimización).

Códigos (ERROR bloquea; ADVERTENCIA se informa):
  Q00–Q05 estructura, fórmulas, obligatorios, tipos y rangos (lector)
  Q06 claves duplicadas                    Q12 personal y jornada
  Q07 referencias inexistentes             Q13 eventos y escenarios
  Q08 rutas y elegibilidad                 Q14 parámetros requeridos y dominios
  Q09 capacidades y disponibilidad          Q15 carga anual frente a capacidad
  Q10 fechas de pedidos                    Q16 ventanas infactibles por construcción
  Q11 calendario                           Q17 uso de datos simulados o estimados
"""
from __future__ import annotations

import math
from collections import Counter, defaultdict

from .esquema import ESQUEMA, PARAMETROS_REQUERIDOS


def _dups(informe, hoja, filas, claves):
    c = Counter(tuple(f.get(k) for k in claves) for f in filas)
    for k, v in c.items():
        if v > 1 and all(x is not None for x in k):
            filas_k = [f["_fila"] for f in filas if tuple(f.get(x) for x in claves) == k]
            informe.error("Q06", hoja, filas_k[0], ",".join(claves), f"clave duplicada {k} en filas {filas_k}")


def _ref(informe, hoja, filas, col, dominio, destino, opcional=False):
    for f in filas:
        v = f.get(col)
        if v is None and opcional:
            continue
        if v not in dominio:
            informe.error("Q07", hoja, f["_fila"], col, f"{v!r} no existe en {destino}")


def controlar(t, informe, ajustes=None):
    from .carga import parametros, tramos_jornada
    par = parametros(t)
    par.update(ajustes or {})
    # ------------------------------------------------ Q06 duplicados
    for nombre, h in ESQUEMA.items():
        if h.clave and t.get(nombre):
            if nombre == "25_RECUPERACION_SIM":
                continue
            _dups(informe, nombre, t[nombre], h.clave)
    rec_k = Counter((f["ambito"], f.get("producto_id"), f.get("paso"), f["politica"]) for f in t["25_RECUPERACION_SIM"])
    for k, v in rec_k.items():
        if v > 1:
            informe.error("Q06", "25_RECUPERACION_SIM", None, "ambito,producto_id,paso,politica", f"regla duplicada {k}")
    # ------------------------------------------------ Q07 referencias
    fam = {f["familia_id"] for f in t["01_FAMILIAS"]}
    prod = {f["producto_id"] for f in t["02_PRODUCTOS"]}
    mat = {f["material_id"] for f in t.get("03_MATERIALES", [])}
    rec = {f["recurso_id"]: f for f in t["05_RECURSOS"]}
    per = {f["operario_id"] for f in t["08_PERSONAL"]}
    rutas = {(f["producto_id"], f["paso"]): f for f in t["06_RUTAS"]}
    ev = {f["evento_id"]: f for f in t["23_EVENTOS_SIM"]}
    _ref(informe, "02_PRODUCTOS", t["02_PRODUCTOS"], "familia_id", fam, "01_FAMILIAS")
    _ref(informe, "04_DESPIECE", t.get("04_DESPIECE", []), "producto_id", prod, "02_PRODUCTOS")
    _ref(informe, "04_DESPIECE", t.get("04_DESPIECE", []), "material_id", mat, "03_MATERIALES")
    _ref(informe, "06_RUTAS", t["06_RUTAS"], "producto_id", prod, "02_PRODUCTOS")
    _ref(informe, "06_RUTAS", t["06_RUTAS"], "recurso_id", rec, "05_RECURSOS")
    _ref(informe, "07_ELEGIBILIDAD", t["07_ELEGIBILIDAD"], "recurso_id", rec, "05_RECURSOS")
    for f in t["07_ELEGIBILIDAD"]:
        if (f["producto_id"], f["paso"]) not in rutas:
            informe.error("Q07", "07_ELEGIBILIDAD", f["_fila"], "producto_id,paso", "operación inexistente en 06_RUTAS")
    for hoja, col in (("20_PEDIDOS_SIM", "producto_id"), ("12_REG_ENTREGAS", "producto_id")):
        _ref(informe, hoja, t.get(hoja, []), col, prod, "02_PRODUCTOS")
    _ref(informe, "21_PERFILES_SIM", t["21_PERFILES_SIM"], "operario_id", per, "08_PERSONAL")
    _ref(informe, "22_HABILIDADES_SIM", t["22_HABILIDADES_SIM"], "operario_id", per, "08_PERSONAL")
    for f in t["22_HABILIDADES_SIM"][:1]:
        for k in f:
            if k not in ("_fila", "operario_id", "naturaleza") and k not in rec:
                informe.error("Q07", "22_HABILIDADES_SIM", 1, k, "columna de recurso inexistente en 05_RECURSOS")
    for f in t.get("16_REG_HABILIDADES", []):
        if f["operario_id"] not in per or f["recurso_id"] not in rec:
            informe.error("Q07", "16_REG_HABILIDADES", f["_fila"], "operario_id/recurso_id", "referencia inexistente")
    _ref(informe, "23_EVENTOS_SIM", t["23_EVENTOS_SIM"], "recurso_id", rec, "05_RECURSOS")
    peds = {f["pedido_id"] for f in t["20_PEDIDOS_SIM"]}
    _ref(informe, "23_EVENTOS_SIM", t["23_EVENTOS_SIM"], "pedido_ref", peds, "20_PEDIDOS_SIM", opcional=True)
    for hoja in ("24_ESCENARIOS_FALLA_SIM", "27_ESCENARIOS_OPERATIVOS_SIM"):
        for f in t[hoja]:
            for e in [x for x in (f.get("eventos") or "").split("+") if x]:
                if e not in ev:
                    informe.error("Q07", hoja, f["_fila"], "eventos", f"evento {e} inexistente en 23_EVENTOS_SIM")
    for f in t["27_ESCENARIOS_OPERATIVOS_SIM"]:
        for w in [x.strip() for x in (f.get("operarios_ausentes") or "").split(";") if x.strip()]:
            if w not in per:
                informe.error("Q07", "27_ESCENARIOS_OPERATIVOS_SIM", f["_fila"], "operarios_ausentes", f"{w} no existe en 08_PERSONAL")
    for f in t["25_RECUPERACION_SIM"]:
        if f["ambito"] == "PRODUCTO_PASO" and (f.get("producto_id"), f.get("paso")) not in rutas:
            informe.error("Q07", "25_RECUPERACION_SIM", f["_fila"], "producto_id,paso", "operación inexistente en 06_RUTAS")
    # ------------------------------------------------ Q08 rutas y elegibilidad
    por_prod = defaultdict(list)
    for f in t["06_RUTAS"]:
        por_prod[f["producto_id"]].append(f)
    for p, pasos in por_prod.items():
        pasos.sort(key=lambda r: r["paso"])
        if [r["paso"] for r in pasos] != list(range(1, len(pasos) + 1)):
            informe.error("Q08", "06_RUTAS", pasos[0]["_fila"], "paso", f"{p}: pasos no correlativos 1..n")
        for k, r in enumerate(pasos):
            esperado = None if k == 0 else pasos[k - 1]["paso"]
            if r.get("paso_predecesor") != esperado:
                informe.error("Q08", "06_RUTAS", r["_fila"], "paso_predecesor",
                              f"{p}/{r['paso']}: predecesor {r.get('paso_predecesor')} ≠ {esperado} (el modelo exige ruta lineal)")
            if (r["min_fijos_lote"] or 0) + (r["min_por_unidad"] or 0) <= 0:
                informe.error("Q08", "06_RUTAS", r["_fila"], "min_fijos_lote", "tiempo total nulo")
            if r["tratamiento_tiempo"] == "POR_LOTE" and (r["min_por_unidad"] or 0) != 0:
                informe.error("Q08", "06_RUTAS", r["_fila"], "min_por_unidad", "POR_LOTE con tiempo por unidad ≠ 0")
            if (r.get("min_ciclo_horno_incluido") or 0) > (r["min_fijos_lote"] or 0) + 1e-9:
                informe.error("Q08", "06_RUTAS", r["_fila"], "min_ciclo_horno_incluido",
                              "el ciclo de horno incluido supera el tiempo fijo del lote (unidades incoherentes)")
    for f in t.get("04_DESPIECE", []):
        a, h, area = f.get("ancho_pieza_mm"), f.get("alto_pieza_mm"), f.get("area_chapa_m2_pieza")
        if a is not None and h is not None and (area is None or abs(area - a * h / 1e6) > 1e-9):
            informe.error("Q08", "04_DESPIECE", f["_fila"], "area_chapa_m2_pieza",
                          f"área {area} ≠ ancho × alto = {a * h / 1e6:.6f} m² (unidades incoherentes)")
        if f["tipo_calculo"] == "CHAPA_AREA" and area is None:
            informe.error("Q08", "04_DESPIECE", f["_fila"], "area_chapa_m2_pieza", "línea de chapa sin área")
        if f["tipo_calculo"] == "PERFIL_LONGITUD" and f.get("longitud_pieza_m") is None:
            informe.error("Q08", "04_DESPIECE", f["_fila"], "longitud_pieza_m", "línea de perfil sin longitud")
    elig = defaultdict(list)
    for f in t["07_ELEGIBILIDAD"]:
        if f["elegible"] == 1:
            elig[(f["producto_id"], f["paso"])].append(f)
    for k, r in rutas.items():
        pr = [e for e in elig.get(k, []) if e["tipo_asignacion"] == "PRINCIPAL"]
        if elig.get(k) and (len(pr) != 1 or pr[0]["recurso_id"] != r["recurso_id"] or abs(pr[0]["factor_tiempo"] - 1) > 1e-12):
            informe.error("Q08", "07_ELEGIBILIDAD", r["_fila"], "tipo_asignacion",
                          f"{k}: la fila PRINCIPAL no coincide con el recurso de la ruta o su factor ≠ 1")
    # ------------------------------------------------ Q09 capacidades y disponibilidad laboral
    fuente_hab = str(par.get("fuente_habilidades") or "SIMULADA")
    hab = defaultdict(set)
    if fuente_hab == "REAL":
        for f in t.get("16_REG_HABILIDADES", []):
            if f["nivel_0_3"] >= 2 and f["opera_solo_1_0"] == 1:
                hab[f["recurso_id"]].add(f["operario_id"])
        if not t.get("16_REG_HABILIDADES"):
            informe.error("Q09", "16_REG_HABILIDADES", None, None, "fuente_habilidades = REAL pero el registro está vacío")
    else:
        for f in t["22_HABILIDADES_SIM"]:
            for k, v in f.items():
                if k in rec and v == 1:
                    hab[k].add(f["operario_id"])
    fuente_ped = str(par.get("fuente_pedidos") or "SIMULADA")
    tabla_ped = t.get("12_REG_ENTREGAS", []) if fuente_ped == "REAL" else t["20_PEDIDOS_SIM"]
    if fuente_ped == "REAL" and not tabla_ped:
        informe.error("Q10", "12_REG_ENTREGAS", None, None, "fuente_pedidos = REAL pero el registro está vacío")
    prod_con_ped = {f["producto_id"] for f in tabla_ped}
    for (p, paso), r in rutas.items():
        if p not in prod_con_ped:
            continue
        cand = [e["recurso_id"] for e in elig.get((p, paso), [])] or [r["recurso_id"]]
        if not any((rec[m]["cantidad"] or 0) >= 1 for m in cand if m in rec):
            informe.error("Q09", "06_RUTAS", r["_fila"], "recurso_id", f"{p}/{paso}: ningún recurso elegible con cantidad ≥ 1")
        crew = r["trabajadores_requeridos"]
        if crew and not any(len(hab[m]) >= crew for m in cand):
            informe.error("Q09", "06_RUTAS", r["_fila"], "trabajadores_requeridos",
                          f"{p}/{paso}: ningún recurso elegible tiene {crew} trabajador(es) habilitado(s)")
    # ------------------------------------------------ Q10 fechas de pedidos
    fechas = sorted(f["fecha"] for f in t["09_CALENDARIO"])
    fecha_ped = ("fecha_recepcion", "fecha_liberacion", "fecha_compromiso")
    for f in tabla_ped:
        a, b, c = (f.get(x) for x in fecha_ped)
        if None in (a, b, c):
            continue
        if not (a <= b <= c):
            informe.error("Q10", "20_PEDIDOS_SIM", f["_fila"], "fechas", "debe cumplirse recepción ≤ liberación ≤ compromiso")
        if fechas and (b < fechas[0] or c > fechas[-1]):
            informe.error("Q10", "20_PEDIDOS_SIM", f["_fila"], "fechas", "pedido fuera del horizonte de 09_CALENDARIO")
        if b.weekday() >= 5 or c.weekday() >= 5:
            informe.advertencia("Q10", "20_PEDIDOS_SIM", f["_fila"], "fechas",
                                "liberación o compromiso en fin de semana (se desplaza al día productivo)")
    # ------------------------------------------------ Q11 calendario
    if len(set(fechas)) != len(fechas):
        informe.error("Q11", "09_CALENDARIO", None, "fecha", "fechas repetidas")
    if any((y - x).days != 1 for x, y in zip(fechas, fechas[1:])):
        informe.error("Q11", "09_CALENDARIO", None, "fecha", "el calendario tiene días faltantes")
    if not any(f["laborable_base"] == 1 for f in t["09_CALENDARIO"]):
        informe.error("Q11", "09_CALENDARIO", None, "laborable_base", "no hay días laborables")
    try:
        tramos = tramos_jornada(par.get("jornada_productiva"))
        horas = sum((int(b[:2]) + int(b[3:5]) / 60) - (int(a[:2]) + int(a[3:5]) / 60) for a, b in tramos)
        largos = {round((int(b[:2]) + int(b[3:5]) / 60) - (int(a[:2]) + int(a[3:5]) / 60), 6) for a, b in tramos}
    except Exception:  # noqa: BLE001
        informe.error("Q14", "11_PARAMETROS", None, "jornada_productiva", "formato inválido (use 'HH:MM-HH:MM y HH:MM-HH:MM')")
        horas, largos = None, set()
    # ------------------------------------------------ Q12 personal
    if horas is not None:
        for f in t["08_PERSONAL"]:
            if abs(f["horas_netas_dia"] - horas) > 1e-6:
                informe.error("Q12", "08_PERSONAL", f["_fila"], "horas_netas_dia",
                              f"{f['horas_netas_dia']} h ≠ {horas} h de la jornada productiva (unidades incoherentes)")
            ctrl = (f["hora_salida"].hour + f["hora_salida"].minute / 60) - (f["hora_entrada"].hour + f["hora_entrada"].minute / 60) - f["descanso_h"]
            if abs(ctrl - f["horas_netas_dia"]) > 1e-6:
                informe.advertencia("Q12", "08_PERSONAL", f["_fila"], "hora_salida", "salida − entrada − descanso ≠ horas netas")
    n_trab = par.get("trabajadores_produccion")
    if n_trab is not None and len(t["08_PERSONAL"]) != int(n_trab):
        informe.error("Q12", "08_PERSONAL", None, "operario_id",
                      f"{len(t['08_PERSONAL'])} trabajadores ≠ {int(n_trab)} declarados en 11_PARAMETROS")
    if fuente_hab == "SIMULADA" and {f["operario_id"] for f in t["22_HABILIDADES_SIM"]} != per:
        informe.error("Q12", "22_HABILIDADES_SIM", None, "operario_id", "la matriz no cubre exactamente a los trabajadores de 08_PERSONAL")
    # ------------------------------------------------ Q13 eventos y escenarios
    for f in t["23_EVENTOS_SIM"]:
        if fechas and not (fechas[0] <= f["inicio"] <= fechas[-1]):
            informe.error("Q13", "23_EVENTOS_SIM", f["_fila"], "inicio", "evento fuera del calendario")
        if f.get("pedido_ref") and f.get("paso_ref"):
            pr = next((x for x in t["20_PEDIDOS_SIM"] if x["pedido_id"] == f["pedido_ref"]), None)
            if pr and (pr["producto_id"], f["paso_ref"]) in rutas:
                cand = [e["recurso_id"] for e in elig.get((pr["producto_id"], f["paso_ref"]), [])] or \
                       [rutas[(pr["producto_id"], f["paso_ref"])]["recurso_id"]]
                if f["recurso_id"] not in cand:
                    informe.advertencia("Q13", "23_EVENTOS_SIM", f["_fila"], "paso_ref",
                                        "el paso de referencia no se procesa en el recurso del evento")
    for hoja in ("24_ESCENARIOS_FALLA_SIM", "27_ESCENARIOS_OPERATIVOS_SIM"):
        for f in t[hoja]:
            evs = [ev[x] for x in (f.get("eventos") or "").split("+") if x in ev]
            for i, a in enumerate(evs):
                for b in evs[i + 1:]:
                    fa = a["inicio"].timestamp() + a["horas_reloj"] * 3600
                    fb = b["inicio"].timestamp() + b["horas_reloj"] * 3600
                    if a["recurso_id"] == b["recurso_id"] and a["inicio"].timestamp() < fb and b["inicio"].timestamp() < fa:
                        informe.error("Q13", hoja, f["_fila"], "eventos",
                                      f"{a['evento_id']} y {b['evento_id']} se solapan en {a['recurso_id']}")
            if evs and not f.get("politica_recuperacion"):
                informe.error("Q13", hoja, f["_fila"], "politica_recuperacion", "escenario con eventos sin política A/B")
    # ------------------------------------------------ Q14 parámetros
    for pid, (hoja, tipo, dom) in PARAMETROS_REQUERIDOS.items():
        v = par.get(pid)
        if v is None:
            informe.error("Q14", hoja, None, pid, "parámetro requerido ausente")
            continue
        if tipo == "num" and not isinstance(v, (int, float)):
            informe.error("Q14", hoja, None, pid, f"debe ser numérico: {v!r}")
        if dom and (v not in dom and not (tipo == "num" and float(v) in dom)):
            informe.error("Q14", hoja, None, pid, f"valor {v!r} fuera de {dom}")
    if par.get("lote_no_cruza") == "TRAMO" and len(largos) > 1:
        informe.advertencia("Q14", "11_PARAMETROS", None, "lote_no_cruza",
                            "tramos de distinta duración: la continuidad se aplica por JORNADA")
    # ------------------------------------------------ Q15/Q16 carga y ventanas (solo con pedidos y tiempos válidos)
    seg = None
    if horas:
        seg = min(largos) if (par.get("lote_no_cruza") == "TRAMO" and len(largos) == 1) else horas
    lote_def = {f["producto_id"]: f["lote_guia_und"] for f in t["02_PRODUCTOS"]}
    carga = defaultdict(float)
    for f in tabla_ped:
        p = f["producto_id"]
        lote = f.get("lote_und") or lote_def.get(p) or 1
        total = 0.0
        for r in sorted(por_prod.get(p, []), key=lambda x: x["paso"]):
            h = (math.ceil(f["unidades"] / lote) * r["min_fijos_lote"] + f["unidades"] * r["min_por_unidad"]) / 60
            total += h
            carga[r["recurso_id"]] += h
            if seg and r["interrumpible_en_pausas"] == 0 and h > seg + 1e-9:
                informe.error("Q09", "06_RUTAS", r["_fila"], "interrumpible_en_pausas",
                              f"{f.get('pedido_id', f.get('pedido_real_id'))}: operación no interrumpible de {h:.2f} h excede "
                              f"el tramo continuo de {seg:.2f} h (infactible)")
        if horas and f.get("fecha_liberacion") and f.get("fecha_compromiso"):
            dias = sum(1 for x in t["09_CALENDARIO"] if f["fecha_liberacion"] <= x["fecha"] <= f["fecha_compromiso"]
                       and x["laborable_base"] == 1)
            if total > dias * horas + 1e-9:
                informe.advertencia("Q16", "20_PEDIDOS_SIM", f["_fila"], "fecha_compromiso",
                                    f"{f.get('pedido_id')}: la ruta suma {total:.1f} h > {dias * horas:.0f} h disponibles hasta el "
                                    "compromiso: llegará tarde aun con la planta vacía")
    if horas:
        dias_anio = sum(1 for x in t["09_CALENDARIO"] if x["fecha"].year == int(par.get("anio_base") or 2025)
                        and x["laborable_base"] == 1)
        for m, h in carga.items():
            cap = dias_anio * horas * max(1, rec[m]["cantidad"] if m in rec else 1)
            if cap and h / cap > 1:
                informe.advertencia("Q15", "05_RECURSOS", None, m, f"carga anual {h:.0f} h > capacidad {cap:.0f} h")
    # ------------------------------------------------ Q17 naturaleza de los datos en uso
    if fuente_ped != "REAL":
        informe.info("Q17", "20_PEDIDOS_SIM", None, None, "se usan pedidos SIMULADOS (no son registros de SAGAPI)")
    if fuente_hab != "REAL":
        informe.info("Q17", "22_HABILIDADES_SIM", None, None, "se usa la matriz de habilidades SIMULADA")
    origen = Counter(f["origen_tiempo"] for f in t["06_RUTAS"])
    if set(origen) != {"CRONOMETRADO"}:
        informe.info("Q17", "06_RUTAS", None, "origen_tiempo", f"tiempos no cronometrados: {dict(origen)}")
    return informe
