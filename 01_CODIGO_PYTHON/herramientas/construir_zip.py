#!/usr/bin/env python3
"""Construye y verifica SAGAPI_MILP_VERSION_OPTIMIZADA_FINAL.zip con la estructura de entrega.

* Copia las carpetas 01–07, tests/ y README.md; agrega la versión inicial v1.4.0 y la auditoría de la etapa 1
  (desde historial/) en 06_AUDITORIA_Y_VALIDACION/Evidencias_Validacion/.
* Excluye cachés y temporales (__pycache__, .pytest_cache, *.pyc, HTML intermedios).
* Escribe un manifiesto SHA-256 y comprueba: rutas obligatorias presentes, ningún archivo vacío, ninguna carpeta
  vacía, ningún caché y ninguna ruta absoluta.

Uso: python 01_CODIGO_PYTHON/herramientas/construir_zip.py [carpeta_salida]
"""
from __future__ import annotations

import csv
import hashlib
import os
import shutil
import sys
import tempfile
import zipfile

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
NOMBRE = "SAGAPI_MILP_VERSION_OPTIMIZADA_FINAL"
CARPETAS = ["01_CODIGO_PYTHON", "02_BASE_DATOS", "03_MODELO_MATEMATICO", "04_RESULTADOS", "05_GRAFICOS",
            "06_AUDITORIA_Y_VALIDACION", "07_DOCUMENTACION", "tests"]
EXTRA = {os.path.join("historial", "v1_4_0_original"):
         os.path.join("06_AUDITORIA_Y_VALIDACION", "Evidencias_Validacion", "version_inicial_v1_4_0"),
         os.path.join("historial", "etapa1_auditoria_v2_0"):
         os.path.join("06_AUDITORIA_Y_VALIDACION", "Evidencias_Validacion", "etapa1_auditoria")}
OBLIGATORIOS = [
    "README.md", "01_CODIGO_PYTHON/Programa_principal.py", "01_CODIGO_PYTHON/sagapi/__init__.py",
    "01_CODIGO_PYTHON/requirements.txt", "02_BASE_DATOS/SAGAPI_BASE_CORREGIDA_FINAL.xlsx",
    "02_BASE_DATOS/Diccionario_de_datos.xlsx", "03_MODELO_MATEMATICO/Formulacion_MILP_Actualizada.pdf",
    "04_RESULTADOS/Resultados_MILP", "04_RESULTADOS/Comparacion_MILP_FIFO", "04_RESULTADOS/Indicadores_KPI",
    "04_RESULTADOS/Escenarios", "05_GRAFICOS/Diagramas_Gantt", "05_GRAFICOS/Utilizacion_Recursos",
    "05_GRAFICOS/Comparaciones", "05_GRAFICOS/Analisis_Sensibilidad",
    "06_AUDITORIA_Y_VALIDACION/Informe_Correcciones.pdf", "06_AUDITORIA_Y_VALIDACION/Matriz_Errores.xlsx",
    "06_AUDITORIA_Y_VALIDACION/Reporte_Pruebas", "06_AUDITORIA_Y_VALIDACION/Evidencias_Validacion",
    "07_DOCUMENTACION/Manual_Ejecucion.pdf", "07_DOCUMENTACION/Informe_Tecnico_Final.pdf",
    "07_DOCUMENTACION/Registro_Cambios.md", "07_DOCUMENTACION/Limitaciones_y_Supuestos.md", "tests/conftest.py",
]
EXCLUIR_DIR = {"__pycache__", ".pytest_cache", ".venv", ".git"}


def _ignorar(directorio, nombres):
    return [n for n in nombres if n in EXCLUIR_DIR or n.endswith(".pyc") or (n.startswith(".") and n.endswith(".html"))]


def construir(salida):
    tmp = tempfile.mkdtemp()
    base = os.path.join(tmp, NOMBRE)
    os.makedirs(base)
    shutil.copy2(os.path.join(RAIZ, "README.md"), base)
    for c in CARPETAS:
        shutil.copytree(os.path.join(RAIZ, c), os.path.join(base, c), ignore=_ignorar)
    for origen, destino in EXTRA.items():
        if os.path.isdir(os.path.join(RAIZ, origen)):
            shutil.copytree(os.path.join(RAIZ, origen), os.path.join(base, destino), ignore=_ignorar)
    manifiesto = os.path.join(base, "06_AUDITORIA_Y_VALIDACION", "Evidencias_Validacion", "MANIFIESTO_SHA256.csv")
    filas = []
    for d, _, archivos in os.walk(base):
        for a in sorted(archivos):
            p = os.path.join(d, a)
            if p == manifiesto:
                continue
            filas.append((os.path.relpath(p, base).replace(os.sep, "/"), os.path.getsize(p),
                          hashlib.sha256(open(p, "rb").read()).hexdigest()))
    filas.sort()
    with open(manifiesto, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["archivo", "bytes", "sha256"])
        w.writerows(filas)
    os.makedirs(salida, exist_ok=True)
    zpath = os.path.join(salida, NOMBRE + ".zip")
    if os.path.exists(zpath):
        os.remove(zpath)
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for d, dirs, archivos in os.walk(base):
            dirs.sort()
            for a in sorted(archivos):
                p = os.path.join(d, a)
                z.write(p, os.path.relpath(p, tmp))
    shutil.rmtree(tmp)
    return zpath, len(filas) + 1


def verificar(zpath):
    problemas = []
    with zipfile.ZipFile(zpath) as z:
        nombres = z.namelist()
        if z.testzip() is not None:
            problemas.append("archivo dañado en el ZIP")
        infos = z.infolist()
    pref = NOMBRE + "/"
    if not all(n.startswith(pref) for n in nombres):
        problemas.append("hay entradas fuera de la carpeta raíz")
    if any(n.startswith("/") or ".." in n.split("/") for n in nombres):
        problemas.append("rutas absolutas o con '..'")
    rel = [n[len(pref):] for n in nombres]
    for o in OBLIGATORIOS:
        if not any(r == o or r.startswith(o + "/") for r in rel):
            problemas.append(f"falta {o}")
    for i in infos:
        if not i.is_dir() and i.file_size == 0:
            problemas.append(f"archivo vacío: {i.filename}")
    cache = [n for n in nombres if "__pycache__" in n or n.endswith(".pyc") or ".pytest_cache" in n]
    if cache:
        problemas.append(f"{len(cache)} archivos de caché")
    return problemas, len(nombres)


if __name__ == "__main__":
    salida = sys.argv[1] if len(sys.argv) > 1 else os.path.join(RAIZ, "dist")
    zpath, n = construir(salida)
    probs, total = verificar(zpath)
    print(f"{zpath}: {total} archivos, {os.path.getsize(zpath) / 1e6:.1f} MB")
    print("Verificación de estructura:", "SIN PROBLEMAS" if not probs else probs)
    sys.exit(1 if probs else 0)
