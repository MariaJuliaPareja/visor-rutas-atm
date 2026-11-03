import itertools

import pytest

from rutas_atm.held_karp import held_karp
from rutas_atm.instancia import distancia_ruta, generar_instancia


def fuerza_bruta(d):
    n = d.shape[0]
    mejor = min(itertools.permutations(range(1, n)), key=lambda p: distancia_ruta([0, *p], d))
    return distancia_ruta([0, *mejor], d)


@pytest.mark.parametrize("n,semilla", [(3, 1), (4, 7), (5, 42), (6, 3), (7, 11)])
def test_held_karp_coincide_con_fuerza_bruta(n, semilla):
    d = generar_instancia(n, semilla=semilla).distancias
    distancia, ruta = held_karp(d)
    assert distancia == pytest.approx(fuerza_bruta(d))
    assert sorted(ruta) == list(range(n)) and ruta[0] == 0
    assert distancia_ruta(ruta, d) == pytest.approx(distancia)


def test_held_karp_devuelve_enteros_de_python():
    _, ruta = held_karp(generar_instancia(5).distancias)
    assert all(type(k) is int for k in ruta)  # INC-01: numpy.int64 rompia la validacion del esquema


def test_rechaza_instancias_fuera_de_rango():
    with pytest.raises(ValueError):
        generar_instancia(2)
