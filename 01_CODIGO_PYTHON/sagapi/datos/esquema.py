"""Esquema declarado de la base de datos SAGAPI (fuente única de verdad).

Lo usan:
  * el constructor del Excel (`herramientas/construir_base_final.py`) para escribir encabezados,
    formatos y validaciones;
  * el lector estricto (`sagapi.datos.lector`) para comprobar hojas, columnas, tipos y rangos;
  * el generador del diccionario de datos (`Diccionario_de_datos.xlsx`).

Tipos admitidos: texto, entero, binario, decimal, moneda, fraccion, fecha, fechahora, hora.
`derivada=True` indica una columna calculada por fórmula en el Excel: el programa no la usa como
entrada (puede recalcularla) y por eso SÍ puede contener fórmulas. Cualquier otra columna es de
ENTRADA y el lector rechaza que contenga fórmulas (evita lecturas silenciosas de valores vacíos).
"""
from __future__ import annotations

from dataclasses import dataclass, field

NATURALEZAS = ("REAL", "REFERENCIA", "CALCULADO", "ESTIMADO", "SIMULADO", "CONFIGURACION", "PENDIENTE")
NATURALEZA_DEF = {
    "REAL": "Dato declarado o respaldado por la empresa.",
    "REFERENCIA": "Dato público verificable ajeno a la empresa (ley, constante física, UIT, feriados oficiales).",
    "CALCULADO": "Resultado de una operación reproducible a partir de otros datos de la base.",
    "ESTIMADO": "Aproximación justificada que requiere validación en planta.",
    "SIMULADO": "Dato artificial para probar el modelo; no es historial ni registro de SAGAPI.",
    "CONFIGURACION": "Parámetro de ejecución del modelo o del experimento; no describe la planta.",
    "PENDIENTE": "Dato necesario que falta a propósito (ver pendientes de validación).",
}


@dataclass(frozen=True)
class Columna:
    nombre: str
    tipo: str = "texto"
    unidad: str = ""
    obligatorio: bool = True
    naturaleza: str = ""
    descripcion: str = ""
    minimo: float | None = None
    maximo: float | None = None
    dominio: tuple = ()
    derivada: bool = False
    uso_python: str = ""


@dataclass(frozen=True)
class Hoja:
    nombre: str
    grupo: str                     # OPERATIVA | SIMULACION | REGISTRO | DERIVADA | INDICE
    descripcion: str
    columnas: tuple
    clave: tuple = ()
    obligatoria: bool = True
    naturaleza: str = ""
    lee_python: bool = True

    def col(self, nombre):
        for c in self.columnas:
            if c.nombre == nombre:
                return c
        raise KeyError(f"{self.nombre}: columna {nombre} no declarada")

    @property
    def entradas(self):
        return [c for c in self.columnas if not c.derivada]


C = Columna
NAT = C("naturaleza", "texto", descripcion="Naturaleza principal de la fila (código de NATURALEZAS).",
        dominio=NATURALEZAS)
TIPOS_RECURSO = ("MAQUINA", "EQUIPO_MANUAL", "PUESTO_MANUAL", "AREA", "EXTERNO")
TIPOS_ASIG = ("PRINCIPAL", "ALT_UTILLAJE", "ALT_MISMO_PROCESO")
TRATAMIENTOS = ("POR_UNIDAD", "POR_LOTE")
ORIGENES_T = ("HEREDADO_SIN_CRONOMETRAJE", "HIPOTESIS_TECNICA", "CRONOMETRADO")
TIPOS_CALCULO = ("CHAPA_AREA", "PERFIL_LONGITUD", "UNIDAD", "SIN_PRECIO")
AMBITOS_REC = ("PRODUCTO_PASO", "GENERICO_POR_UNIDAD", "GENERICO_POR_LOTE")

