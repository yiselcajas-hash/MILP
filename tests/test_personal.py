"""Personal: certificado de cobertura, reparación laboral, asignación MILP y verificación L1–L5."""
import pytest

from sagapi import personal as pers, reglas, simulacion as sim
from sagapi.personal import Dotacion, EstadoPersonal
from sagapi.verificacion import verificar_personal


def test_certificado_base_25_trabajadores(datos, inst):
    dot = pers.dotacion(datos)
    assert len(dot.trabajadores) == 25 and dot.fuente == "SIMULADA"
    c = pers.certificado_cobertura(dot, inst)
    assert c["ok"] and c["cubierto"] == c["demanda"]
    asignados = [w for eq in c["equipos"].values() for w in eq]
    assert len(asignados) == len(set(asignados)), "un trabajador no puede estar en dos equipos"
    for m, eq in c["equipos"].items():
        for w in eq:
            assert m.split("#")[0] in dot.habilidades[w]


def test_certificado_falla_con_pocos_trabajadores(datos, inst):
    dot = pers.dotacion(datos, datos.operarios[13:])          # quedan 13 trabajadores
    c = pers.certificado_cobertura(dot, inst)
    assert not c["ok"] and c["deficit"]


def test_certificado_flujo_con_dotacion_2():
    """Máquina que exige 2 personas: el flujo debe asignar 2 distintas o declarar déficit."""
    from types import SimpleNamespace
    inst = SimpleNamespace(ops=[dict(crew=2), dict(crew=1)], elig={0: ["A"], 1: ["B"]})
    dot = Dotacion(["w1", "w2", "w3"], {"w1": {"A"}, "w2": {"A", "B"}, "w3": {"B"}})
    c = pers.certificado_cobertura(dot, inst)
    assert c["ok"] and sorted(c["equipos"]["A"]) == ["w1", "w2"] and c["equipos"]["B"] == ["w3"]
    dot2 = Dotacion(["w1", "w2"], {"w1": {"A"}, "w2": {"A", "B"}})
    assert not pers.certificado_cobertura(dot2, inst)["ok"]


def test_estado_personal_primer_inicio_y_reserva():
    dot = Dotacion(["w1", "w2"], {"w1": {"A", "B"}, "w2": {"B"}})
    est = EstadoPersonal(dot)
    assert est.primer_inicio(0.0, 2.0, "A") == 0.0
    est.reservar(0, 0.0, 2.0, "A")
    assert est.asignacion[0] == ["w1"]
    assert est.primer_inicio(0.0, 1.0, "A") == pytest.approx(2.0)     # w1 ocupado hasta 2
    assert est.primer_inicio(0.0, 1.0, "B") == 0.0                   # w2 libre
    with pytest.raises(RuntimeError):
        est.primer_inicio(0.0, 1.0, "C")                            # nadie habilitado: error explícito


def test_asignacion_milp_anual_fifo(datos, inst):
    dot = pers.dotacion(datos)
    prog, _ = reglas.fifo_plan(inst, list(range(len(inst.jobs))))
    a = pers.asignar_trabajadores(inst, prog, dot, tl=120)
    assert a["estado"] in ("OPTIMO", "FACTIBLE_LIMITE_TIEMPO")
    assert a["violaciones"] == []
    viol = verificar_personal(inst, prog, (), a["asignacion"], dot.habilidades, horas_dia=8.0)
    assert viol == []
    # el equilibrio no empeora la carga máxima respecto de la asignación por equipos fijos
    c = pers.certificado_cobertura(dot, inst)
    eq = pers.asignacion_por_equipos(inst, prog, c)
    carga_eq = {}
    for (t, o), ws in eq.items():
        m, S, C = prog[o]
        for w in ws:
            carga_eq[w] = carga_eq.get(w, 0.0) + C - S
    assert max(a["cargas"].values()) <= max(carga_eq.values()) + 1e-6


