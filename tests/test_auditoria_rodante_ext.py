"""Pruebas independientes sobre reservas FIFO y traspasos entre ventanas."""
import unittest
from sagapi.auditoria_rodante import auditar_cruces, verificar_arrastres


def reserva(op,m,s,c,w,ventana=1):
    return dict(operacion_id=op,maquina=m,inicio_h=s,fin_h=c,
                trabajador_simulado=w,ventana=ventana)


class AuditoriaRodanteExternaTests(unittest.TestCase):
    def test_todos_los_intervalos_sin_conflictos(self):
        c={10:('M1',0,4,'W1'), 11:('M1',4,9,'W1')}
        r=[reserva(22,'M1',9,13,'W2'), reserva(23,'M2',2,8,'W2')]
        a, errores=auditar_cruces(c,r)
        self.assertEqual(errores,[])
        self.assertEqual(a['reservas_externas_unicas'],2)
        self.assertFalse(a['cobertura_anual_certificada'])

    def test_bloquea_cruce_de_maquina_externa(self):
        a,errs=auditar_cruces({10:('M1',0,5,'W1')},[reserva(22,'M1',4,7,'W2')])
        self.assertEqual(a['cruces_maquina_compromiso_externa'],1)
        self.assertTrue(any('Cruce de máquina' in e for e in errs))

    def test_bloquea_cruce_de_trabajador_externo(self):
        a,errs=auditar_cruces({10:('M1',0,5,'W1')},[reserva(22,'M2',4,7,'W1')])
        self.assertEqual(a['cruces_trabajador_compromiso_externa'],1)
        self.assertTrue(errs)

    def test_rechaza_cambio_trabajador_entre_ventanas(self):
        a,errs=auditar_cruces({},[reserva(22,'M2',0,9,'W1',1),reserva(22,'M2',0,9,'W2',2)])
        self.assertEqual(a['reservas_externas_unicas'],1)
        self.assertTrue(any('cambió' in e for e in errs))

    def test_rechaza_solapamiento_dentro_fifo_externo(self):
        _,errs=auditar_cruces({},[reserva(22,'M2',0,9,'W1'),reserva(23,'M3',4,7,'W1')])
        self.assertTrue(any('Reserva FIFO externa: solapamiento trabajador' in e for e in errs))

    def test_reserva_repetida_no_es_doble_conflicto(self):
        a,errs=auditar_cruces({},[reserva(22,'M2',0,9,'W1',1),reserva(22,'M2',0,9,'W1',2)])
        self.assertEqual(errs,[])
        self.assertEqual(a['reservas_observaciones'],2)
        self.assertEqual(a['reservas_externas_unicas'],1)

    def test_rechaza_operacion_duplicada_entre_subproblemas(self):
        _,errs=auditar_cruces({10:('M1',0,2,'W1')},[reserva(10,'M1',0,2,'W1')])
        self.assertTrue(any('a la vez' in e for e in errs))

    def test_traspaso_correcto(self):
        esperado={10:('M1',0,12,'W1')}
        self.assertEqual(verificar_arrastres(esperado,{10:('M1',0,12,'W1')}),[])

    def test_traspaso_cambio_y_ausencia(self):
        esperado={10:('M1',0,12,'W1')}
        self.assertTrue(verificar_arrastres(esperado,{10:('M1',0,12,'W2')}))
        self.assertTrue(verificar_arrastres(esperado,{}))

if __name__=='__main__': unittest.main()
