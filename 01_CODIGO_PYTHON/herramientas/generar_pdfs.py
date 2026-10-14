#!/usr/bin/env python3
"""Convierte los documentos fuente (Markdown) a PDF: pandoc → HTML con MathML → Chromium sin interfaz → PDF.

Uso: python 01_CODIGO_PYTHON/herramientas/generar_pdfs.py [nombre ...]
Requiere pandoc ≥ 2.11 y Chromium (variable CHROMIUM o /opt/pw-browsers). Los PDF se escriben en su carpeta.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
FUENTES = os.path.join(RAIZ, "07_DOCUMENTACION", "fuentes")
DESTINO = {
    "Formulacion_MILP_Actualizada": "03_MODELO_MATEMATICO",
    "Informe_Correcciones": "06_AUDITORIA_Y_VALIDACION",
    "Manual_Ejecucion": "07_DOCUMENTACION",
    "Informe_Tecnico_Final": "07_DOCUMENTACION",
    "Informe_KPI": os.path.join("04_RESULTADOS", "Indicadores_KPI"),
    "Informe_Resultados_Computacionales": "04_RESULTADOS",
}


def _chromium():
    cands = [os.environ.get("CHROMIUM", ""), "/opt/pw-browsers/chromium-1194/chrome-linux/chrome",
             shutil.which("chromium") or "", shutil.which("chromium-browser") or "", shutil.which("google-chrome") or ""]
    cands += sorted(__import__("glob").glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome"))
    for c in cands:
        if c and os.path.exists(c):
            return c
    raise SystemExit("No se encontró Chromium (defina la variable CHROMIUM)")


def convertir(nombre):
    md = os.path.join(FUENTES, nombre + ".md")
    destino = os.path.join(RAIZ, DESTINO[nombre])
    os.makedirs(destino, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        html = os.path.join(FUENTES, f".{nombre}.html")
        subprocess.run(["pandoc", md, "-s", "-o", html, "--mathml", "--toc", "--toc-depth=2", "--css", "estilo.css",
                        "--metadata", "toc-title=Contenido", "--resource-path", f"{FUENTES}:{RAIZ}"],
                       check=True, cwd=FUENTES)
        pdf = os.path.join(tmp, nombre + ".pdf")
        subprocess.run([_chromium(), "--headless", "--no-sandbox", "--disable-gpu", "--no-pdf-header-footer",
                        f"--print-to-pdf={pdf}", "file://" + html], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=180)
        os.remove(html)
        shutil.copy(pdf, os.path.join(destino, nombre + ".pdf"))
    print("PDF:", os.path.join(DESTINO[nombre], nombre + ".pdf"))


if __name__ == "__main__":
    for n in (sys.argv[1:] or [n for n in DESTINO if os.path.exists(os.path.join(FUENTES, n + ".md"))]):
        convertir(n)
