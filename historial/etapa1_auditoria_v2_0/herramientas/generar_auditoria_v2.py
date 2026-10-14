#!/usr/bin/env python3
"""Genera el libro de auditoría de datos SAGAPI v2.0 (Entregables 2 y parte del 4).

Hojas: 1_MATRIZ_ERRORES · 2_PENDIENTES_VALIDACION · 3_MAPA_MIGRACION · 4_DEPENDENCIAS_PYTHON ·
5x_PROCEDENCIA (textos metodológicos y de procedencia retirados de la base operativa, conservados aquí).
Uso: python herramientas/generar_auditoria_v2.py [--original ...] [--salida entrega_v2_0/auditoria]
"""
from __future__ import annotations

import argparse
import os
import sys

import openpyxl

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bd_v2_comun import Col, escribir_tabla  # noqa: E402

# (id, hoja, celda/rango, categoría, problema, evidencia, severidad, acción, corrección o motivo, ubicación v2)
MATRIZ = [
    # ------------------------------------------------------------------ transversales
    ("E-001", "Libro completo", "25_CAPACIDAD_CON_FALLAS!D2:E205,G2:G205; 21B!I67", "Fórmula",
     "613 celdas con error #VALUE! guardadas en el archivo entregado.",
     "Recorrido de valores en caché: 612 en 25_CAPACIDAD_CON_FALLAS (MONTH sobre rango con vacíos) y 1 en 21B (WEEKDAY).",
     "ALTA", "ELIMINADO / REEMPLAZADO", "La hoja 25 se reemplaza por 25_PERDIDA_CAPACIDAD_ESC (por escenario, 0 errores); 21B se archiva.",
     "MODELO 25_PERDIDA_CAPACIDAD_ESC"),
    ("E-002", "24_VALIDACIONES", "B21:C21", "Control",
     "El control 'Familias con nombre consistente' devuelve 0 frente al objetivo 50 y nadie lo señaló.",
     "Valor en caché 0; COUNTIF con criterio matricial dentro de SUMPRODUCT no se evalúa como se pretendía.",
     "MEDIA", "CORREGIDO", "Columna auxiliar 'Familia válida (1/0)' en 01_PRODUCTOS y control = COUNTIF(...,0) → 0 (OK).",
     "MODELO 24_VALIDACIONES fila 8"),
    ("E-003", "24_VALIDACIONES", "B22", "Control / referencia rota",
     "'Máquinas sin operario habilitado' apunta a '06B_HABILIDADES'!B12:Q12, que hoy es la fila del operario OP-11 "
     "(la fila de totales pasó a la 27 al ampliar a 25 trabajadores). Resultado 13 frente a objetivo 0.",
     "Fórmula =COUNTIF('06B_HABILIDADES'!B12:Q12,0); fila 27 = 'Operarios habilitados'.",
     "MEDIA", "CORREGIDO", "Conteo por recurso con SUMPRODUCT sobre la matriz y control con COUNTIFS (0 = OK).",
     "MODELO 04_MAQUINAS col. K y 24_VALIDACIONES fila 11"),
    ("E-004", "24_VALIDACIONES", "B6, B26", "Control frágil",
     "B6 cuenta A2:A13 suponiendo que F01–F12 ocupan esas filas; B26 'Python reproduce' es un 'Sí' escrito a mano.",
     "Fórmulas por posición; valor literal.", "BAJA", "CORREGIDO",
     "Controles por contenido; la reproducción FIFO se verifica con herramientas/verificar_bd_v2.py (V09).",
     "MODELO 24_VALIDACIONES; E5"),
    ("E-005", "Varias (04, 07, 11, 20)", "fórmulas con '19_PARAMETROS'!$B$16/$B$17/$B$35/$B$36", "Fórmula frágil",
     "Las fórmulas leen parámetros por número de fila; insertar un parámetro desplaza la referencia sin error visible.",
     "Ej.: 07_CALENDARIO!K2 = IF(AND('19_PARAMETROS'!$B$17=1,...)).", "MEDIA", "CORREGIDO",
     "Nombres definidos (p_horas_productivas_dia, p_aplicar_feriados, p_costo_hora_hombre, ...).",
     "OPERATIVA 11_PARAMETROS; MODELO 19_PARAMETROS"),
    ("E-006", "Libro completo", "Formato de fechas", "Formato", "Fechas en dd/mm/yyyy, contrario a la norma AAAA-MM-DD.",
     "number_format 'dd/mm/yyyy' en 08_PEDIDOS!E2 y 'dd/mm/yyyy hh:mm' en 14_FALLAS_ESC!B2.", "BAJA", "CORREGIDO",
     "yyyy-mm-dd y yyyy-mm-dd hh:mm:ss en las tres bases.", "Todas"),
    ("E-007", "Libro completo", "Fuente y colores", "Formato",
     "Fuente Carlito y codificación de colores no documentada en la hoja (gris/amarillo).",
     "Font.name = 'Carlito'.", "BAJA", "CORREGIDO", "Arial; azul = dato introducido, negro = fórmula; leyenda en 00_CODIGOS.",
     "Todas"),
    ("E-008", "Libro completo", "Claves por nombre largo", "Modelo de datos",
     "Las relaciones se hacen por nombres largos (p. ej. 'Plegadora hidráulica de chapa metálica'); un cambio de "
     "redacción rompe rutas, elegibilidad, fallas y habilidades.", "05_RUTAS!E, 13_ELEGIBILIDAD!D, 14!E, 06B fila 1.",
     "MEDIA", "CORREGIDO (bases fuente) / CONSERVADO (MODELO)",
     "Claves cortas (PRD-001, CCH-01, MAT-LAC2, OP-01, BOM-0001). El MODELO conserva nombres porque Python 1.4.0 los usa.",
     "OPERATIVA y SIMULACION"),
    ("E-009", "Libro completo", "Nombre del archivo", "Trazabilidad",
     "'..._25_TRABAJADORES_SIMULADOS_...' sugiere que los 25 trabajadores son simulados; la cantidad es real y solo "
     "las habilidades son simuladas.", "06C_SUPUESTOS_PERSONAL!B2:C2 (25, DATO CONFIRMADO POR EMPRESA).", "BAJA",
     "CORREGIDO", "Nombres: SAGAPI_BD_OPERATIVA / SIMULACION / MODELO v2.0.", "Base de datos v2.0"),
    ("E-010", "Libro completo", "Entradas y resultados mezclados", "Arquitectura",
     "Las hojas 28–33 (resultados) viven dentro de la base de entrada y 'reportes --escribir-excel' sobrescribe el "
     "archivo de datos (reportes.py: wb.save(E.archivo)).", "sagapi/reportes.py líneas 388–515.", "ALTA",
     "REUBICADO", "Resultados fuera de la base; la corrección del código se planifica (plan maestro, M-05).",
     "E7 Plan maestro"),
    # ------------------------------------------------------------------ 00 / 01 / 01B
    ("E-011", "00_LEEME", "A1:C17", "Contenido no operativo",
     "Texto metodológico; cita el archivo 'Base_Datos_SAGAPI_Final.xlsx', que no corresponde al nombre real.",
     "00_LEEME!C13.", "BAJA", "REUBICADO", "Se archiva íntegro en 5A_LEEME_ORIGINAL; la base tiene 00_DICCIONARIO y 00_CODIGOS.",
     "Auditoría 5A"),
    ("E-012", "01_PRODUCTOS", "G2:G51 (44 celdas)", "Texto en campo numérico", "'No aplica' en 'Puertas'.",
     "44 celdas de texto.", "BAJA", "CORREGIDO", "Vacío (no aplica) y tipo entero.", "OPERATIVA 02_PRODUCTOS!H"),
    ("E-013", "01_PRODUCTOS", "D:F de 19 filas (20, 21, 24–36, 45–48)", "Dato de plantilla",
     "19 productos de 7 tipos (sillas, bancos, carros, archivadores, estanterías) comparten 85 × 120 × 60 cm; un "
     "banco de bar de 120 cm de ancho no es físico.", "Agrupación por (alto, ancho, fondo).", "MEDIA", "PENDIENTE",
     "No hay medidas reales; se marca dimensiones_genericas = 1 (fórmula). No afecta al MILP (sin pedidos).",
     "OPERATIVA 02_PRODUCTOS!L"),
    ("E-014", "01_PRODUCTOS", "H2:H51", "Supuesto", "Lote guía = 10 en los 50 productos (racks, sillas y lockers por igual).",
     "Valor único 10.", "ALTA", "PENDIENTE",
     "Afecta p_om vía ROUNDUP(q/lote)·setup; no hay dato. Clasificado ESTIMADO.", "OPERATIVA 02_PRODUCTOS!I"),
    ("E-015", "01_PRODUCTOS", "K:M", "Mezcla de entidades",
     "Demanda simulada (pedidos/unidades 2025) e hipervínculos a imágenes dentro del maestro de productos.",
     "Fórmulas COUNTIF/SUMIF sobre 08_PEDIDOS.", "BAJA", "ELIMINADO",
     "La demanda vive en la base de simulación; los recuentos de componentes y pasos se mantienen como fórmulas.",
     "OPERATIVA 02_PRODUCTOS!J:K"),
    ("E-016", "01_PRODUCTOS", "42 de 50 productos", "Alcance",
     "42 productos no tienen pedidos ni intervienen en el modelo; 6 de ellos tienen rutas de solo 2 pasos.",
     "COUNTIF de 08_PEDIDOS = 0; 05_RUTAS: sillas, escritorio Skala, bancos Brand/Aster con 2 pasos.", "BAJA",
     "CONSERVADO", "Se conservan como catálogo (ESTIMADO); el verificador exige ruta y despiece solo a productos con pedido.",
     "OPERATIVA 02_PRODUCTOS"),
    ("E-017", "01B_IMAGENES", "Hoja completa", "Contenido no operativo",
     "Esquemas generados (no fotografías), columna H sin encabezado y fórmulas que dependen del orden de 01; "
     "openpyxl pierde las imágenes al reescribir el libro y falta herramientas/img.", "01B!H1 = None; reportes.py reinsertaría "
     "imágenes desde una carpeta inexistente.", "BAJA", "ELIMINADO", "No aportan dato; se documenta.", "—"),
    # ------------------------------------------------------------------ 02 / 03
    ("E-018", "02_MATERIALES", "D8:D42, E3:F42 (114 celdas)", "Texto en campo numérico",
     "'Según especificación' en Espesor, Ancho y Largo.", "34 + 40 + 40 celdas de texto.", "MEDIA", "CORREGIDO",
     "Vacío (dato no especificado).", "OPERATIVA 03_MATERIALES!E:G"),
    ("E-019", "02_MATERIALES", "G10:G42 (33 de 41)", "Dato faltante", "33 materiales sin costo unitario.",
     "Celdas vacías.", "MEDIA", "PENDIENTE", "No hay cotizaciones; naturaleza = PENDIENTE (no se inventa precio).",
     "OPERATIVA 03_MATERIALES!H"),
    ("E-020", "02_MATERIALES", "B2:B42, C2:C42", "Vocabulario", "Grupos y unidades con mayúsculas y sinónimos mezclados "
     "(PERFIL/Perfil, HERRAJE/Herraje, m/metro, unidad).", "Valores distintos para lo mismo.", "BAJA", "CORREGIDO",
     "Vocabulario controlado (PERFIL, HERRAJE, m, und, l, m3, m2).", "OPERATIVA 03_MATERIALES!C:D"),
    ("E-021", "02_MATERIALES / 03_DESPIECE", "02!C8 (MAT-PR-1) frente a 03!J (perfiles)", "Unidades",
     "El perfil genérico se cotiza 'por m' (6,10), pero el costo de 03 se calcula como masa (kg) × 6,10 / 0,96.",
     "Ingeniería inversa: costo/(masa × 6,10) = 1/0,96 en las 58 líneas; costo/(longitud × 6,10) = 1/0,64.",
     "ALTA", "DOCUMENTADO / PENDIENTE",
     "Se explicita la fórmula vigente (precio aplicado por kg) y se pide confirmar la unidad del precio.",
     "OPERATIVA 04_DESPIECE!L; 2_PENDIENTES"),
    ("E-022", "02_MATERIALES", "G2:G7", "Supuesto", "Todas las chapas a 6,80 S/ por kg, sin distinguir laminado en caliente, "
     "LAF ni espesor.", "6 materiales CHAPA con el mismo precio.", "MEDIA", "PENDIENTE", "ESTIMADO.", "OPERATIVA 03_MATERIALES!H"),
    ("E-023", "02_MATERIALES", "MAT-PR-1, MAT-FIJ, MAT-OTR frente a COM-009…COM-027", "Duplicidad conceptual",
     "Materiales genéricos y específicos coexisten; el despiece usa solo los genéricos.", "Grupos PERFIL/HERRAJE.", "BAJA",
     "DOCUMENTADO", "material_generico = 1.", "OPERATIVA 03_MATERIALES!I"),
    ("E-024", "03_DESPIECE", "Productos lockers y góndolas con pedido", "Incoherencia técnica",
     "Lockers de 4 y 6 puertas usan chapa de 1,5 mm y góndolas de 1,0 mm ('alternativa V4'), aunque el catálogo indica "
     "LAF 0,6 mm (lockers) y 0,8 mm (góndolas): la masa y el costo de chapa pueden estar 1,25–2,5 veces sobrestimados.",
     "02_MATERIALES MAT-LAF06 'catálogo lockers', MAT-LAF08 'catálogo góndolas'; 03 filas 15–40.", "ALTA", "PENDIENTE",
     "No hay plano que decida el espesor real; se conserva y se pide validación.", "2_PENDIENTES"),
    ("E-025", "03_DESPIECE", "E2:G225 (437 celdas)", "Texto en campo numérico", "'No aplica' y 0 como 'no aplica' en "
     "Ancho, Alto y Longitud de pieza.", "157 + 157 + 123 celdas de texto.", "MEDIA", "CORREGIDO", "Vacío; tipo decimal.",
     "OPERATIVA 04_DESPIECE!G:I"),
    ("E-026", "03_DESPIECE", "I2:J225", "Supuesto oculto",
     "Masa y costo escritos como números sin fórmula, con supuestos implícitos: densidad 7 850 kg/m³, perfil 1,5 kg/m, "
     "aprovechamiento 0,92 (chapa) y 0,96 (perfil).", "Ingeniería inversa exacta en 150 líneas (diferencia máx. 7e-15).",
     "MEDIA", "RECONSTRUIDO",
     "Fórmulas explícitas con parámetros con nombre; reproducen los 150 valores originales (verificado).",
     "OPERATIVA 04_DESPIECE!K:L; 11_PARAMETROS"),
    ("E-027", "03_DESPIECE", "J (53 líneas MAT-FIJ)", "Dato calculable vacío",
     "Costo de tornillería, bisagras y cerraduras vacío pese a existir precio unitario (0,90 S/ por und).",
     "53 celdas vacías con material MAT-FIJ y precio en 02!G9.", "MEDIA", "RECONSTRUIDO",
     "costo = piezas × 0,90 (CALCULADO). La masa de herrajes queda vacía (no hay masa unitaria).",
     "OPERATIVA 04_DESPIECE!L"),
    ("E-028", "03_DESPIECE", "Bisagras y cerraduras", "Supuesto no representativo",
     "Bisagras y cerraduras de locker se costean con el herraje genérico de 0,90 S/; existen COM-020/COM-021 sin precio.",
     "03 filas de 'Bisagra', 'Cerradura'.", "MEDIA", "PENDIENTE", "Requiere cotización.", "2_PENDIENTES"),
    ("E-029", "03_DESPIECE", "K2:K225; 10_MATERIALES_ORDEN!K", "Error de cálculo",
     "'Planchas equivalentes / producto' = área de UNA pieza / 2,88; omite las piezas por unidad (subestima, p. ej. "
     "bandeja del minirack: 0,25 en lugar de 1,00 plancha).", "Fórmula =IF(N(H2)>0,H2/(1.2*2.4),0); H es área por pieza.",
     "MEDIA", "CORREGIDO", "Nueva fórmula: piezas × área / área de plancha (70 líneas cambian).", "OPERATIVA 04_DESPIECE!M"),
    ("E-030", "03_DESPIECE", "21 líneas MAT-OTR / MAT-MEL18", "Dato faltante",
     "Componentes comprados (asientos, ruedas, vidrio, melamina) sin costo ni masa.", "Celdas vacías.", "BAJA", "PENDIENTE",
     "Solo afectan a productos sin pedidos.", "2_PENDIENTES"),
    # ------------------------------------------------------------------ 04
    ("E-031", "04_MAQUINAS", "C2:D18, H2:H18", "Dato no verificado",
     "Marca y modelo 'del escenario' y 'Estatus físico = Referencia técnica comercial; no inventario certificado'.",
     "17 filas con el mismo texto.", "MEDIA", "REUBICADO",
     "Se archivan en 5E; la base agrega inventario_verificado = 0 (PENDIENTE).", "Auditoría 5E; OPERATIVA 05_RECURSOS!K"),
    ("E-032", "04_MAQUINAS", "F15 (PIN-EXT), F18 (SAL-PIN)", "Dato faltante",
     "Sin costo de uso; SAL-PIN no se usa en ninguna ruta y PIN-EXT tiene cantidad 0 (proveedor externo, no recurso).",
     "Celdas vacías; 0 rutas con SAL-PIN.", "BAJA", "DOCUMENTADO", "tipo_recurso = EXTERNO / AREA; costo vacío válido.",
     "OPERATIVA 05_RECURSOS"),
    ("E-033", "04_MAQUINAS", "Mesa de armado, áreas y zonas", "Realismo / modelado",
     "Puestos manuales y áreas (inspección, embalaje, preparación, armado) se modelan como máquinas de capacidad 1: el "
     "MILP prohíbe que dos pedidos se inspeccionen o armen a la vez aunque haya 25 personas.",
     "Restricciones disyuntivas R4–R5 por nombre de recurso (modelo.py).", "ALTA", "DOCUMENTADO / PENDIENTE",
     "Se añade tipo_recurso (ESTIMADO); la capacidad simultánea real se solicita.", "OPERATIVA 05_RECURSOS!D; E7 M-08"),
    ("E-034", "04_MAQUINAS", "F", "Riesgo de doble conteo",
     "No se sabe si el costo de uso por hora incluye al operario; 20_COSTOS suma además mano de obra.",
     "Columna sin definición.", "MEDIA", "PENDIENTE", "Pregunta en pendientes.", "2_PENDIENTES"),
    ("E-035", "04_MAQUINAS", "P2:P18", "Texto redundante", "Columna de naturaleza con el mismo párrafo en 17 filas.",
     "Texto idéntico.", "BAJA", "ELIMINADO", "Naturaleza por columna en 00_DICCIONARIO y por fila en 'naturaleza'.", "—"),
    ("E-036", "04_MAQUINAS", "Encabezado F 'Costo de uso S//h'", "Formato", "Doble barra en la unidad.", "Encabezado.",
     "BAJA", "CORREGIDO (fuente) / CONSERVADO (MODELO)", "costo_uso_soles_h; el MODELO mantiene el texto porque Python lo lee.",
     "OPERATIVA 05_RECURSOS!F"),
    # ------------------------------------------------------------------ 05 / 13
    ("E-037", "05_RUTAS", "F2:G407 (406 filas)", "Dato no verificado",
     "Ningún tiempo está cronometrado: 215 'VALOR HEREDADO SIN CRONOMETRAJE' y 191 'HIPOTESIS TECNICA'.",
     "Columna K.", "CRÍTICA", "PENDIENTE", "ESTIMADO; plantilla 15_REG_TIEMPOS para cronometrar (prioridad plegadora).",
     "OPERATIVA 06_RUTAS!J; 15_REG_TIEMPOS"),
    ("E-038", "05_RUTAS", "H2:H407", "Tipo mixto", "Precedencia mezcla el texto 'Inicio' con números.", "406 celdas.",
     "BAJA", "CORREGIDO (fuente) / CONSERVADO (MODELO)", "paso_predecesor entero (vacío = primera operación).",
     "OPERATIVA 06_RUTAS!E"),
    ("E-039", "05_RUTAS", "B, L", "Redundancia", "Familia (derivable del producto) y 'Clave de unión' (Producto|Paso).",
     "Concatenación.", "BAJA", "ELIMINADO (fuente)", "Se derivan cuando hace falta.", "—"),
    ("E-040", "05_RUTAS", "Rutas de productos con pedido", "Modelado",
     "Precedencia estrictamente lineal: corte de planchas y corte de tubos (materiales distintos) no pueden solaparse "
     "y cada operación espera el lote completo anterior (sin lotes de transferencia).",
     "Precedencia k = k−1 en 406 filas.", "ALTA", "DOCUMENTADO", "Requiere datos de flujo real; ver E6/E7 (M-09).",
     "E6 C-06"),
    ("E-041", "05_RUTAS", "56 filas (36 PER-02, 20 SOL-02)", "Incoherencia",
     "El 'Segundo taladro (alternativo)' y la 'Segunda estación (alternativa)' son recurso PRINCIPAL en 56 pasos de "
     "productos sin pedidos.", "05_RUTAS!E99, E107, E116, …", "BAJA", "DOCUMENTADO",
     "Sin efecto en el MILP actual; se señala para la validación del catálogo.", "OPERATIVA 06_RUTAS"),
    ("E-042", "05_RUTAS / 19_PARAMETROS", "Curado: 45 min por lote; 19!B11 '10 piezas'", "Unidades",
     "La capacidad del horno se declara en 10 PIEZAS por carga, pero el lote es de 10 UNIDADES de producto "
     "(un minirack tiene 12 piezas de chapa y 12 de perfil).", "19_PARAMETROS fila 11; 01_PRODUCTOS!H.", "ALTA",
     "PENDIENTE", "Se conserva el valor y se pide la capacidad real del horno (m², colgadores o piezas).", "2_PENDIENTES"),
    ("E-043", "13_ELEGIBILIDAD", "C, H", "Redundancia", "Operación repetida de 05 y naturaleza en texto largo.",
     "473 filas.", "BAJA", "CORREGIDO", "Códigos ALT_UTILLAJE / ALT_MISMO_PROCESO y naturaleza por fila.",
     "OPERATIVA 07_ELEGIBILIDAD"),
    ("E-044", "13_ELEGIBILIDAD", "Factor 1,10 (44 filas)", "Supuesto", "Factor de tiempo en máquina alternativa sin medición.",
     "SUPUESTO TÉCNICO.", "MEDIA", "PENDIENTE", "ESTIMADO.", "OPERATIVA 07_ELEGIBILIDAD!F"),
    # ------------------------------------------------------------------ 06 / 06B / 06C
    ("E-045", "06_OPERARIOS", "B:I", "Mezcla real/simulado",
     "La fila de cada trabajador mezcla datos reales (existencia, turno, 8 h) con la especialidad simulada y textos "
     "('Según 07_CALENDARIO (supuesto)', horas como texto '08:00').", "C2:C26 texto; D:E texto; I párrafo repetido.",
     "MEDIA", "SEPARADO", "Real → OPERATIVA 08_PERSONAL (horas como hora); especialidad → SIMULACION 02_PERFILES_SIM.",
     "OPERATIVA 08_PERSONAL; SIMULACION 02_PERFILES_SIM"),
    ("E-046", "06B_HABILIDADES", "B2:Q26", "Dato simulado", "La matriz de habilidades completa es simulada.",
     "S2:S26 'SUPUESTO SIMULADO; NO CERTIFICACIÓN'.", "CRÍTICA", "SEPARADO / PENDIENTE",
     "Se traslada a la base de simulación; plantilla 16_REG_HABILIDADES para la matriz real.",
     "SIMULACION 03_HABILIDADES_SIM; OPERATIVA 16_REG_HABILIDADES"),
    ("E-047", "06B_HABILIDADES", "R2:R26, fila 27", "Estructura", "Fila de totales y columna de suma dentro de la tabla de datos "
     "(Python la salta por su texto inicial).", "A27 = 'Operarios habilitados'.", "BAJA", "ELIMINADO",
     "Los totales se calculan en 04_MAQUINAS del MODELO.", "MODELO 04_MAQUINAS!K"),
    ("E-048", "06C_SUPUESTOS_PERSONAL", "A1:C16", "Contenido no operativo", "Hoja narrativa; mezcla datos confirmados con "
     "supuestos.", "15 filas.", "BAJA", "REUBICADO",
     "Hechos confirmados (25, 1 turno, 8 h) → 11_PARAMETROS (REAL); texto → 5D.", "OPERATIVA 11_PARAMETROS; Auditoría 5D"),
    # ------------------------------------------------------------------ 07
    ("E-049", "07_CALENDARIO", "C2:C397 (12 feriados en días hábiles)", "Realismo",
     "Con el interruptor en 0, 1-ene, Jueves y Viernes Santo, 1-may, 28–29-jul, 8-dic, 25-dic, etc. son días productivos.",
     "13 fechas con feriado y Productivo = 1.", "ALTA", "DOCUMENTADO / PENDIENTE",
     "No se cambia sin confirmar la práctica de SAGAPI; el interruptor y la fórmula quedan operativos (249 días con feriados).",
     "OPERATIVA 09_CALENDARIO; 11_PARAMETROS"),
    ("E-050", "07_CALENDARIO", "B, D:I", "Redundancia / texto", "Día en texto, horas en texto, columnas constantes "
     "(descanso, regla, entrada, salida) y mes derivable.", "396 filas idénticas en E:H.", "BAJA", "CORREGIDO",
     "dia_semana y horas_productivas por fórmula; constantes en parámetros.", "OPERATIVA 09_CALENDARIO"),
    # ------------------------------------------------------------------ 08
    ("E-051", "08_PEDIDOS", "A2:I97", "Dato simulado",
     "Los 96 pedidos son sintéticos: 8 por mes, liberados los días 3 y 16, siempre los mismos 8 productos, "
     "recepción = liberación.", "S2:S97 'SINTETICO'; patrón regular.", "CRÍTICA", "SEPARADO",
     "Base de simulación; plantilla 12_REG_ENTREGAS para pedidos reales.", "SIMULACION 01_PEDIDOS_SIM"),
    ("E-052", "08_PEDIDOS", "J2:O97", "Columnas vacías", "Entrega efectiva, unidades buenas/defectuosas, causa, días de "
     "atraso vacíos en 96 filas; 'SIN REGISTRO' en O.", "480 celdas vacías.", "BAJA", "ELIMINADO",
     "Se reemplazan por la plantilla 12_REG_ENTREGAS (vacía = sin registros reales).", "OPERATIVA 12_REG_ENTREGAS"),
    ("E-053", "08_PEDIDOS", "F/G de 43 pedidos", "Realismo", "43 pedidos se liberan o vencen en sábado o domingo.",
     "WEEKDAY > 5.", "MEDIA", "DOCUMENTADO", "El modelo los desplaza; se marca con fórmula.",
     "SIMULACION 01_PEDIDOS_SIM!I:J; MODELO 08!Q"),
    ("E-054", "08_PEDIDOS", "P049, P050, P058", "Infactibilidad por construcción",
     "La suma de tiempos de la ruta supera las horas productivas entre liberación y compromiso (97,9 h > 96 h; "
     "116,8 h > 104 h): llegan tarde aun con la planta vacía.", "Columna 'Ruta excede ventana'.", "ALTA", "DOCUMENTADO",
     "Alerta viva en 08_PEDIDOS y 24_VALIDACIONES.", "MODELO 08_PEDIDOS!P"),
    ("E-055", "08_PEDIDOS", "Compromiso (14–18 días)", "Realismo / resultados",
     "Sin averías, el FIFO entrega tarde 73 de 96 pedidos (100 % de lockers y 'otros'); EDD reduce a 27. Los plazos "
     "simulados son incompatibles con las rutas, lo que infla el beneficio atribuible al MILP frente al FIFO.",
     "simulacion.kpis_anuales sobre fifo_plan (73) y corrida 'anual' (EDD+EDD = 27).", "CRÍTICA", "DOCUMENTADO",
     "Ver E1 §5 y E6. Requiere plazos reales.", "E1, E6"),
    ("E-056", "08_PEDIDOS", "H, I, R (fórmulas)", "Lectura Python",
     "'Lote' es fórmula: Python (data_only=False) la lee como vacía y usa el lote del producto por coincidencia.",
     "datos._num devuelve el valor por defecto ante '=...'.", "MEDIA", "CORREGIDO",
     "Lote como valor en la base de simulación y en el MODELO.", "SIMULACION 01_PEDIDOS_SIM!D"),
    ("E-057", "08_PEDIDOS / 12_PRECIOS", "P, Q", "Supuesto", "Precio = promedio de la familia; un minirack y un estante "
     "reforzado valen igual.", "12_PRECIOS!D.", "MEDIA", "PENDIENTE", "Necesita lista de precios por producto.", "2_PENDIENTES"),
    # ------------------------------------------------------------------ 09 / 10 / 11 / 20
    ("E-058", "09_CARGA_ORDEN", "H:I", "Fórmula frágil", "Tiempos tomados por posición ('05_RUTAS'!F2); si se ordena 05, "
     "la carga cambia sin aviso.", "H2 = '05_RUTAS'!F2.", "MEDIA", "CORREGIDO", "SUMIFS por (producto, paso).",
     "MODELO 09_CARGA_ORDEN!H:I"),
    ("E-059", "10_MATERIALES_ORDEN", "H, I", "Cálculo incompleto", "El costo por pedido omite los herrajes (vacíos en 03).",
     "SUM ignora vacíos.", "MEDIA", "CORREGIDO", "Incluye herrajes (+18 266 S/ en el año) e indicador de costo completo.",
     "MODELO 10_MATERIALES_ORDEN!L"),
    ("E-060", "11_CAPACIDAD", "G2:G205", "Cero falso", "'Paradas históricas h' = 0 en 204 filas, aunque no existe historial: "
     "0 afirma que no hubo paradas.", "K = 'SIN HISTORIAL REAL DE PARADAS'.", "MEDIA", "ELIMINADO",
     "La capacidad no descuenta paradas; las paradas reales se registrarán en 13_REG_PARADAS.", "OPERATIVA 10_CAPACIDAD_MENSUAL"),
    ("E-061", "20_COSTOS", "F2:F97", "Inconsistencia", "Costo de máquinas con tarifa promedio 18 S/ por h, mientras 04 "
     "define tarifas por recurso (16–32) y 09 ya las usa.", "20!F = horas × '19_PARAMETROS'!$B$36.", "MEDIA", "CORREGIDO",
     "Tarifa por recurso (103 351 → 137 085 S/ en el año).", "MODELO 20_COSTOS!F"),
    ("E-062", "20_COSTOS", "Total", "Realismo", "Margen bruto implícito ≈ 65–71 %; la mano de obra solo cuenta horas de "
     "proceso (5 742 h × 13 S/) frente a 25 personas × 2 088 h disponibles.", "Costos 580 242 S/ (v1.2) frente a ventas "
     "1 971 970 S/.", "ALTA", "DOCUMENTADO", "Indicador 'Margen bruto %' y alerta en 24_VALIDACIONES.", "MODELO 20_COSTOS!I"),
    ("E-063", "Sistema", "Horas-hombre", "Realismo", "La carga de proceso anual (5 742 h) equivale al 11 % de las horas "
     "disponibles de 25 trabajadores (52 200 h): o los tiempos están subestimados, o la demanda modelada es parcial, o "
     "hay trabajo indirecto no modelado.", "Suma de 09_CARGA_ORDEN!J frente a 25 × 8 × 261.", "CRÍTICA", "PENDIENTE",
     "No puede resolverse sin datos de planta; condiciona toda conclusión sobre personal.", "2_PENDIENTES"),
    # ------------------------------------------------------------------ 12 / 14 / 15 / 16 / 17 / 18
    ("E-064", "12_PRECIOS", "E2:F5; 19!B4:B5", "Duplicidad / supuesto", "Penalidad 10 % repetida en 12 y 19; sin cláusula "
     "contractual.", "Dos fuentes del mismo valor.", "MEDIA", "CORREGIDO / PENDIENTE",
     "Una sola fuente (01_FAMILIAS, ESTIMADO).", "OPERATIVA 01_FAMILIAS!F:G"),
    ("E-065", "14_FALLAS_ESC", "A2:J22", "Dato simulado", "Los 21 eventos son sintéticos (F21 mantenimiento supuesto); "
     "12 fallas de la plegadora entre junio y noviembre, ninguna antes.", "I 'SINTETICO'.", "ALTA", "SEPARADO",
     "SIMULACION 04_EVENTOS_SIM; plantilla 13_REG_PARADAS.", "SIMULACION 04_EVENTOS_SIM"),
    ("E-066", "14_FALLAS_ESC", "B (p. ej. 10:14:25.200)", "Dato artificial", "Instantes con fracciones de segundo, "
     "ubicados para caer dentro de operaciones del FIFO.", "B3, B5, B7 …", "BAJA", "DOCUMENTADO",
     "Se conservan (los escenarios dependen de ellos).", "SIMULACION 04_EVENTOS_SIM!D"),
    ("E-067", "14_FALLAS_ESC / 25", "F04, F19, F21 (16–17 jul, plegadora)", "Contradicción temporal",
     "Eventos que se solapan en la misma máquina pertenecen a escenarios distintos, pero 25_CAPACIDAD_CON_FALLAS los "
     "sumaba por mes como si ocurrieran todos.", "SUMPRODUCT por mes sobre los 21 eventos.", "MEDIA", "CORREGIDO",
     "Pérdida de capacidad por ESCENARIO; el verificador prohíbe solapes dentro de un escenario (0 encontrados).",
     "MODELO 25_PERDIDA_CAPACIDAD_ESC"),
    ("E-068", "15_RECUPERACION", "H2:H63", "Vocabulario", "Naturaleza mezcla 'SCENARIO' (inglés) y 'SUPUESTO TECNICO'.",
     "Dos valores.", "BAJA", "CORREGIDO", "ESTIMADO.", "SIMULACION 06_RECUPERACION_SIM!J"),
    ("E-069", "15_RECUPERACION", "I2:I63", "Tipo mixto", "'Piezas a repetir' mezcla enteros con 'TODO EL LOTE'.",
     "31 celdas de texto.", "BAJA", "CORREGIDO", "Entero o vacío; el reinicio del lote ya lo indica 'reinicia_lote' "
     "(comportamiento idéntico en Python, verificado).", "SIMULACION 06_RECUPERACION_SIM!H"),
    ("E-070", "15_RECUPERACION", "A60:A63", "Modelo de datos", "Pseudoproductos '(Genérico) …' en la columna de producto.",
     "4 filas.", "BAJA", "CORREGIDO (fuente)", "Columna 'ambito'; el MODELO regenera el texto que espera Python.",
     "SIMULACION 06_RECUPERACION_SIM!A"),
    ("E-071", "16_PROGRAMA_BASE", "J:K", "Redundancia", "Columnas constantes ('FIFO DEL ESCENARIO', 'NO PROGRAMA HISTORICO').",
     "1 152 filas.", "BAJA", "CORREGIDO", "Naturaleza CALCULADO; Python lo reproduce (dif. máx. 1,7e-6 h).",
     "SIMULACION 09_PROGRAMA_FIFO_REF"),
    ("E-072", "17_ESTADO_PLANTA", "A1:J1153", "Hoja derivada", "Instantánea del estado solo para F01 (2 304 fórmulas); "
     "Python la recalcula para cualquier evento (estado.particionar).", "Columna A = 'F01'.", "BAJA", "ELIMINADO",
     "Reproducible con el programa.", "—"),
    ("E-073", "18_ESCENARIOS", "C:D, F", "Semántica", "'Recuperación' mezcla política y regla ('FIFO' en S00); "
     "'Duración (h)' suma eventos no contiguos (S14 = 8 h, S21 = 9 h); S20A sin momento.", "18 filas 28, 39, 40.",
     "BAJA", "CORREGIDO", "politica_recuperacion A/B/vacío; momento y duración se derivan de los eventos.",
     "SIMULACION 05_ESCENARIOS_SIM"),
    # ------------------------------------------------------------------ 19 / 21 / 21B / 22 / 23 / 26 / 27 / 28-33
    ("E-074", "19_PARAMETROS", "B2:B43", "Tipo mixto", "La columna Valor mezcla números, textos, fórmulas y definiciones "
     "(f1, f2 no son parámetros).", "Filas 2–3, 13, 26–28.", "MEDIA", "CORREGIDO",
     "valor_num / valor_txt, unidad y naturaleza; definiciones al informe.", "OPERATIVA 11_PARAMETROS; SIMULACION 08_CONFIG_MODELO"),
    ("E-075", "19_PARAMETROS", "B33:B34", "Desactualizado", "Describe una 'cartera de 3 configuraciones; óptimo si dos "
     "coinciden', mecanismo eliminado del código 1.4.0 (solver.py: una resolución HiGHS).", "solver.solve_robusto.",
     "MEDIA", "CORREGIDO", "Texto actualizado.", "SIMULACION 08_CONFIG_MODELO"),
    ("E-076", "19_PARAMETROS", "B7 y B34; B10", "Duplicidad", "Límite de cómputo duplicado; ciclo de horno duplicado con "
     "05!J.", "Dos fuentes.", "BAJA", "CORREGIDO", "Una sola entrada.", "SIMULACION 08_CONFIG_MODELO"),
    ("E-077", "19_PARAMETROS", "B36", "Obsoleto", "Costo hora-máquina promedio 18 S/ incompatible con tarifas por recurso.",
     "Ver E-061.", "BAJA", "ELIMINADO", "Se usa la tarifa de cada recurso.", "—"),
    ("E-078", "19_PARAMETROS", "B38", "Dato faltante", "Factor de emisión vacío.", "Celda vacía.", "BAJA", "PENDIENTE",
     "Vacío válido (CO2 no se calcula).", "OPERATIVA 11_PARAMETROS"),
    ("E-079", "21_INCIDENCIAS_REAL / 22_CALIDAD_REAL", "Solo encabezado", "Plantilla vacía",
     "Hojas sin registros; útiles como plantillas pero sin validaciones ni claves.", "max_row = 1.", "BAJA", "REUBICADO",
     "Plantillas 13_REG_PARADAS y 14_REG_CALIDAD con listas desplegables y formatos.", "OPERATIVA 13/14_REG"),
    ("E-080", "21B_PARADAS_ARCHIVO_ORIG", "A1:K67", "Dato no atribuible",
     "60 paradas registradas para una ROLADORA que la empresa declara no tener; 13 en sábado o domingo con calendario "
     "lunes-viernes; I67 con #VALUE!. Se usaban para 'calibrar' duraciones.", "B = 'ROLADORA'; J = Saturday/Sunday.",
     "ALTA", "REUBICADO", "Se archiva en 5F; no se usa como historial de SAGAPI.", "Auditoría 5F"),
    ("E-081", "23_ORIGEN_DATOS / 26_REGISTRO_CAMBIOS", "Hojas completas", "Procedencia",
     "Textos de procedencia y registro de cambios v1.2 dentro de la base operativa.", "21 + 65 filas.", "BAJA", "REUBICADO",
     "Archivados íntegros en 5B y 5C.", "Auditoría 5B, 5C"),
    ("E-082", "27_SENSIBILIDAD", "A2:E6", "Dependencia vacía", "Python lee la hoja pero no usa sus niveles: están fijos en "
     "experimentos.e4_sensibilidad.", "Datos.sensibilidad no se usa.", "BAJA", "DOCUMENTADO",
     "Se conserva; corrección en el plan (M-15).", "SIMULACION 07_SENSIBILIDAD_SIM"),
    ("E-083", "28–33 (resultados)", "Hojas completas", "Resultados en la base de entrada",
     "Resultados de corridas anteriores sin versión de código ni fecha verificables.", "Encabezado 'RESULTADO CALCULADO'.",
     "MEDIA", "ELIMINADO", "Los resultados se regeneran con el programa en una carpeta de salida.", "—"),
    ("E-084", "herramientas/construir_base_final.py", "Script", "Reproducibilidad",
     "El generador de v1.2 no reproduce el libro entregado (crea 10 trabajadores con nombres; el libro tiene 25 'OP-xx') "
     "y requiere archivos que no están en el ZIP (V13, Data_SAGAPI_PIA).", "HAB = {'Juan Quispe': ...}.", "MEDIA",
     "REEMPLAZADO", "construir_bd_v2.py reconstruye todo desde el v1.2 incluido y el verificador lo comprueba (V11).",
     "herramientas/construir_bd_v2.py"),
]

