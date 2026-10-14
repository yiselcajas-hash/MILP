"""Pruebas específicas de reservas externas — piloto limitado, no validación anual."""
import unittest
from sagapi.personal_integrado import ModeloPersonalOperaciones
from sagapi.solver import solve
from sagapi.cobertura_externa import preparar_reservas_futuras
from tests.test_personal_integrado import ejemplo


class ReservasExternasTest(unittest.TestCase):
    def test_reserva_maquina_y_trabajador_impide_solapes(self):
        sub = ejemplo()
        # Reserva hipotética de otro pedido, M1 y W1: intervalo [1,3].
        sub.windows = [('M1',1.0,3.0)]
        sub.trabajadores_externos = {99:('M1',1.0,3.0,'W1')}
        sub.ventanas_maquina_externas = [(99,'M1',1.0,3.0)]
        mdl = ModeloPersonalOperaciones(sub)
        mdl.M.set_objective(mdl.f1b_terms())
        out = solve(mdl.M,time_limit=10)
        self.assertEqual(out['status'],'Optimal')
        self.assertEqual(mdl.verificar_personal(out['x']),[])
        for o,(m,s) in mdl.decode(out['x']).items():
            c=s+sub.pR[(o,m)]
            self.assertTrue(c<=1.0+1e-5 or s>=3.0-1e-5)
        self.assertGreater(len(mdl.yp_externa),0)

    def test_reserva_externa_fija_no_reutiliza_trabajador_ocupado(self):
        sub=ejemplo(fijo=True)
        sub.inst.datos.habilidades={'W1':{'M1','M2'},'W2':{'M1','M2'}}
        # La operación fija en M1 [0,3] precisa operario; externo [2,4]
        # reserva W1. El solver debe asignar W2 a la fija.
        sub.trabajadores_externos={99:('M2',2.0,4.0,'W1')}
        sub.ventanas_maquina_externas=[(99,'M2',2.0,4.0)]
        sub.windows=[('M2',2.0,4.0)]
        mdl=ModeloPersonalOperaciones(sub)
        mdl.M.set_objective(mdl.f1b_terms())
        result=solve(mdl.M,time_limit=10)
        self.assertEqual(result['status'],'Optimal')
        self.assertEqual(mdl.asignaciones(result['x'])[0],'W2')
        self.assertEqual(mdl.verificar_personal(result['x']),[])

    def test_verificador_detecta_conflicto_reserva_corrupta(self):
        sub=ejemplo()
        mdl=ModeloPersonalOperaciones(sub)
        mdl.M.set_objective(mdl.f1b_terms())
        out=solve(mdl.M,time_limit=10)
        self.assertEqual(out['status'],'Optimal')
        sol=mdl.decode(out['x']); assigned=mdl.asignaciones(out['x'])
        o=0
        m,s=sol[o]
        sub.trabajadores_externos={99:(m,s,s+1.0,assigned[o])}
        errors=mdl.verificar_personal(out['x'])
        self.assertTrue(any('reserva externa' in x for x in errors),errors)

    def test_horizonte_externo_invalido(self):
        sub=ejemplo()
        with self.assertRaises(ValueError):
            preparar_reservas_futuras(sub,{},0)

if __name__=='__main__':
    unittest.main()
