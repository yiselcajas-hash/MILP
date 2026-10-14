"""Pruebas del cronograma auditable EX POST de personal (habilidades simuladas)."""
import datetime as dt
import os
import unittest
from types import SimpleNamespace
from sagapi.auditoria_personal import asignar_personal, ErrorAuditoriaPersonal
from sagapi.calendario import Calendario


class AuditoriaOperariosTest(unittest.TestCase):
    def setUp(self):
        dias = [(dt.date(2025, 1, 2), True), (dt.date(2025, 1, 3), True)]
        cal = Calendario(dias)
        d = SimpleNamespace(habilidades={'OP-01': {'Corte'}, 'OP-02': {'Soldadura'}}, calendario=cal)
        self.I = SimpleNamespace(
            datos=d, machines=['Corte', 'Soldadura'],
            ops=[{'job': 0, 'paso': 1, 'operacion': 'Cortar'},
                 {'job': 1, 'paso': 1, 'operacion': 'Soldar'}],
            jobs=[{'id': 'P01', 'familia': 'Racks'}, {'id': 'P02', 'familia': 'Lockers'}],
            op_label=lambda o: f'P{o+1}-01')

    def test_asignacion_operaciones_simultaneas_y_descanso(self):
        prog = {0: ('Corte', 3.0, 5.0), 1: ('Soldadura', 3.5, 6.5)}
        filas, resumen = asignar_personal(self.I, prog, 'TEST', 'MILP+MILP')
        self.assertEqual(resumen['operaciones_con_cobertura'], 2)
        self.assertEqual(resumen['trabajadores_utilizados'], 2)
        self.assertEqual(resumen['conflictos_h'], 0.0)
        self.assertAlmostEqual(resumen['horas_hombre_asignadas'], 5.0, places=4)
        self.assertTrue(any(r['fin_reloj'].endswith('12:00:00') for r in filas))
        self.assertTrue(any(r['inicio_reloj'].endswith('13:00:00') for r in filas))
        for fila in filas:
            self.assertIn(fila['maquina'], self.I.datos.habilidades[fila['trabajador_simulado']])

    def test_falta_de_habilidad_incompatible_detectada(self):
        self.I.datos.habilidades = {'OP-01': {'Corte', 'Soldadura'}}
        with self.assertRaises(ErrorAuditoriaPersonal):
            asignar_personal(self.I, {0: ('Corte', 1.0, 3.0), 1: ('Soldadura', 2.0, 4.0)})

    def test_operacion_fuera_calendario_detectada(self):
        with self.assertRaises(ErrorAuditoriaPersonal):
            asignar_personal(self.I, {0: ('Corte', 15.0, 17.0)})

    def test_dobles_reservas_maquina_detectadas(self):
        self.I.datos.habilidades = {'OP-01': {'Corte'}, 'OP-02': {'Corte'}}
        with self.assertRaises(ErrorAuditoriaPersonal):
            asignar_personal(self.I, {0: ('Corte', 1.0, 4.0), 1: ('Corte', 2.0, 5.0)})

if __name__ == '__main__':
    unittest.main()