# (id, dato, ubicación v2, por qué no se reconstruye, a quién solicitar, impacto en el modelo, prioridad)
PENDIENTES = [
    ("PV-01", "Tiempos de preparación y por unidad de las 96 operaciones de los 8 productos con pedido (prioridad: plegado, "
     "perforación, armado y corte)", "OPERATIVA 06_RUTAS!F:G", "Ningún tiempo fue cronometrado", "Jefe de planta / "
     "cronometraje 15_REG_TIEMPOS", "p_om de todas las restricciones; carga de la plegadora (69 % anual, 81 % jun–ago)", "P0"),
    ("PV-02", "Matriz real de habilidades (25 × 16) y personas necesarias por operación", "OPERATIVA 16_REG_HABILIDADES",
     "Toda la matriz es simulada", "Jefe de planta", "Restricciones de personal R11–R15; conclusiones sobre rotación", "P0"),
    ("PV-03", "Pedidos reales: cantidades, fechas de recepción, liberación (material) y compromiso, precio", "OPERATIVA "
     "12_REG_ENTREGAS", "Los 96 pedidos son sintéticos", "Ventas / planeamiento", "Todo el modelo (r_j, d_j, w_j, P_j)", "P0"),
    ("PV-04", "Explicar la brecha de horas-hombre: 5 742 h de proceso frente a 52 200 h disponibles", "—",
     "Requiere distribución real del tiempo del personal (directo/indirecto)", "Gerencia de producción",
     "Validez de cualquier conclusión sobre dotación", "P0"),
    ("PV-05", "¿Se trabaja en feriados nacionales?", "OPERATIVA 11_PARAMETROS aplicar_feriados", "Práctica no informada",
     "Gerencia", "Calendario (261 o 249 días productivos)", "P1"),
    ("PV-06", "Horario real (entrada, salida, refrigerio) y si hay horas extra", "OPERATIVA 08_PERSONAL; 11_PARAMETROS",
     "Solo se confirmaron 8 h netas y 1 turno", "RR. HH.", "Eje de horas productivas", "P1"),
    ("PV-07", "Historial de paradas de la plegadora y demás máquinas (inicio, fin, causa)", "OPERATIVA 13_REG_PARADAS",
     "Las fallas son sintéticas y el registro 21B corresponde a una roladora", "Mantenimiento", "Escenarios de falla, "
     "Monte Carlo, MTBF/MTTR", "P1"),
    ("PV-08", "Inventario físico de máquinas (cantidad, existencia del 2.º taladro y 2.ª estación de soldadura, sala de "
     "pintura)", "OPERATIVA 05_RECURSOS!E,K", "Inventario no certificado", "Jefe de planta", "Conjuntos M_o y capacidad", "P1"),
    ("PV-09", "Capacidad simultánea de puestos manuales y áreas (armado, inspección, embalaje, preparación)",
     "OPERATIVA 05_RECURSOS!D:E", "Se modelan con capacidad 1", "Jefe de planta", "Restricciones disyuntivas R4–R5", "P1"),
    ("PV-10", "Tamaño de lote por producto y capacidad real del horno (piezas, m² o colgadores por carga)",
     "OPERATIVA 02_PRODUCTOS!I; 11_PARAMETROS", "Lote = 10 en todo el catálogo; unidad de capacidad contradictoria",
     "Jefe de planta", "Número de preparaciones y curado", "P1"),
    ("PV-11", "Espesor real de chapa de lockers (0,6 o 1,5 mm) y góndolas (0,8 o 1,0 mm)", "OPERATIVA 04_DESPIECE!D",
     "Catálogo y despiece se contradicen", "Ingeniería de producto", "Masa, costo y planchas", "P2"),
    ("PV-12", "Unidad del precio del perfil (S/ por m o por kg) y sección real", "OPERATIVA 03_MATERIALES!D,H",
     "Precio aplicado por kg aunque se declara por m", "Compras", "Costo de materiales", "P2"),
    ("PV-13", "Precios de 33 materiales y de bisagras/cerraduras", "OPERATIVA 03_MATERIALES!H", "Sin cotizaciones",
     "Compras", "Costo de materiales (no afecta al MILP)", "P2"),
    ("PV-14", "Penalidad contractual real por atraso (si existe)", "OPERATIVA 01_FAMILIAS!F:G", "No hay cláusula acreditada",
     "Ventas / contratos", "Objetivo f1", "P1"),
    ("PV-15", "¿El costo de uso por hora de máquina incluye al operario?", "OPERATIVA 05_RECURSOS!F", "Sin definición",
     "Contabilidad", "Costos (no afecta al MILP)", "P2"),
    ("PV-16", "Medidas reales de los productos del catálogo con dimensiones genéricas", "OPERATIVA 02_PRODUCTOS!E:G",
     "Valores de plantilla", "Ingeniería de producto", "Ninguno en el MILP actual", "P3"),
    ("PV-17", "Factor de tiempo en máquinas alternativas (1,10)", "OPERATIVA 07_ELEGIBILIDAD!F", "Sin medición",
     "Cronometraje", "p_om en alternativas", "P2"),
    ("PV-18", "Reglas reales de recuperación tras avería (reanudar o reiniciar, verificación)", "SIMULACION 06_RECUPERACION_SIM",
     "Hipótesis técnica", "Operador de plegadora", "Tiempo restante de operaciones interrumpidas", "P2"),
]

