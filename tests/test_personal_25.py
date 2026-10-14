"""Pruebas de la reserva de un trabajador habilitado por recurso potencial.

Son pruebas sobre habilidades SIMULADAS; no constituyen auditoría de habilidades reales.
"""
import os
import unittest
from sagapi import datos, instancia, estado, reglas
from sagapi.modelo import ModeloMILP
from sagapi.personal import emparejar, resumen_dotacion
from sagapi.solver import validar_vector

ARCHIVO = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                       'Base_Datos_SAGAPI_25_TRABAJADORES_SIMULADOS_v1_2.xlsx')

class Personal25Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d = datos.leer(ARCHIVO)
        cls.I = instancia.construir(cls.d)

    def test_exactamente_25_en_un_turno(self):
        self.assertEqual(len(self.d.operarios), 25)
        self.assertEqual(len(self.d.habilidades), 25)
        self.assertTrue(all(w in self.d.habilidades for w in self.d.operarios))

    def test_cobertura_simultanea_15_recursos(self):
        a = resumen_dotacion(self.d.habilidades, self.I.machines)
        self.assertTrue(a['cobertura_total_simultanea'])
        self.assertEqual(len(a['emparejamiento_testigo']), len(self.I.machines))
        self.assertEqual(len(set(a['emparejamiento_testigo'].values())), len(self.I.machines))

    def test_matriz_incompatible_se_detecta(self):
        ejemplo = {'W1': {'Corte'}, 'W2': {'Pintura'}}
        self.assertIsNone(emparejar(['Corte', 'Pintura', 'Soldadura'], ejemplo))
        self.assertIsNone(emparejar(['Corte', 'Corte-2'], {'W1': {'Corte','Corte-2'}}))

    def test_milp_detecta_escasez_real_en_un_contraejemplo(self):
        from tests.test_enumeracion import micro
        from sagapi.solver import solve
        I, d, _ = micro(1)
        d.habilidades = {"W1": set(I.machines)}
        sub = estado.subproblema_inicial(I, jobs=[0])
        m = ModeloMILP(sub)
        self.assertGreaterEqual(len(m.maquinas_dotacion), 2)
        m.M.set_objective(m.f1_terms())
        r = solve(m.M, time_limit=5)
        self.assertIsNone(r["x"])
        self.assertFalse(r["certificado"])

    def test_reserva_forma_parte_modelo_y_encode_valido(self):
        sub = estado.subproblema_inicial(self.I, jobs=[0, 1])
        m = ModeloMILP(sub)
        self.assertGreater(m.tamano()['asignaciones_personal'], 0)
        self.assertGreater(m.bloques['R11_PERSONAL'][1]-m.bloques['R11_PERSONAL'][0], 0)
        prog, _ = reglas.fifo_plan(self.I, [0, 1])
        sol = {o: (maq, S) for o, (maq, S, _) in prog.items()}
        self.assertFalse(validar_vector(m.M, m.encode(sol)))

if __name__ == '__main__':
    unittest.main()
