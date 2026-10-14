"""Pruebas de invariantes independientes para el piloto de horizonte rodante."""
import unittest

from sagapi.rodante_personal import verificar_compromisos, ejecutar


class RodantePersonalTests(unittest.TestCase):
    def test_compromiso_valido(self):
        f = {1:('M1',0,4,'W1'), 2:('M1',4,7,'W1')}
        p = {1:('M1',0,4), 2:('M1',4,7)}
        self.assertEqual(verificar_compromisos(f, p, {1:'W1',2:'W1'}), [])

    def test_inmutabilidad_horarios(self):
        errores = verificar_compromisos({1:('M1',0,4,'W1')}, {1:('M1',0.2,4.2)})
        self.assertTrue(any('modificada' in e for e in errores))

    def test_inmutabilidad_maquina(self):
        errores = verificar_compromisos({1:('M1',0,4,'W1')}, {1:('M2',0,4)})
        self.assertTrue(errores)

    def test_inmutabilidad_trabajador(self):
        errores = verificar_compromisos({1:('M1',0,4,'W1')}, {1:('M1',0,4)}, {1:'W2'})
        self.assertTrue(any('trabajador' in e for e in errores))

    def test_detecta_doble_trabajador(self):
        f = {1:('M1',0,5,'W1'), 2:('M2',3,7,'W1')}
        p = {o:datos[:3] for o,datos in f.items()}
        self.assertTrue(any('trabajador' in e for e in verificar_compromisos(f,p)))

    def test_detecta_doble_maquina(self):
        f = {1:('M1',0,5,'W1'), 2:('M1',3,7,'W2')}
        p = {o:datos[:3] for o,datos in f.items()}
        self.assertTrue(any('máquina' in e for e in verificar_compromisos(f,p)))

    def test_missing_operation(self):
        self.assertTrue(verificar_compromisos({1:('M1',0,5,'W1')}, {}))

    def test_parametros_invalidos(self):
        with self.assertRaises(ValueError):
            ejecutar(None, None, {}, [], 'A', [1], 0,
                     n_ventanas=0, paso_h=8, horizonte_externos=120)
        with self.assertRaises(ValueError):
            ejecutar(None, None, {}, [], 'A', [1], 0,
                     n_ventanas=1, paso_h=8, horizonte_externos=4)


if __name__=='__main__':
    unittest.main()