# (hoja original, columna/rango original, acción, libro v2, hoja v2, columna v2, nota)
MAPA = [
    ("00_LEEME", "todo", "ARCHIVADO", "AUDITORÍA", "5A_LEEME_ORIGINAL", "—", "Sustituido por 00_DICCIONARIO y 00_CODIGOS"),
    ("01_PRODUCTOS", "Familia", "TRANSFORMADO", "OPERATIVA", "02_PRODUCTOS", "familia_id", "Clave FAM-xxx; MODELO conserva el nombre"),
    ("01_PRODUCTOS", "Nombre completo", "CONSERVADO", "OPERATIVA", "02_PRODUCTOS", "producto (+ producto_id)", "Python: clave"),
    ("01_PRODUCTOS", "Tipo / Alto / Ancho / Fondo", "CONSERVADO", "OPERATIVA", "02_PRODUCTOS", "tipo, alto_cm, ancho_cm, fondo_cm", ""),
    ("01_PRODUCTOS", "Puertas", "CORREGIDO", "OPERATIVA", "02_PRODUCTOS", "puertas", "'No aplica' → vacío"),
    ("01_PRODUCTOS", "Lote guía", "CONSERVADO", "OPERATIVA", "02_PRODUCTOS", "lote_guia_und", "Python: lote por defecto"),
    ("01_PRODUCTOS", "Componentes / Pasos de ruta", "FÓRMULA", "OPERATIVA", "02_PRODUCTOS", "n_componentes, n_pasos_ruta", "COUNTIF"),
    ("01_PRODUCTOS", "Pedidos/Unidades 2025, Esquema", "ELIMINADO", "—", "—", "—", "Demanda simulada; imágenes no operativas"),
    ("01B_IMAGENES", "todo", "ELIMINADO", "—", "—", "—", "Esquemas generados, no datos"),
    ("02_MATERIALES", "todas", "NORMALIZADO", "OPERATIVA", "03_MATERIALES", "material_id … costo_unitario_soles", "Clave = clave técnica"),
    ("03_DESPIECE", "Producto/Componente/Material/Piezas", "TRANSFORMADO", "OPERATIVA", "04_DESPIECE", "bom_id, producto_id, componente, material_id, piezas_por_unidad", ""),
    ("03_DESPIECE", "Ancho/Alto/Longitud", "CORREGIDO", "OPERATIVA", "04_DESPIECE", "ancho_pieza_mm, alto_pieza_mm, longitud_pieza_m", "'No aplica'/0 → vacío"),
    ("03_DESPIECE", "Área / Masa / Costo", "FÓRMULA", "OPERATIVA", "04_DESPIECE", "area_chapa_m2_pieza, masa_kg_producto, costo_soles_producto",
     "MODELO: valores (Python lee la masa)"),
    ("03_DESPIECE", "Planchas equivalentes", "CORREGIDO", "OPERATIVA", "04_DESPIECE", "planchas_equiv_producto", "× piezas"),
    ("04_MAQUINAS", "Equipo, Tipo técnico, Cantidad, Costo, Clave, kW, Factor, Grupo, Crítica", "NORMALIZADO", "OPERATIVA",
     "05_RECURSOS", "recurso … recurso_critico", "MODELO conserva encabezados heredados"),
    ("04_MAQUINAS", "Marca, Modelo, Estatus físico", "ARCHIVADO", "AUDITORÍA", "5E_MAQUINAS_REFERENCIA", "—", "No verificados"),
    ("04_MAQUINAS", "Horas, Utilización, Energía, Naturaleza", "MOVIDO", "MODELO", "04_MAQUINAS / 11_CAPACIDAD", "fórmulas", "Dependen de pedidos simulados"),
    ("05_RUTAS", "Producto/Paso/Operación/Equipo/Min fijos/Min unidad/Tratamiento/Ciclo horno", "NORMALIZADO", "OPERATIVA", "06_RUTAS",
     "producto_id, paso, operacion, recurso_id, min_fijos_lote, min_por_unidad, tratamiento_tiempo, min_ciclo_horno_incluido", ""),
    ("05_RUTAS", "Precedencia", "CORREGIDO", "OPERATIVA", "06_RUTAS", "paso_predecesor", "MODELO regenera 'Inicio'"),
    ("05_RUTAS", "Origen de duración", "CODIFICADO", "OPERATIVA", "06_RUTAS", "origen_tiempo", ""),
    ("05_RUTAS", "Familia, Clave de unión", "ELIMINADO", "—", "—", "—", "Derivables"),
    ("06_OPERARIOS", "Operario, Turnos, Descanso, Horas netas, Inicio, Fin", "NORMALIZADO", "OPERATIVA", "08_PERSONAL",
     "operario_id, turno, descanso_h, horas_netas_dia, hora_entrada, hora_salida", ""),
    ("06_OPERARIOS", "Especialidad", "SEPARADO", "SIMULACION", "02_PERFILES_SIM", "especialidad_simulada", ""),
    ("06_OPERARIOS", "Días, Identidad", "ARCHIVADO", "AUDITORÍA", "5D_SUPUESTOS_PERSONAL", "—", "Texto"),
    ("06B_HABILIDADES", "matriz", "SEPARADO", "SIMULACION", "03_HABILIDADES_SIM", "recurso_id por columna", "Sin fila de totales"),
    ("06C_SUPUESTOS_PERSONAL", "todo", "REPARTIDO", "OPERATIVA / AUDITORÍA", "11_PARAMETROS / 5D", "—", "Hechos → parámetros"),
    ("07_CALENDARIO", "Fecha, Productivo, Feriado", "CONSERVADO", "OPERATIVA", "09_CALENDARIO", "fecha, laborable_base, feriado_nacional", ""),
    ("07_CALENDARIO", "Productivo efectivo", "FÓRMULA", "OPERATIVA", "09_CALENDARIO", "productivo_efectivo", "Nombre definido"),
    ("07_CALENDARIO", "Día, Horas netas, Entrada, Salida, Descanso, Regla, Mes", "ELIMINADO/FÓRMULA", "OPERATIVA", "09_CALENDARIO",
     "dia_semana, horas_productivas", "Constantes en parámetros"),
    ("08_PEDIDOS", "Pedido…Compromiso, Lote", "SEPARADO", "SIMULACION", "01_PEDIDOS_SIM", "pedido_id … lote_und", "Lote como valor"),
    ("08_PEDIDOS", "Entrega efectiva … Estado entrega", "ELIMINADO", "OPERATIVA", "12_REG_ENTREGAS", "plantilla", "Vacíos"),
    ("08_PEDIDOS", "Precio, Valor, Penalidad, w_j, Plazo, Tope, Horas", "MOVIDO", "MODELO", "08_PEDIDOS", "fórmulas", "Python los recalcula"),
    ("09_CARGA_ORDEN", "todo", "MOVIDO", "MODELO", "09_CARGA_ORDEN", "fórmulas SUMIFS", "Derivada"),
    ("10_MATERIALES_ORDEN", "todo", "MOVIDO", "MODELO", "10_MATERIALES_ORDEN", "fórmulas", "Incluye herrajes y planchas corregidas"),
    ("11_CAPACIDAD", "Días, Horas/día, Cantidad, Horas programadas", "MOVIDO", "OPERATIVA + MODELO", "10_CAPACIDAD_MENSUAL / 11_CAPACIDAD", "fórmulas", ""),
    ("11_CAPACIDAD", "Paradas históricas h, Horas netas h, Lectura", "ELIMINADO", "—", "—", "—", "Cero falso"),
    ("12_PRECIOS", "todo", "NORMALIZADO", "OPERATIVA", "01_FAMILIAS", "familia_id … penalidad_diaria_frac", "MODELO 12_PRECIOS"),
    ("13_ELEGIBILIDAD", "Producto/Paso/Máquina/Tipo/Elegible/Factor", "NORMALIZADO", "OPERATIVA", "07_ELEGIBILIDAD",
     "producto_id, paso, recurso_id, tipo_asignacion, elegible, factor_tiempo", "Tipo codificado"),
    ("13_ELEGIBILIDAD", "Operación, Naturaleza del factor", "ELIMINADO", "—", "—", "naturaleza", "Redundante"),
    ("14_FALLAS_ESC", "todo", "SEPARADO", "SIMULACION", "04_EVENTOS_SIM", "evento_id … paso_ref", "tipo_evento FALLA/MANTENIMIENTO"),
    ("15_RECUPERACION", "todo", "SEPARADO", "SIMULACION", "06_RECUPERACION_SIM", "ambito … min_verificacion", "Piezas: entero/vacío"),
    ("15_RECUPERACION", "Detalle de la política", "ARCHIVADO", "AUDITORÍA", "5G_DETALLE_RECUPERACION", "—", "Texto"),
    ("16_PROGRAMA_BASE", "Pedido, Paso, Máquina, Inicio, Fin, Duración", "SEPARADO", "SIMULACION", "09_PROGRAMA_FIFO_REF", "", "CALCULADO"),
    ("17_ESTADO_PLANTA", "todo", "ELIMINADO", "—", "—", "—", "Reproducible (estado.particionar)"),
    ("18_ESCENARIOS", "Escenario, Caso, Evento, Recuperación, Semilla", "SEPARADO", "SIMULACION", "05_ESCENARIOS_SIM", "", "Momento y duración derivados"),
    ("19_PARAMETROS", "parámetros de planta", "NORMALIZADO", "OPERATIVA", "11_PARAMETROS", "parametro_id, valor_num, valor_txt", ""),
    ("19_PARAMETROS", "parámetros del modelo", "NORMALIZADO", "SIMULACION", "08_CONFIG_MODELO", "", ""),
    ("19_PARAMETROS", "f1, f2, reglas descriptivas, 85 %", "ARCHIVADO", "INFORMES", "E1/E6", "—", "No son parámetros"),
    ("20_COSTOS", "todo", "MOVIDO", "MODELO", "20_COSTOS", "fórmulas", "Tarifa por recurso"),
    ("21_INCIDENCIAS_REAL", "encabezado", "REEMPLAZADO", "OPERATIVA", "13_REG_PARADAS", "plantilla", ""),
    ("21B_PARADAS_ARCHIVO_ORIG", "todo", "ARCHIVADO", "AUDITORÍA", "5F_PARADAS_ROLADORA", "—", "No atribuible a SAGAPI"),
    ("22_CALIDAD_REAL", "encabezado", "REEMPLAZADO", "OPERATIVA", "14_REG_CALIDAD", "plantilla", ""),
    ("23_ORIGEN_DATOS", "todo", "ARCHIVADO", "AUDITORÍA", "5B_ORIGEN_DATOS_V12", "—", "Naturaleza por fila/columna en v2"),
    ("24_VALIDACIONES", "todo", "REESCRITO", "MODELO", "24_VALIDACIONES", "fórmulas", "Controles corregidos"),
    ("25_CAPACIDAD_CON_FALLAS", "todo", "REEMPLAZADO", "MODELO", "25_PERDIDA_CAPACIDAD_ESC", "fórmulas", "612 #VALUE! en v1.2"),
    ("26_REGISTRO_CAMBIOS", "todo", "ARCHIVADO", "AUDITORÍA", "5C_REGISTRO_CAMBIOS_V12", "—", ""),
    ("27_SENSIBILIDAD", "todo", "SEPARADO", "SIMULACION", "07_SENSIBILIDAD_SIM", "", "Python la lee (no usa los niveles)"),
    ("28_RESULTADOS_ANUALES … 33_ROBUSTEZ_MC", "todo", "ELIMINADO", "—", "—", "—", "Salidas, no entradas"),
]

