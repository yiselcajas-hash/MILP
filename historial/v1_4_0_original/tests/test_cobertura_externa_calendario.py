"""Regresión de cobertura t0 y turnos para SAGAPI 1.3.1; NO certifica toda la planta."""
import unittest
import datetime as dt

from sagapi import reglas
from sagapi.calendario import Calendario
from sagapi.cobertura_externa import preparar_con_cobertura, PedidoExternoInterrumpido
from sagapi.experimentos import Experimentos, _ventanas
from sagapi.jornada_piloto import segmentar_turnos, comprobar_jornadas


class TurnosTest(unittest.TestCase):
    def setUp(self):
        self.cal = Calendario([(dt.date(2025,1,1),True),
                               (dt.date(2025,1,2),False),
                               (dt.date(2025,1,3),True)])

    def test_operacion_12h_cruza_jornadas_y_descanso(self):
        segs = segmentar_turnos(self.cal, 2, 14)
        self.assertEqual(round(sum(x['horas'] for x in segs),6),12.0)
        self.assertTrue(all(x['fecha']!='2025-01-02' for x in segs))
        self.assertTrue(all(x['horas']<=4+1e-6 for x in segs))
        self.assertTrue(all('12:00:00' not in x['inicio_reloj'] for x in segs))

    def test_error_fuera_calendario(self):
        with self.assertRaisesRegex(ValueError,'horizonte'):
            segmentar_turnos(self.cal,12,17)

    def test_maximo_ocho_horas_por_dia(self):
        ops = [dict(operacion_id=1,trabajador_simulado='OP-01',inicio_h=0,fin_h=8),
               dict(operacion_id=2,trabajador_simulado='OP-01',inicio_h=8,fin_h=16)]
        segs,diag=comprobar_jornadas(self.cal,ops)
        self.assertEqual(len(segs),4)
        self.assertAlmostEqual(diag['max_horas_trabajador_dia'],8)

    def test_trabajador_sobrecargado_se_detecta(self):
        ops = [dict(operacion_id=1,trabajador_simulado='OP-01',inicio_h=0,fin_h=6),
               dict(operacion_id=2,trabajador_simulado='OP-01',inicio_h=4,fin_h=8)]
        with self.assertRaisesRegex(ValueError,'excede'):
            comprobar_jornadas(self.cal,ops)


class CoberturaExternaRealistaTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import os
        folder=os.path.dirname(os.path.dirname(__file__))
        excel=os.path.join(folder,'Base_Datos_SAGAPI_25_TRABAJADORES_SIMULADOS_v1_2.xlsx')
        cls.E=Experimentos(excel,os.path.join(folder,'resultados'),log=lambda *a:None)
        cls.base=reglas.fifo_plan(cls.E.I,range(len(cls.E.I.jobs)))[0]

    def _caso(self, id, n):
        esc=next(x for x in self.E.d.escenarios if x['id']==id)
        ws=_ventanas(self.E.d,[x for x in esc['eventos'].split('+') if x])
        t0=min(x[1] for x in ws)
        jobs=[j for j in range(len(self.E.I.jobs))
              if self.E.I.jobs[j]['r']<=t0+1e-6
              and self.base[self.E.I.job_ops[j][-1]][2]>t0+1e-6]
        return ws,t0,jobs[:n],esc['politica']

    def test_s08a_auto_incluye_externo_interrumpido(self):
        ws,t0,sel,pol=self._caso('S08A',3)
        sub,info=preparar_con_cobertura(self.E.d,self.E.I,self.base,t0,sel,ws,pol)
        self.assertEqual(info['pedidos_autoincluidos_por_falla'],['P071'])
        self.assertEqual(len(sub.free),32)
        self.assertEqual(info['externas_activas_fijadas'],0)

    def test_s08a_no_puede_ignorar_externo_interrumpido(self):
        ws,t0,sel,pol=self._caso('S08A',3)
        with self.assertRaises(PedidoExternoInterrumpido):
            preparar_con_cobertura(self.E.d,self.E.I,self.base,t0,sel,ws,pol,auto_incluir=False)

    def test_s05a_externa_ocupa_maquina_hasta_terminar(self):
        ws,t0,sel,pol=self._caso('S05A',2)
        sub,info=preparar_con_cobertura(self.E.d,self.E.I,self.base,t0,sel,ws,pol)
        self.assertEqual(len(sub.externas_activas),1)
        for m,s,c in sub.externas_activas.values():
            self.assertGreaterEqual(sub.mavail[m],c)
        self.assertFalse(info['cobertura_global_anual'])


if __name__ == '__main__':
    unittest.main()
