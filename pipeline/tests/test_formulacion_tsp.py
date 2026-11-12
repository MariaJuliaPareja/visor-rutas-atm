import itertools
from pathlib import Path

import numpy as np
import pytest

from rutas_atm.experimento import cargar_crudos
from rutas_atm.formulacion_tsp import construir_modelo, decodificar, es_permutacion, factible_estricto
from rutas_atm.linea_base import held_karp
from rutas_atm.preparacion_datos import distancia_ruta, generar_instancia

CRUDOS = Path(__file__).resolve().parents[2] / "salidas" / "crudos"
RECOCIDO = (
    "corridas_i94_n4_simulado_20261111-213722-183.pkl",
    "corridas_i95_n5_simulado_20261111-213734-436.pkl",
)


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
    # La secuencia sigue siendo best-effort: dos cajeros en la misma posicion pueden
    # deletrear una permutacion. El flag estricto de esa cadena es falso.
    d = generar_instancia(3).distancias
    modelo = construir_modelo("QUBO", d)
    bits = {v: 0 for v in modelo.bqm.variables}
    for i, p in [(0, 0), (1, 1), (2, 1)]:
        bits[i * 3 + p] = 1
    assert decodificar(modelo, bits) == ([0, 1, 2], True)
    assert factible_estricto(modelo, bits) is False


def test_one_hot_completo_es_estricto():
    d = generar_instancia(3).distancias
    modelo = construir_modelo("QUBO", d)
    bits = {v: 0 for v in modelo.bqm.variables}
    for i, p in [(0, 0), (1, 1), (2, 2)]:
        bits[i * 3 + p] = 1
    assert factible_estricto(modelo, bits) is True


def test_gps_con_ciclo_corto_es_infactible():
    d = generar_instancia(4).distancias
    modelo = construir_modelo("GPS", d)
    bits = {v: 0 for v in modelo.bqm.variables}
    for arista in [(0, 1, 1), (1, 2, 1), (2, 1, 1)]:  # 0 -> 1 -> 2 -> 1: nunca visita el 3
        bits[modelo.var_index[arista]] = 1
    secuencia, factible = decodificar(modelo, bits)
    assert not factible
    assert secuencia == [0, 1, 2, 1]


def _codificar_gps(modelo, ruta, mascara=0):
    fin = modelo.N + 1
    camino = list(ruta) + [fin]
    tour = set(zip(camino, camino[1:]))
    bits = {v: 0 for v in modelo.bqm.variables}
    vi = modelo.var_index
    pares = {(i, j) for (i, j, _) in vi}
    for i, j in pares:
        if (i, j) in tour:
            bits[vi[(i, j, 1)]] = 1
        elif (j, i) in tour:
            bits[vi[(i, j, 2)]] = 1
    libres = []
    vistos = set()
    for i, j in pares:
        if (i, j) in vistos or (j, i) in vistos:
            continue
        vistos.add((i, j))
        vistos.add((j, i))
        if (i, j) not in tour and (j, i) not in tour:
            a, b = (i, j) if i < j else (j, i)
            libres.append((a, b))
    for k, (a, b) in enumerate(libres):
        for r in range(3):
            bits[vi[(a, b, r)]] = 0
            bits[vi[(b, a, r)]] = 0
        if (mascara >> k) & 1:
            bits[vi[(a, b, 2)]] = 1
            bits[vi[(b, a, 0)]] = 1
        else:
            bits[vi[(b, a, 2)]] = 1
            bits[vi[(a, b, 0)]] = 1
    return bits


def test_codificaciones_gps_de_un_tour_son_estrictas():
    d = generar_instancia(3, semilla=5).distancias
    modelo = construir_modelo("GPS", d)
    for ruta in ([0, 1, 2], [0, 2, 1]):
        for mascara in range(4):
            bits = _codificar_gps(modelo, ruta, mascara)
            secuencia, permuta = decodificar(modelo, bits)
            assert factible_estricto(modelo, bits) and permuta
            assert es_permutacion(secuencia, 3)


def test_cadena_aleatoria_n4_no_es_estricta():
    d = generar_instancia(4, semilla=1).distancias
    rng = np.random.default_rng(42)
    for formulacion in ("QUBO", "GPS"):
        modelo = construir_modelo(formulacion, d)
        variables = list(modelo.bqm.variables)
        verdaderos = 0
        for _ in range(1000):
            bits = {v: int(rng.integers(0, 2)) for v in variables}
            secuencia, _ = decodificar(modelo, bits)
            verdaderos += factible_estricto(modelo, bits) and es_permutacion(secuencia, 4)
        assert verdaderos <= 5


@pytest.mark.skipif(not all((CRUDOS / nombre).exists() for nombre in RECOCIDO), reason="lotes locales")
def test_recocido_simulado_sigue_factible():
    for nombre in RECOCIDO:
        lote = cargar_crudos(CRUDOS / nombre)
        distancias = lote.instancia.distancias
        for corrida in lote.corridas:
            modelo = construir_modelo(corrida.formulacion, distancias)
            secuencia, _ = decodificar(modelo, corrida.bits)
            assert corrida.factible
            assert factible_estricto(modelo, corrida.bits) and es_permutacion(secuencia, modelo.n)


def test_formulacion_desconocida():
    with pytest.raises(ValueError):
        construir_modelo("MTZ", generar_instancia(3).distancias)
