import unittest
from types import SimpleNamespace
from sagapi.diagnostico_global import diagnosticar


def inst():
    return SimpleNamespace(ops=[{'job':0},{'job':0},{'job':1}],
                           jobs=[{'id':'P1'},{'id':'P2'}],
                           job_ops={0:[0,1],1:[2]})

BASE={0:('M1',0,2), 1:('M1',2,3), 2:('M2',0,3)}

class DiagnosticoGlobalTests(unittest.TestCase):
    def test_programa_hypotetico_original_sin_choques(self):
        r,e=diagnosticar(inst(),BASE,{})
        self.assertEqual(r['total_incidencias_diagnosticas'],0)
        self.assertFalse(r['programa_global_certificado'])
        self.assertEqual(r['operaciones_sin_compromiso_milp'],3)
    def test_identifica_solape_y_precedencia(self):
        r,e=diagnosticar(inst(),BASE,{1:('M1',1,3,'W1')})
        self.assertEqual(r['cruces_maquinas_ensamblaje'],1)
        self.assertEqual(r['violaciones_precedencia_ensamblaje'],1)
    def test_identifica_averia(self):
        r,e=diagnosticar(inst(),BASE,{}, [('M2',1,2)])
        self.assertEqual(r['cruces_fallas_ensamblaje'],1)
        self.assertEqual(len(e),1)
    def test_rechaza_falta_de_operacion(self):
        r,e=diagnosticar(inst(),{0:('M1',0,2)}, {})
        self.assertEqual(r['operaciones_sin_programacion'],2)
        self.assertFalse(r['programa_global_certificado'])
    def test_op_inexistente(self):
        r,e=diagnosticar(inst(),BASE,{123:('M1',0,1,'W1')})
        self.assertTrue(any(x['tipo']=='ID_INVALIDO' for x in e))