# (hoja MODELO, columna, obligatoria, función/módulo, uso en el modelo, efecto si se renombra/elimina)
DEPENDENCIAS = [
    ("01_PRODUCTOS", "Nombre completo", "Sí", "datos.leer", "Clave de producto (rutas, pedidos, despiece)", "KeyError: lectura aborta"),
    ("01_PRODUCTOS", "Familia", "Sí", "datos.leer / validar", "Familia del pedido (precio)", "KeyError"),
    ("01_PRODUCTOS", "Lote guía", "No (def. 10)", "datos.leer", "Lote por defecto si 08 no lo trae", "Silencioso: usa 10"),
    ("01_PRODUCTOS", "Tipo, Alto cm, Ancho cm, Fondo cm", "No", "datos.leer", "Informativo", "Ninguno"),
    ("03_DESPIECE", "Producto, Material, Área de chapa m², Masa kg / producto", "No (hoja opcional)", "datos.leer → masa_chapa",
     "Indicador material_reproceso_kg", "Silencioso: indicador = 0"),
    ("04_MAQUINAS", "Equipo o recurso completo", "Sí", "datos.leer / validar", "Conjunto M; validación de rutas", "KeyError"),
    ("04_MAQUINAS", "Cantidad de escenario", "Sí*", "datos.validar", "Recurso disponible si ≥ 1 (capacidad no modelada > 1)",
     "Silencioso: 0 ⇒ error de validación de rutas"),
    ("04_MAQUINAS", "Costo de uso S//h, Clave interna, Grupo de operarios", "No", "datos.leer", "Informativo", "Silencioso"),
    ("04_MAQUINAS", "Potencia nominal kW (referencia), Factor de carga medio", "No", "indicadores.evaluar, experimentos.e1",
     "Energía (kWh)", "Silencioso: energía = 0"),
    ("05_RUTAS", "Producto, Paso, Operación, Equipo principal", "Sí", "datos.leer → instancia.construir", "O_j, principal, M_o",
     "KeyError"),
    ("05_RUTAS", "Min fijos por lote, Minutos por unidad", "Sí", "datos.duracion_h", "p_om (R3, R4–R5, R6, R7)",
     "ErrorDatos si vacío o negativo"),
    ("05_RUTAS", "Precedencia", "Sí", "datos.leer", "Comprueba ruta lineal ('Inicio' en el paso 1)", "ErrorDatos"),
    ("05_RUTAS", "Tratamiento del tiempo", "Sí", "estado.tiempo_restante, regla_recuperacion", "Recuperación tras avería",
     "Silencioso: trata como POR_UNIDAD"),
    ("06_OPERARIOS", "Operario (seudónimo)", "Sí", "datos.leer", "Lista de trabajadores", "KeyError"),
    ("06B_HABILIDADES", "fila 1 = nombres de recurso; col. A = operario; 1/0", "No (hoja opcional)",
     "modelo R11; personal_integrado R11–R15; verificacion.control_personal", "Asignación de personal",
     "Silencioso: sin restricción de personal. Columnas extra se interpretan como máquinas"),
    ("07_CALENDARIO", "Fecha, Productivo (1/0)", "Sí", "datos.leer → Calendario", "Eje de horas productivas; r_j, d_j, ventanas",
     "KeyError"),
    ("07_CALENDARIO", "Feriado nacional Perú", "No", "datos.leer; experimentos.e4_anual_sensibilidad", "Feriados si interruptor = 1",
     "Silencioso"),
    ("08_PEDIDOS", "Pedido, Producto, Familia, Unidades, Recepción 2025, Liberación 2025, Compromiso 2025", "Sí",
     "datos.leer", "J, q_j, r_j, d_j, plazo, w_j, P_j", "KeyError / ErrorDatos"),
    ("08_PEDIDOS", "Lote", "No", "datos.leer", "ROUNDUP(q/lote)", "Silencioso: usa lote guía"),
    ("08_PEDIDOS", "Clasificación", "No", "datos.leer", "Informativo", "Ninguno"),
    ("12_PRECIOS", "Familia, Unidades agregadas 2025, Ventas agregadas S/", "Sí", "datos.leer", "Precio medio → valor_j, w_j, P_j",
     "ErrorDatos"),
    ("12_PRECIOS", "Penalidad fija %, Penalidad diaria %", "No (def. 0,10 / 0)", "datos.leer", "P_j (f1)", "Silencioso"),
    ("13_ELEGIBILIDAD", "Producto, Paso, Máquina elegible, Tipo de asignación, Elegible 1/0, Factor de tiempo relativo", "Sí",
     "datos.leer → instancia", "M_o y p_om alternativos; sensibilidad usa el texto 'ALTERNATIVA CON UTILLAJE COMPATIBLE'",
     "KeyError; cambiar el texto anula la sensibilidad sin aviso"),
    ("14_FALLAS_ESC", "Evento, Inicio, Horas de reloj, Equipo", "Sí", "datos.leer → experimentos._ventanas", "Ventanas (m, a, b) R2/R6",
     "KeyError / ErrorDatos"),
    ("14_FALLAS_ESC", "Motivo hipotético, Pedido…, Paso, Tipo de dato, Horas de turno afectadas", "No", "datos.leer; cmd_validar",
     "Control de horas de turno", "Silencioso"),
    ("15_RECUPERACION", "Producto, Paso, Operación, Política, Conserva piezas, Reinicia lote, Repite setup", "Sí",
     "estado.regla_recuperacion", "Tiempo restante (políticas A/B)", "KeyError"),
    ("15_RECUPERACION", "Piezas a repetir por interrupción, Min de verificación tras reparación", "No", "estado.tiempo_restante",
     "Tiempo restante", "Silencioso: 0"),
    ("16_PROGRAMA_BASE", "Pedido, Paso, Máquina, Inicio, Fin", "No (hoja opcional)", "experimentos.e0_fifo",
     "Comprobación de reproducción FIFO", "Silencioso: no compara"),
    ("18_ESCENARIOS", "Escenario, Evento, Recuperación, Semilla", "Sí", "datos.leer; cmd_caso, rodante, experimentos",
     "Definición de escenarios", "KeyError"),
    ("19_PARAMETROS", "Parámetro, Valor (nombres exactos: 'Aplicar feriados nacionales (1/0)', 'Jornada productiva', "
     "'Máquina de la avería', 'Costo equivalente reasignación', 'Réplicas Monte Carlo de fallas de la plegadora', "
     "'Semilla Monte Carlo')", "Sí", "datos.leer; Experimentos.__init__; e5_montecarlo", "Calendario, β, Monte Carlo",
     "Silencioso: valores por defecto"),
    ("24_VALIDACIONES", "Control = 'Python reproduce 16_PROGRAMA_BASE'", "Solo con --escribir-excel", "reportes.escribir_excel",
     "Escribe Sí/No", "KeyError si falta la hoja"),
    ("27_SENSIBILIDAD", "todas", "No", "datos.leer", "Ninguno (niveles fijos en el código)", "Ninguno"),
]


