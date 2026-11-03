import io
import json
import urllib.error

import numpy as np
import pytest

from rutas_atm import experimento
from rutas_atm.cajeros_osm import ErrorDeCatalogo, cargar_catalogo, descargar, extraer_cajeros, guardar_catalogo
from rutas_atm.config import Configuracion
from rutas_atm.conversor_resultados import convertir
from rutas_atm.preparacion_datos import instancia_desde_catalogo
from rutas_atm.validacion import validar

# Respuesta de Overpass de prueba: ubicaciones inventadas, no son cajeros reales.
RESPUESTA = {"elements": [
    {"type": "node", "id": 3, "lat": -16.3990, "lon": -71.5370, "tags": {"amenity": "atm", "brand": "BBVA",
                                                                        "addr:street": "Calle Mercaderes",
                                                                        "addr:housenumber": "100"}},
    {"type": "node", "id": 1, "lat": -16.4010, "lon": -71.5300,
     "tags": {"amenity": "atm", "operator": "BBVA Continental"}},
    {"type": "way", "id": 7, "center": {"lat": -16.3950, "lon": -71.5400},
     "tags": {"amenity": "bank", "atm": "yes", "name": "BBVA Yanahuara"}},
    {"type": "node", "id": 9, "lat": -16.3960, "lon": -71.5330, "tags": {"amenity": "atm", "brand": "BCP"}},
    # el mismo cajero mapeado dos veces
    {"type": "node", "id": 4, "lat": -16.3990, "lon": -71.5370, "tags": {"amenity": "atm", "name": "BBVA"}},
    {"type": "node", "id": 5, "lat": -16.4100, "lon": -71.5200, "tags": {"amenity": "atm", "network": "bbva"}},
]}


def abridor(cuerpo):
    def abrir(peticion, timeout):
        return io.BytesIO(json.dumps(cuerpo).encode())
    return abrir


def test_filtra_por_entidad_y_quita_duplicados():
    cajeros = extraer_cajeros(RESPUESTA, "BBVA")
    assert [c["osm_id"] for c in cajeros] == ["node/1", "node/3", "node/5", "way/7"]
    assert cajeros[1]["direccion"] == "Calle Mercaderes 100"
    assert cajeros[3]["latitud"] == -16.395  # una agencia usa el centro del edificio


def test_descarga_y_guarda_con_atribucion(tmp_path):
    catalogo = descargar("BBVA", abrir=abridor(RESPUESTA))
    assert catalogo["entidad"] == "BBVA" and "ODbL" in catalogo["atribucion"]
    ruta = tmp_path / "cajeros.json"
    guardar_catalogo(catalogo, ruta)
    assert cargar_catalogo(ruta)["cajeros"] == catalogo["cajeros"]


def test_errores_controlados(tmp_path):
    with pytest.raises(ErrorDeCatalogo, match="no tiene cajeros"):
        descargar("Scotiabank", abrir=abridor(RESPUESTA))

    def sin_red(peticion, timeout):
        raise urllib.error.URLError("sin conexion")
    with pytest.raises(ErrorDeCatalogo, match="Overpass"):
        descargar(abrir=sin_red, espera_s=0)
    with pytest.raises(ErrorDeCatalogo, match="--descargar-cajeros"):
        cargar_catalogo(tmp_path / "no-existe.json")


@pytest.fixture
def catalogo():
    return descargar("BBVA", abrir=abridor(RESPUESTA))


def test_instancia_real_con_base_de_operaciones(catalogo):
    inst = instancia_desde_catalogo(catalogo, 4, semilla=1, deposito=(-16.3989, -71.5350), radio_km=4)
    assert inst.n == 4 and inst.coordenadas[0] == (-16.3989, -71.535)
    assert inst.etiquetas[0]["rol"] == "deposito"
    assert all(e["rol"] == "cajero" and e["osm_id"] for e in inst.etiquetas[1:])
    assert inst.fuente["tipo"] == "osm"


def test_rechaza_si_no_hay_cajeros_suficientes_cerca(catalogo):
    with pytest.raises(ValueError, match="RUTAS_RADIO_KM"):
        instancia_desde_catalogo(catalogo, 5, radio_km=0.1)


def test_lote_con_cajeros_reales_y_tiempos(tmp_path, monkeypatch, catalogo):
    ruta = tmp_path / "cajeros.json"
    guardar_catalogo(catalogo, ruta)

    def falsa_vial(coordenadas, url, con_tiempos):
        n = len(coordenadas)
        d = np.ones((n, n)) - np.eye(n)
        return d, 3 * d
    monkeypatch.setattr(experimento, "matriz_vial", falsa_vial)
    monkeypatch.setenv("RUTAS_FUENTE", "osm")
    monkeypatch.setenv("RUTAS_CATALOGO", str(ruta))
    monkeypatch.setenv("RUTAS_DISTANCIA", "vial")
    monkeypatch.setenv("RUTAS_NUM_READS", "20")
    doc = convertir(experimento.ejecutar_experimento(4, 1, Configuracion.desde_entorno()))
    assert validar(doc)[0] == []
    inst = doc["instancia"]
    assert inst["cajeros"][0]["nombre"] == "Base de operaciones"
    assert inst["matriz_tiempos"]["tiempos"][0][1] == 3.0
    assert inst["fuente"]["entidad"] == "BBVA"


def test_usa_un_espejo_si_el_principal_esta_saturado():
    llamadas = []

    def abrir(peticion, timeout):
        llamadas.append(peticion.full_url)
        if "overpass-api.de" in peticion.full_url:
            raise urllib.error.HTTPError(peticion.full_url, 502, "Bad Gateway", {}, None)
        return io.BytesIO(json.dumps(RESPUESTA).encode())
    catalogo = descargar("BBVA", abrir=abrir, espera_s=0)
    assert len(catalogo["cajeros"]) == 4
    assert llamadas[:2] == [llamadas[0]] * 2 and "kumi" in llamadas[2]  # 2 intentos y luego el espejo
