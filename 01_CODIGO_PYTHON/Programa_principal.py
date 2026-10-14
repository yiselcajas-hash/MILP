"""Punto de entrada de SAGAPI v2.0 (ver README.md y 07_DOCUMENTACION/Manual_Ejecucion.pdf).

Ejemplos (desde la carpeta 01_CODIGO_PYTHON):
  python Programa_principal.py validar
  python Programa_principal.py programar --plan MILP --reaccion MILP --escenario S20A
  python Programa_principal.py caso --escenario S06A
  python Programa_principal.py todo
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from sagapi.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
