import itertools

import pytest

from rutas_atm.formulacion_tsp import construir_modelo, decodificar
from rutas_atm.linea_base import held_karp
from rutas_atm.preparacion_datos import distancia_ruta, generar_instancia


def estado_fundamental(bqm):
    variables = list(bqm.variables)
    mejor = min(itertools.product([0, 1], repeat=len(variables)),
                key=lambda bits: bqm.energy(dict(zip(variables, bits, strict=False))))
    return dict(zip(variables, mejor, strict=False))


def test_estado_fundamental_qubo_es_la_ruta_optima():
    d = generar_instancia(3, semilla=5).distancias
    modelo = construir_modelo("QUBO", d)
    secuencia, factible = decodificar(modelo, estado_fundamental(modelo.bqm))
    assert factible
    assert distancia_ruta(secuencia, d) == pytest.approx(held_karp(d)[0])


@pytest.mark.parametrize("n,esperado", [(3, 30), (4, 54), (5, 84), (6, 120)])
def test_numero_de_variables(n, esperado):
    d = generar_instancia(n).distancias
    assert construir_modelo("GPS", d).num_variables == esperado
    assert construir_modelo("QUBO", d).num_variables == n * n


def test_qubo_con_cajero_repetido_es_infactible():
    d = generar_instancia(3).distancias
    modelo = construir_modelo("QUBO", d)
    bits = {v: 0 for v in modelo.bqm.variables}
    for i, p in [(0, 0), (1, 1), (1, 2)]:  # el cajero 1 en dos posiciones, el 2 nunca
        bits[i * 3 + p] = 1
    secuencia, factible = decodificar(modelo, bits)
    assert not factible
    assert secuencia == [0, 1, 1]  # aparece todo lo activo, sin "reparar"


def test_factibilidad_se_evalua_sobre_la_ruta_decodificada():
    # DEC-03: dos cajeros en la misma posicion y una posicion vacia producen igual una
    # ruta que visita cada cajero una vez; se considera factible a nivel de ruta.
    d = generar_instancia(3).distancias
    modelo = construir_modelo("QUBO", d)
    bits = {v: 0 for v in modelo.bqm.variables}
    for i, p in [(0, 0), (1, 1), (2, 1)]:
        bits[i * 3 + p] = 1
    assert decodificar(modelo, bits) == ([0, 1, 2], True)


def test_gps_con_ciclo_corto_es_infactible():
    d = generar_instancia(4).distancias
    modelo = construir_modelo("GPS", d)
    bits = {v: 0 for v in modelo.bqm.variables}
    for arista in [(0, 1, 1), (1, 2, 1), (2, 1, 1)]:  # 0 -> 1 -> 2 -> 1: nunca visita el 3
        bits[modelo.var_index[arista]] = 1
    secuencia, factible = decodificar(modelo, bits)
    assert not factible
    assert secuencia == [0, 1, 2, 1]


def test_formulacion_desconocida():
    with pytest.raises(ValueError):
        construir_modelo("MTZ", generar_instancia(3).distancias)