def _texto_seguro(v):
    """Los textos archivados no deben convertirse en fórmulas ni en errores de Excel."""
    if isinstance(v, str) and v.startswith("="):
        return "Fórmula original: " + v[1:]
    if isinstance(v, str) and v in ("#VALUE!", "#REF!", "#NAME?", "#DIV/0!", "#N/A", "#NUM!", "#NULL!"):
        return f"{v} (error presente en el archivo original)"
    return v


def tabla_original(ws):
    filas = list(ws.iter_rows(values_only=True))
    enc = [str(c) if c is not None else f"col_{j + 1}" for j, c in enumerate(filas[0])]
    return enc, [[_texto_seguro(v) for v in f] for f in filas[1:] if f and any(v is not None for v in f)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--original", default="Base_Datos_SAGAPI_25_TRABAJADORES_SIMULADOS_v1_2.xlsx")
    ap.add_argument("--salida", default=os.path.join("entrega_v2_0", "auditoria"))
    a = ap.parse_args()
    os.makedirs(a.salida, exist_ok=True)
    o = openpyxl.load_workbook(a.original, data_only=True)
    wb = openpyxl.Workbook()
    wb.remove(wb.active)

    ws = wb.create_sheet("1_MATRIZ_ERRORES")
    cols = [Col("id", "txt", 7), Col("hoja_original", "txt", 22), Col("celda_o_rango", "txt", 28), Col("categoria", "txt", 18),
            Col("problema", "txt", 60), Col("evidencia", "txt", 48), Col("severidad", "txt", 10), Col("accion", "txt", 18),
            Col("correccion_aplicada_o_motivo", "txt", 60), Col("ubicacion_v2", "txt", 30)]
    escribir_tabla(ws, cols, [[_texto_seguro(v) for v in m] for m in MATRIZ], comentarios=False)
    from openpyxl.styles import Alignment
    for fila in ws.iter_rows(min_row=2):
        for c in fila:
            c.alignment = Alignment(wrap_text=True, vertical="top")

    ws = wb.create_sheet("2_PENDIENTES_VALIDACION")
    cols = [Col("id", "txt", 7), Col("dato_requerido", "txt", 60), Col("ubicacion_v2", "txt", 30),
            Col("por_que_no_se_reconstruye", "txt", 40), Col("solicitar_a", "txt", 22), Col("impacto_en_el_modelo", "txt", 44),
            Col("prioridad", "txt", 9)]
    escribir_tabla(ws, cols, [list(p) for p in PENDIENTES], comentarios=False)

    ws = wb.create_sheet("3_MAPA_MIGRACION")
    cols = [Col("hoja_original", "txt", 26), Col("columnas_originales", "txt", 44), Col("accion", "txt", 16),
            Col("libro_v2", "txt", 18), Col("hoja_v2", "txt", 28), Col("columnas_v2", "txt", 50), Col("nota", "txt", 40)]
    escribir_tabla(ws, cols, [list(m) for m in MAPA], comentarios=False)

    ws = wb.create_sheet("4_DEPENDENCIAS_PYTHON")
    cols = [Col("hoja_MODELO", "txt", 18), Col("columnas", "txt", 60), Col("obligatoria", "txt", 14),
            Col("funcion_modulo", "txt", 40), Col("uso_en_el_modelo", "txt", 44), Col("efecto_si_se_renombra_o_elimina", "txt", 44)]
    escribir_tabla(ws, cols, [list(d) for d in DEPENDENCIAS], comentarios=False)

    archivos = [("5A_LEEME_ORIGINAL", "00_LEEME"), ("5B_ORIGEN_DATOS_V12", "23_ORIGEN_DATOS"),
                ("5C_REGISTRO_CAMBIOS_V12", "26_REGISTRO_CAMBIOS"), ("5D_SUPUESTOS_PERSONAL", "06C_SUPUESTOS_PERSONAL"),
                ("5F_PARADAS_ROLADORA", "21B_PARADAS_ARCHIVO_ORIG")]
    for nuevo, viejo in archivos:
        enc, filas = tabla_original(o[viejo])
        ws = wb.create_sheet(nuevo)
        escribir_tabla(ws, [Col(e, "gen", 22) for e in enc], filas, comentarios=False)
    # máquinas: marca/modelo/estatus
    enc, filas = tabla_original(o["04_MAQUINAS"])
    idx = [enc.index(c) for c in ("Clave interna", "Equipo o recurso completo", "Marca comercial del escenario", "Modelo comercial",
                                  "Estatus físico", "Naturaleza columnas añadidas")]
    ws = wb.create_sheet("5E_MAQUINAS_REFERENCIA")
    escribir_tabla(ws, [Col(enc[i], "txt", 30) for i in idx], [[f[i] for i in idx] for f in filas], comentarios=False)
    enc, filas = tabla_original(o["15_RECUPERACION"])
    idx = [enc.index(c) for c in ("Producto", "Paso", "Política", "Naturaleza", "Detalle de la política")]
    ws = wb.create_sheet("5G_DETALLE_RECUPERACION")
    escribir_tabla(ws, [Col(enc[i], "txt", 30) for i in idx], [[f[i] for i in idx] for f in filas], comentarios=False)
    enc, filas = tabla_original(o["06_OPERARIOS"])
    ws = wb.create_sheet("5H_OPERARIOS_V12")
    escribir_tabla(ws, [Col(e, "txt", 18) for e in enc], filas, comentarios=False)
    # resumen
    ws = wb.create_sheet("0_RESUMEN", 0)
    from collections import Counter
    sev = Counter(m[6] for m in MATRIZ)
    acc = Counter(m[7].split(" ")[0] for m in MATRIZ)
    filas = [["Hallazgos en la matriz", len(MATRIZ)]] + [[f"Severidad {k}", v] for k, v in sorted(sev.items())] + \
            [[f"Acción {k}", v] for k, v in sorted(acc.items())] + [["Pendientes de validación", len(PENDIENTES)],
                                                                   ["Original analizado", os.path.basename(a.original)]]
    escribir_tabla(ws, [Col("indicador", "txt", 40), Col("valor", "gen", 50)], filas, comentarios=False, filtro=False)
    for w in wb.worksheets:
        w.sheet_properties.tabColor = "B8860B" if w.title[0] in "01234" else "7F7F7F"
    wb._sheets.sort(key=lambda w: w.title)
    ruta = os.path.join(a.salida, "SAGAPI_AUDITORIA_DATOS_v2_0.xlsx")
    wb.save(ruta)
    import csv
    with open(os.path.join(a.salida, "matriz_errores_excel.csv"), "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow([c.nombre for c in [Col("id"), Col("hoja_original"), Col("celda_o_rango"), Col("categoria"), Col("problema"),
                                      Col("evidencia"), Col("severidad"), Col("accion"), Col("correccion_aplicada_o_motivo"),
                                      Col("ubicacion_v2")]])
        w.writerows(MATRIZ)
    with open(os.path.join(a.salida, "pendientes_validacion.csv"), "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow(["id", "dato_requerido", "ubicacion_v2", "por_que_no_se_reconstruye", "solicitar_a", "impacto_en_el_modelo",
                    "prioridad"])
        w.writerows(PENDIENTES)
    print(ruta, len(MATRIZ), "hallazgos;", len(PENDIENTES), "pendientes")


if __name__ == "__main__":
    main()