def test_verificador_personal_detecta_violaciones(inst):
    prog = {0: ("CCH-01", 0.0, 2.0), 12: ("CCH-01", 2.0, 3.0)}
    hab = {"w1": {"CCH-01"}, "w2": {"PLE-01"}}
    assert any(v.startswith("L1") for v in verificar_personal(inst, prog, (), {("F", 0): [], ("F", 12): ["w1"]}, hab))
    assert any(v.startswith("L2") for v in verificar_personal(inst, prog, (), {("F", 0): ["w2"], ("F", 12): ["w1"]}, hab))
    assert any(v.startswith("L5") for v in verificar_personal(inst, prog, (), {("F", 0): ["w1"], ("F", 12): ["w1"]}, hab,
                                                              ausentes={"w1"}))
    solape = {0: ("CCH-01", 0.0, 2.0), 1: ("PLE-01", 1.0, 2.0)}
    hab2 = {"w1": {"CCH-01", "PLE-01"}}
    assert any(v.startswith("L3") for v in verificar_personal(inst, solape, (), {("F", 0): ["w1"], ("F", 1): ["w1"]}, hab2))


def test_personal_insuficiente_detiene_con_mensaje_claro(datos, inst):
    dot = pers.dotacion(datos, datos.operarios[13:])          # con 13 trabajadores nadie opera HOR-01
    with pytest.raises(sim.ErrorSimulacion, match="personal insuficiente"):
        sim.simular(datos, inst, "FIFO", "CONV", [], dot=dot)


def test_reparacion_laboral_en_simulacion(datos, inst):
    """Con 14 trabajadores el certificado falla (déficit en MAN-01): se reservan trabajadores y se verifica."""
    dot = pers.dotacion(datos, datos.operarios[14:])
    res = sim.simular(datos, inst, "EDD", "EDD", ["F01", "F06"], dot=dot, asignar_personal=True, tl_personal=60)
    assert res.modo_personal == "REPARACION_LABORAL"
    assert res.verificacion["total"] == 0
    assert res.asignacion_info["violaciones"] == 0


def _inst_dos_maquinas():
    from types import SimpleNamespace
    from sagapi.instancia import Instancia
    jobs = [dict(idx=j, id=f"J{j}", familia="F", producto="X", q=1, r=0.0, d=2.0, w=1.0, P=100.0, pdia=1.0, valor=1.0,
                 tope=1.0) for j in range(2)]
    ops = [dict(idx=j, job=j, pos=0, paso=1, operacion="op", principal=m, trato="POR_UNIDAD", setup_min=0, min_unidad=1,
                lote=1, q=1, crew=1, interrumpible=True) for j, m in enumerate(("A", "B"))]
    return Instancia(SimpleNamespace(recuperacion=[]), jobs, ops, {0: [0], 1: [1]}, {0: ["A"], 1: ["B"]},
                     {(0, "A"): 2.0, (1, "B"): 2.0}, ["A", "B"], {}, {"A": ["A"], "B": ["B"]}, 4.0)


def test_un_solo_trabajador_obliga_a_secuenciar():
    """Dos máquinas y una sola persona habilitada para ambas: no pueden operar a la vez."""
    from sagapi import estado, optimizacion as opt
    from sagapi.solver import Estado
    inst = _inst_dos_maquinas()
    dot = Dotacion(["w1"], {"w1": {"A", "B"}})
    assert not pers.certificado_cobertura(dot, inst)["ok"]
    sub = estado.subproblema_inicial(inst)
    sol = reglas.edd(sub, personal=EstadoPersonal(dot))
    inicios = sorted(S for (m, S) in sol.values())
    assert inicios == [0.0, 2.0]
    r = opt.optimizar(sub, tl=10, personal=EstadoPersonal(dot))
    assert sorted(S for (m, S) in r["sol"].values()) == [0.0, 2.0]
    assert r["reparacion_laboral"] and r["estado_global"] == Estado.HEURISTICA   # nunca se declara óptimo
    prog = {o: (m, S, S + 2.0) for o, (m, S) in r["sol"].items()}
    a = pers.asignar_trabajadores(inst, prog, dot, tl=10)
    assert a["violaciones"] == [] and a["asignacion"] == {("F", 0): ["w1"], ("F", 1): ["w1"]}