HOJAS = [
    Hoja("01_FAMILIAS", "OPERATIVA", "Familias productivas, ventas agregadas 2025 y penalidades por atraso.", (
        C("familia_id", descripcion="Clave de familia."),
        C("familia", descripcion="Familia declarada por la empresa.", naturaleza="REAL"),
        C("unidades_vendidas_2025", "entero", "und", naturaleza="REAL", minimo=1,
          descripcion="Unidades agregadas 2025 (archivo de la empresa).", uso_python="precio medio → valor_j, w_j, P_j"),
        C("ventas_2025_soles", "moneda", "S/", naturaleza="REAL", minimo=0,
          descripcion="Ventas agregadas 2025 (archivo de la empresa).", uso_python="precio medio"),
        C("precio_promedio_soles", "moneda", "S/ por und", naturaleza="CALCULADO", derivada=True,
          descripcion="ventas / unidades (fórmula)."),
        C("penalidad_fija_frac", "fraccion", "fracción del valor", naturaleza="ESTIMADO", minimo=0, maximo=1,
          descripcion="Penalidad si el pedido se entrega tarde (sin cláusula verificada).", uso_python="P_j"),
        C("penalidad_diaria_frac", "fraccion", "fracción/día", naturaleza="ESTIMADO", minimo=0, maximo=1,
          descripcion="Penalidad diaria (0 = no aplica)."),
        NAT), clave=("familia_id",)),
    Hoja("02_PRODUCTOS", "OPERATIVA", "Catálogo de productos.", (
        C("producto_id", descripcion="Clave de producto."),
        C("familia_id", descripcion="Familia (01_FAMILIAS)."),
        C("producto", descripcion="Nombre del producto."),
        C("tipo", descripcion="Tipo comercial.", obligatorio=False),
        C("alto_cm", "decimal", "cm", naturaleza="ESTIMADO", minimo=0, obligatorio=False),
        C("ancho_cm", "decimal", "cm", naturaleza="ESTIMADO", minimo=0, obligatorio=False),
        C("fondo_cm", "decimal", "cm", naturaleza="ESTIMADO", minimo=0, obligatorio=False),
        C("puertas", "entero", "und", obligatorio=False, minimo=0, descripcion="Vacío = no aplica."),
        C("lote_guia_und", "entero", "und", naturaleza="ESTIMADO", minimo=1, maximo=1000,
          descripcion="Tamaño de lote de fabricación.", uso_python="lote por defecto"),
        C("n_componentes", "entero", derivada=True, obligatorio=False, naturaleza="CALCULADO"),
        C("n_pasos_ruta", "entero", derivada=True, obligatorio=False, naturaleza="CALCULADO"),
        C("dimensiones_genericas", "binario", derivada=True, obligatorio=False, naturaleza="CALCULADO",
          descripcion="1 si ≥5 productos comparten exactamente las mismas dimensiones (plantilla)."),
        NAT), clave=("producto_id",)),
    Hoja("03_MATERIALES", "OPERATIVA", "Maestro de materiales.", (
        C("material_id", descripcion="Clave técnica."), C("material"), C("grupo"), C("unidad_costo"),
        C("espesor_mm", "decimal", "mm", obligatorio=False, minimo=0),
        C("ancho_m", "decimal", "m", obligatorio=False, minimo=0), C("largo_m", "decimal", "m", obligatorio=False, minimo=0),
        C("costo_unitario_soles", "moneda", "S/", obligatorio=False, minimo=0, naturaleza="ESTIMADO"),
        C("material_generico", "binario"), NAT), clave=("material_id",)),
    Hoja("04_DESPIECE", "OPERATIVA", "Lista de materiales por producto.", (
        C("bom_id"), C("producto_id"), C("componente"), C("material_id"), C("tipo_calculo", dominio=TIPOS_CALCULO),
        C("piezas_por_unidad", "entero", "pzas", minimo=1),
        C("ancho_pieza_mm", "decimal", "mm", obligatorio=False, minimo=0),
        C("alto_pieza_mm", "decimal", "mm", obligatorio=False, minimo=0),
        C("longitud_pieza_m", "decimal", "m", obligatorio=False, minimo=0),
        C("area_chapa_m2_pieza", "decimal", "m²", obligatorio=False, minimo=0),
        C("masa_kg_producto", "decimal", "kg", derivada=True, obligatorio=False, naturaleza="CALCULADO",
          uso_python="masa de chapa por producto (indicador)"),
        C("costo_soles_producto", "moneda", "S/", derivada=True, obligatorio=False, naturaleza="CALCULADO"),
        C("planchas_equiv_producto", "decimal", "planchas", derivada=True, obligatorio=False, naturaleza="CALCULADO"),
        NAT), clave=("bom_id",)),
    Hoja("05_RECURSOS", "OPERATIVA", "Máquinas, puestos y áreas de trabajo.", (
        C("recurso_id", descripcion="Clave del recurso."), C("recurso", descripcion="Nombre."),
        C("tipo_tecnico", obligatorio=False), C("tipo_recurso", dominio=TIPOS_RECURSO, naturaleza="ESTIMADO"),
        C("cantidad", "entero", "und", minimo=0, maximo=20, naturaleza="ESTIMADO",
          descripcion="Unidades idénticas del recurso = capacidad simultánea.", uso_python="capacidad (unidades paralelas)"),
        C("costo_uso_soles_h", "moneda", "S/ por h", obligatorio=False, minimo=0, naturaleza="ESTIMADO",
          uso_python="costo de planificación (KPI)"),
        C("potencia_kw_ref", "decimal", "kW", minimo=0, naturaleza="ESTIMADO"),
        C("factor_carga", "fraccion", "fracción", minimo=0, maximo=1, naturaleza="ESTIMADO"),
        C("grupo_operarios", obligatorio=False), C("recurso_critico", "binario"),
        C("inventario_verificado", "binario", naturaleza="PENDIENTE"), NAT), clave=("recurso_id",)),
    Hoja("06_RUTAS", "OPERATIVA", "Rutas de fabricación y tiempos por operación.", (
        C("producto_id"), C("paso", "entero", minimo=1),
        C("operacion"), C("recurso_id", descripcion="Recurso principal."),
        C("paso_predecesor", "entero", obligatorio=False, minimo=1, descripcion="Vacío = primera operación."),
        C("min_fijos_lote", "decimal", "min por lote", minimo=0, maximo=480, naturaleza="ESTIMADO",
          uso_python="p_om = (⌈q/L⌉·s + q·u)/60"),
        C("min_por_unidad", "decimal", "min por und", minimo=0, maximo=600, naturaleza="ESTIMADO", uso_python="p_om"),
        C("tratamiento_tiempo", dominio=TRATAMIENTOS, uso_python="recuperación tras avería"),
        C("min_ciclo_horno_incluido", "decimal", "min", obligatorio=False, minimo=0),
        C("origen_tiempo", dominio=ORIGENES_T),
        C("trabajadores_requeridos", "entero", "personas", minimo=0, maximo=5, naturaleza="ESTIMADO",
          descripcion="Personas que atienden la operación durante toda su duración (sin dato real: 1).",
          uso_python="asignación de trabajadores"),
        C("interrumpible_en_pausas", "binario", naturaleza="ESTIMADO",
          descripcion="1 = puede continuar tras refrigerio/cierre; 0 = debe completarse en un tramo continuo "
                      "(ciclo de horno).", uso_python="restricción R12 (lote no partible)"),
        NAT), clave=("producto_id", "paso")),
    Hoja("07_ELEGIBILIDAD", "OPERATIVA", "Recursos elegibles por operación.", (
        C("producto_id"), C("paso", "entero", minimo=1), C("recurso_id", uso_python="conjunto M_o"),
        C("tipo_asignacion", dominio=TIPOS_ASIG), C("elegible", "binario"),
        C("factor_tiempo", "decimal", "×", minimo=0.1, maximo=5, naturaleza="ESTIMADO", uso_python="p_om alternativo"),
        NAT), clave=("producto_id", "paso", "recurso_id")),
    Hoja("08_PERSONAL", "OPERATIVA", "Trabajadores de producción (25 confirmados).", (
        C("operario_id", naturaleza="REAL"), C("turno", "entero", minimo=1, maximo=3, naturaleza="REAL"),
        C("hora_entrada", "hora", naturaleza="ESTIMADO"), C("hora_salida", "hora", naturaleza="ESTIMADO"),
        C("descanso_h", "decimal", "h", minimo=0, maximo=4, naturaleza="ESTIMADO"),
        C("horas_netas_dia", "decimal", "h", minimo=1, maximo=12, naturaleza="REAL"),
        C("control_horario_h", "decimal", "h", derivada=True, obligatorio=False, naturaleza="CALCULADO"),
        NAT), clave=("operario_id",)),
    Hoja("09_CALENDARIO", "OPERATIVA", "Calendario productivo.", (
        C("fecha", "fecha"), C("dia_semana", "entero", derivada=True, obligatorio=False),
        C("laborable_base", "binario", naturaleza="ESTIMADO", uso_python="días productivos"),
        C("feriado_nacional", obligatorio=False, naturaleza="REFERENCIA", uso_python="feriados si se aplican"),
        C("productivo_efectivo", "binario", derivada=True, obligatorio=False, naturaleza="CALCULADO"),
        C("horas_productivas", "decimal", "h", derivada=True, obligatorio=False, naturaleza="CALCULADO"),
        NAT), clave=("fecha",)),
    Hoja("10_CAPACIDAD_MENSUAL", "DERIVADA", "Horas disponibles por recurso y mes (fórmulas).", (
        C("recurso_id"), C("mes", "entero", minimo=1, maximo=12),
        C("dias_productivos", "entero", derivada=True, obligatorio=False),
        C("horas_dia", "decimal", derivada=True, obligatorio=False),
        C("cantidad", "entero", derivada=True, obligatorio=False),
        C("horas_disponibles", "decimal", "h", derivada=True, obligatorio=False), NAT),
        clave=("recurso_id", "mes"), lee_python=False),
    Hoja("11_PARAMETROS", "OPERATIVA", "Parámetros de planta.", (
        C("parametro_id"), C("parametro"), C("valor_num", "decimal", obligatorio=False),
        C("valor_txt", obligatorio=False), C("unidad", obligatorio=False), NAT,
        C("nota", obligatorio=False), C("usado_por_python", "binario")), clave=("parametro_id",)),
    Hoja("12_REG_ENTREGAS", "REGISTRO", "Pedidos y entregas REALES (vacía hasta que la empresa registre datos).", (
        C("pedido_real_id"), C("producto_id"), C("cliente_codigo", obligatorio=False), C("unidades", "entero", "und", minimo=1),
        C("fecha_recepcion", "fecha"), C("fecha_liberacion", "fecha"), C("fecha_compromiso", "fecha"),
        C("fecha_entrega", "fecha", obligatorio=False), C("unidades_conformes", "entero", obligatorio=False, minimo=0),
        C("unidades_no_conformes", "entero", obligatorio=False, minimo=0),
        C("precio_venta_soles", "moneda", obligatorio=False, minimo=0),
        C("penalidad_contractual_frac", "fraccion", obligatorio=False, minimo=0, maximo=1),
        C("causa_atraso", obligatorio=False), C("fuente_documento")), clave=("pedido_real_id",), obligatoria=False),
    Hoja("13_REG_PARADAS", "REGISTRO", "Paradas REALES de recursos.", (
        C("parada_id"), C("recurso_id"), C("inicio", "fechahora"), C("fin", "fechahora"),
        C("tipo_parada", dominio=("FALLA", "MANTENIMIENTO", "FALTA_MATERIAL", "FALTA_PERSONAL", "OTRO")),
        C("causa"), C("pedido_afectado", obligatorio=False), C("piezas_perdidas", "entero", obligatorio=False, minimo=0),
        C("registrado_por"), C("fuente_documento")), clave=("parada_id",), obligatoria=False, lee_python=False),
    Hoja("14_REG_CALIDAD", "REGISTRO", "Inspecciones REALES.", (
        C("inspeccion_id"), C("pedido_real_id"), C("producto_id"), C("fecha", "fecha"),
        C("cantidad_inspeccionada", "entero", minimo=0), C("conformes", "entero", minimo=0),
        C("no_conformes", "entero", minimo=0), C("defecto", obligatorio=False),
        C("reproceso_h", "decimal", obligatorio=False, minimo=0), C("material_perdido_soles", "moneda", obligatorio=False, minimo=0)),
        clave=("inspeccion_id",), obligatoria=False, lee_python=False),
    Hoja("15_REG_TIEMPOS", "REGISTRO", "Cronometraje REAL de operaciones.", (
        C("medicion_id"), C("producto_id"), C("paso", "entero", minimo=1), C("recurso_id"), C("fecha", "fecha"),
        C("unidades_medidas", "entero", minimo=1), C("min_preparacion_obs", "decimal", minimo=0),
        C("min_total_obs", "decimal", minimo=0), C("operarios_en_operacion", "entero", minimo=0),
        C("metodo", dominio=("CRONOMETRO", "VIDEO", "REGISTRO_OT")), C("observador")),
        clave=("medicion_id",), obligatoria=False, lee_python=False),
    Hoja("16_REG_HABILIDADES", "REGISTRO", "Habilidades REALES validadas por el jefe de planta.", (
        C("operario_id"), C("recurso_id"), C("nivel_0_3", "entero", minimo=0, maximo=3),
        C("opera_solo_1_0", "binario"), C("validado_por"), C("fecha_validacion", "fecha")),
        clave=("operario_id", "recurso_id"), obligatoria=False),
    Hoja("20_PEDIDOS_SIM", "SIMULACION", "96 pedidos SIMULADOS (reparten las unidades reales vendidas en 2025).", (
        C("pedido_id"), C("producto_id"), C("unidades", "entero", "und", minimo=1, maximo=10000, uso_python="q_j"),
        C("lote_und", "entero", "und", minimo=1, uso_python="lote"),
        C("fecha_recepcion", "fecha"), C("fecha_liberacion", "fecha", uso_python="r_j (08:00)"),
        C("fecha_compromiso", "fecha", uso_python="d_j (cierre del día)"),
        C("plazo_dias", "entero", derivada=True, obligatorio=False),
        C("liberacion_fin_semana", "binario", derivada=True, obligatorio=False),
        C("compromiso_fin_semana", "binario", derivada=True, obligatorio=False), NAT),
        clave=("pedido_id",), naturaleza="SIMULADO"),
    Hoja("21_PERFILES_SIM", "SIMULACION", "Especialidad SIMULADA de cada trabajador.", (
        C("operario_id"), C("especialidad_simulada"), NAT), clave=("operario_id",), naturaleza="SIMULADO"),
    Hoja("22_HABILIDADES_SIM", "SIMULACION", "Matriz de habilidades SIMULADA (operario × recurso, 1/0).", (
        C("operario_id"),), clave=("operario_id",), naturaleza="SIMULADO"),   # columnas de recurso: dinámicas
    Hoja("23_EVENTOS_SIM", "SIMULACION", "Fallas y mantenimientos SIMULADOS.", (
        C("evento_id"), C("tipo_evento", dominio=("FALLA", "MANTENIMIENTO_PLANIFICADO")), C("recurso_id"),
        C("inicio", "fechahora", uso_python="ventana (m, a, b)"), C("horas_reloj", "decimal", "h", minimo=0.01, maximo=720),
        C("fin", "fechahora", derivada=True, obligatorio=False),
        C("horas_turno_afectadas", "decimal", "h", minimo=0), C("motivo", obligatorio=False),
        C("pedido_ref", obligatorio=False), C("paso_ref", "entero", obligatorio=False), NAT),
        clave=("evento_id",), naturaleza="SIMULADO"),
    Hoja("24_ESCENARIOS_FALLA_SIM", "SIMULACION", "Escenarios de falla (combinaciones de eventos y política).", (
        C("escenario_id"), C("caso"), C("eventos", obligatorio=False, descripcion="Eventos separados por '+'."),
        C("politica_recuperacion", obligatorio=False, dominio=("A", "B")), C("semilla", "entero"), NAT),
        clave=("escenario_id",), naturaleza="SIMULADO"),
    Hoja("25_RECUPERACION_SIM", "SIMULACION", "Reglas de recuperación tras avería (hipótesis técnica).", (
        C("ambito", dominio=AMBITOS_REC), C("producto_id", obligatorio=False), C("paso", "entero", obligatorio=False),
        C("politica", dominio=("A", "B")), C("conserva_piezas", "binario"), C("reinicia_lote", "binario"),
        C("repite_setup", "binario"), C("piezas_a_repetir", "entero", obligatorio=False, minimo=0),
        C("min_verificacion", "decimal", "min", minimo=0, maximo=240), NAT), naturaleza="ESTIMADO"),
    Hoja("26_SENSIBILIDAD_SIM", "SIMULACION", "Factores y niveles del análisis de sensibilidad (los lee el programa).", (
        C("factor_id"), C("factor"), C("niveles", descripcion="Separados por ';'."), C("aplicado_a"), C("proposito"), NAT),
        clave=("factor_id",), naturaleza="CONFIGURACION"),
    Hoja("27_ESCENARIOS_OPERATIVOS_SIM", "SIMULACION", "Escenarios de carga, plazos, personal e indisponibilidad (SIMULADOS).", (
        C("escenario_id"), C("descripcion"), C("factor_cantidad", "decimal", minimo=0.1, maximo=5),
        C("factor_plazo", "decimal", minimo=0.1, maximo=5), C("operarios_ausentes", obligatorio=False),
        C("eventos", obligatorio=False), C("politica_recuperacion", obligatorio=False, dominio=("A", "B")), NAT),
        clave=("escenario_id",), naturaleza="SIMULADO"),
    Hoja("28_CONFIG_MODELO", "SIMULACION", "Configuración del modelo y del solucionador.", (
        C("parametro_id"), C("parametro"), C("valor_num", "decimal", obligatorio=False), C("valor_txt", obligatorio=False),
        C("unidad", obligatorio=False), NAT, C("nota", obligatorio=False), C("usado_por_python", "binario")),
        clave=("parametro_id",), naturaleza="CONFIGURACION"),
]
ESQUEMA = {h.nombre: h for h in HOJAS}

