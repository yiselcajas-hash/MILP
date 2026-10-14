"""Regresiones unitarias para HiGHS vía API pública y validador algebraico."""
import unittest
import tempfile
from pathlib import Path
import numpy as np

from sagapi.solver import LinModel, solve, solve_robusto, validar_vector, exportar_mps


class SolverPublicoTest(unittest.TestCase):
    def test_optimalidad_con_cota(self):
        model = LinModel()
        a = model.var('a', 0, 1, integer=True)
        b = model.var('b', 0, 1, integer=True)
        model.row([(a, 1), (b, 1)], 1, float('inf'))
        model.set_objective([(a, 2), (b, 1)])
        r = solve_robusto(model, time_limit=5)
        self.assertEqual(r['status'], 'Optimal')
        self.assertTrue(r['certificado'])
        self.assertAlmostEqual(r['obj'], 1, places=6)
        self.assertFalse(validar_vector(model, r['x']))

    def test_infactible_no_declara_optimo(self):
        model = LinModel()
        a = model.var('a', 0, 1, integer=True)
        model.row([(a, 1)], lo=2)
        model.set_objective([(a, 1)])
        r = solve(model, time_limit=5)
        self.assertFalse(r['certificado'])
        self.assertIsNone(r['x'])

    def test_verificador_detecta_candidato_invalido(self):
        model = LinModel()
        a = model.var('a', 0, 1, integer=True)
        model.row([(a, 1)], lo=1)
        self.assertTrue(validar_vector(model, np.array([0.0])))
        self.assertTrue(validar_vector(model, np.array([0.2])))
        self.assertFalse(validar_vector(model, np.array([1.0])))

    def test_exportacion_mps_sin_api_privada(self):
        model = LinModel()
        a = model.var('a', 0, 1, integer=True)
        b = model.var('b', 0, 5, integer=False)
        model.row([(a, 1), (b, 2)], lo=1.5, hi=4)
        model.set_objective([(a, 2), (b, 1)])
        with tempfile.TemporaryDirectory() as td:
            f = Path(exportar_mps(model, Path(td) / 'toy.mps'))
            content = f.read_text()
            self.assertIn('ROWS', content)
            self.assertIn('BOUNDS', content)
            self.assertIn('L000000', content)
            self.assertIn('U000000', content)
            self.assertTrue(f.with_suffix('.variables.json').exists())


if __name__ == '__main__':
    unittest.main()
