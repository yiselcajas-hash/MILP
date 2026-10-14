"""Línea de comandos de extremo a extremo y reportes construidos solo a partir de resultados existentes."""
import subprocess
import sys

from conftest import CODIGO, RAIZ
from sagapi.reportes import graficos


def test_programar_fifo_crea_resultados(tmp_path):
    r = subprocess.run([sys.executable, str(CODIGO / "Programa_principal.py"), "programar", "--plan", "FIFO",
                        "--reaccion", "CONV", "--escenario", "S06A", "--sin-personal", "--salida", str(tmp_path)],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    assert (tmp_path / "Resultados_MILP" / "programa_S06A_FIFO_CONV.csv").exists()
    assert (tmp_path / "Indicadores_KPI" / "KPI_S06A_FIFO_CONV.csv").exists()
    assert "Verificación independiente" in r.stdout


def test_caso_compara_reacciones(tmp_path):
    r = subprocess.run([sys.executable, str(CODIGO / "Programa_principal.py"), "caso", "--escenario", "S06A",
                        "--salida", str(tmp_path)], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    assert (tmp_path / "Comparacion_MILP_FIFO" / "E2b_reaccion_evento.csv").exists()


def test_graficos_no_inventan_datos(tmp_path):
    """Sin archivos de resultados ninguna figura se genera."""
    hechos = graficos.generar_todos(tmp_path / "vacio", tmp_path / "g", log=lambda *_: None)
    assert hechos == []
    assert not list((tmp_path / "g").rglob("*.png")) if (tmp_path / "g").exists() else True


def test_graficos_desde_resultados_reales(tmp_path):
    subprocess.run([sys.executable, str(CODIGO / "Programa_principal.py"), "caso", "--escenario", "S06A",
                    "--salida", str(tmp_path)], capture_output=True, text=True, check=True)
    hechos = graficos.generar_todos(tmp_path, tmp_path / "g", log=lambda *_: None)
    assert any("gantt_reaccion_S06A" in str(h) for h in hechos)


def test_base_no_se_modifica(tmp_path):
    """La base de datos es de solo lectura para el programa (C-19)."""
    import hashlib
    from conftest import BASE
    antes = hashlib.sha256(BASE.read_bytes()).hexdigest()
    r = subprocess.run([sys.executable, str(CODIGO / "Programa_principal.py"), "programar", "--plan", "EDD",
                        "--reaccion", "EDD", "--escenario", "S01A", "--salida", str(tmp_path)], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    assert hashlib.sha256(BASE.read_bytes()).hexdigest() == antes
