"""Contrapruebas de personal integrado; todas las habilidades son simuladas."""
import unittest
from types import SimpleNamespace
from sagapi.estado import Subproblema
from sagapi.modelo import ModeloMILP
from sagapi.personal_integrado import ModeloPersonalOperaciones, LimitePiloto
from sagapi.solver import solve
from sagapi.verificacion import verificar


def ejemplo(fijo=False, alternativa=False):
    # Dos pedidos de una operación, dos máquinas. Un único trabajador
    # habilitado para ambas; en la formulación integrada puede rotar entre ellas.
    maquinas = ['M1', 'M2']
    habilidades = {'W1': {'M1', 'M2'}}
    ops = [dict(job=0, paso=1), dict(job=1, paso=1)]
    jobs = [dict(id='J0', r=0., d=6., P=100., w=1., pdia=100., valor=1000.),
            dict(id='J1', r=0., d=6., P=100., w=1., pdia=100., valor=1000.)]
    I = SimpleNamespace(ops=ops, jobs=jobs, job_ops={0: [0], 1: [1]},
        machines=maquinas, datos=SimpleNamespace(habilidades=habilidades),
        op_label=lambda o: f'J{o}-1')
    if fijo:
        return Subproblema(inst=I, t0=1., free=[1], eligR={1: ['M2']},
           pR={(1, 'M2'): 2.}, lbR={1: 1.}, mavail={'M1': 3., 'M2': 1.},
           fixed={0: ('M1', 0., 3.)}, pending=[1], jobs=[1])
    eligible = {0: ['M1'], 1: ['M2']}
    if alternativa:
        eligible = {0: ['M1', 'M2'], 1: ['M2']}
    pR = {(o, m): 2.0 for o in eligible for m in eligible[o]}
    return Subproblema(inst=I, t0=0., free=[0, 1], eligR=eligible,
        pR=pR, lbR={0: 0., 1: 0.}, mavail={'M1': 0., 'M2': 0.},
        fixed={}, pending=[0, 1], jobs=[0, 1])


class IntegracionPersonalTest(unittest.TestCase):
    def _solve(self, sub):
        mdl = ModeloPersonalOperaciones(sub)
        mdl.M.set_objective(mdl.f1b_terms())
        r = solve(mdl.M, time_limit=10)
        self.assertEqual(r['status'], 'Optimal', r['status'])
        self.assertEqual(mdl.verificar_personal(r['x']), [])
        return mdl, r

    def test_un_trabajador_dos_maquinas_secuencial(self):
        sub = ejemplo()
        estatico = ModeloMILP(sub)
        estatico.M.set_objective(estatico.f1_terms())
        res = solve(estatico.M, time_limit=5)
        self.assertIsNone(res['x'])  # reserva conservadora: no permite rotación
        mdl, r = self._solve(sub)
        asign = mdl.asignaciones(r['x'])
        self.assertEqual(asign, {0:'W1', 1:'W1'})
        sol = mdl.decode(r['x'])
        s0, s1 = sol[0][1], sol[1][1]
        self.assertTrue(s0 >= s1 + 2 - 1e-6 or s1 >= s0 + 2 - 1e-6)

    def test_fijo_ocupa_personal_antes_de_nueva_operacion(self):
        mdl, r = self._solve(ejemplo(fijo=True))
        self.assertEqual(mdl.asignaciones(r['x']), {0:'W1', 1:'W1'})
        self.assertGreaterEqual(mdl.decode(r['x'])[1][1], 3.0 - 1e-6)

    def test_compatibilidad_condicionada_a_maquina(self):
        sub = ejemplo(alternativa=True)
        sub.inst.datos.habilidades = {'W1': {'M1'}, 'W2': {'M2'}}
        mdl, r = self._solve(sub)
        for o, (m, s) in mdl.decode(r['x']).items():
            self.assertIn(m, sub.inst.datos.habilidades[mdl.asignaciones(r['x'])[o]])

    def test_limited_and_no_skills(self):
        with self.assertRaises(LimitePiloto):
            ModeloPersonalOperaciones(ejemplo(), max_operaciones=1)
        sub = ejemplo()
        sub.inst.datos.habilidades = {'W1': {'M1'}}
        with self.assertRaises(ValueError):
            ModeloPersonalOperaciones(sub)

if __name__ == '__main__':
    unittest.main()
