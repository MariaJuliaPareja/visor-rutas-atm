import io
import json
import urllib.error

import numpy as np
import pytest

from rutas_atm.distancias_viales import ErrorDeDistancias, matriz_vial
from rutas_atm.preparacion_datos import generar_instancia

COORDS = [(-16.39, -71.53), (-16.40, -71.52), (-16.41, -71.54)]


def abridor(cuerpo):
    consultas = []

    def abrir(url, timeout):
        consultas.append(url)
        return io.BytesIO(json.dumps(cuerpo).encode())
    abrir.consultas = consultas
    return abrir


def test_convierte_a_km_y_simetriza_las_calles_de_un_sentido():
    abrir = abridor({"code": "Ok", "distances": [[0, 1000, 3000], [1400, 0, 2000], [3000, 2000, 0]]})
    d = matriz_vial(COORDS, url="https://osrm.local", abrir=abrir)
    assert d[0, 1] == d[1, 0] == pytest.approx(1.2)
    assert np.allclose(d, d.T) and np.all(np.diag(d) == 0)
    assert "/table/v1/driving/-71.530000,-16.390000;" in abrir.consultas[0]  # longitud,latitud


@pytest.mark.parametrize("cuerpo", [
    {"code": "InvalidQuery", "message": "x"},
    {"code": "Ok", "distances": [[0, None, 1], [1, 0, 1], [1, 1, 0]]},
    {"code": "Ok", "distances": [[0, 1], [1, 0]]},
])
def test_rechaza_respuestas_invalidas(cuerpo):
    with pytest.raises(ErrorDeDistancias):
        matriz_vial(COORDS, abrir=abridor(cuerpo))


def test_error_de_red_controlado():
    def abrir(url, timeout):
        raise urllib.error.URLError("sin conexion")
    with pytest.raises(ErrorDeDistancias, match="RUTAS_DISTANCIA=linea_recta"):
        matriz_vial(COORDS, abrir=abrir)


def test_instancia_vial_usa_la_matriz_por_calles():
    def plana(c):
        return np.full((len(c), len(c)), 2.0) - 2 * np.eye(len(c))
    inst = generar_instancia(4, metrica="vial", calcular_vial=plana)
    assert inst.metrica == "vial" and inst.distancias[0, 1] == 2.0