# Parámetros que el programa exige (id → (libro-hoja, tipo, dominio))
PARAMETROS_REQUERIDOS = {
    "trabajadores_produccion": ("11_PARAMETROS", "num", None),
    "jornada_productiva": ("11_PARAMETROS", "txt", None),
    "aplicar_feriados": ("11_PARAMETROS", "num", (0, 1)),
    "anio_base": ("11_PARAMETROS", "num", None),
    "hora_liberacion": ("11_PARAMETROS", "txt", None),
    "hora_vencimiento": ("11_PARAMETROS", "txt", None),
    "costo_hora_hombre": ("11_PARAMETROS", "num", None),
    "lote_no_cruza": ("11_PARAMETROS", "txt", ("TRAMO", "JORNADA")),
    "horizonte_congelado_h": ("11_PARAMETROS", "num", None),
    "fuente_habilidades": ("11_PARAMETROS", "txt", ("SIMULADA", "REAL")),
    "fuente_pedidos": ("11_PARAMETROS", "txt", ("SIMULADA", "REAL")),
    "regla_objetivo": ("28_CONFIG_MODELO", "txt", ("TARDANZA_PONDERADA", "PENALIDAD_FIJA", "PENALIDAD_DIARIA_CON_TOPE")),
    "beta_reasignacion": ("28_CONFIG_MODELO", "num", None),
    "maquina_critica": ("28_CONFIG_MODELO", "txt", None),
    "tolerancia_lexicografica": ("28_CONFIG_MODELO", "num", None),
    "limite_computo_s": ("28_CONFIG_MODELO", "num", None),
    "brecha_relativa": ("28_CONFIG_MODELO", "num", None),
    "limite_asignacion_personal_s": ("28_CONFIG_MODELO", "num", None),
}
