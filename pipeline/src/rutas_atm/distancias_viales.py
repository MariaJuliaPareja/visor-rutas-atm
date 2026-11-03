"""CMP-01 Preparacion de datos: matriz de distancias por calles con OSRM sobre OpenStreetMap.

Usa el servicio /table de OSRM (https://project-osrm.org), que calcula la distancia de manejo entre
cada par de cajeros siguiendo la red vial de OpenStreetMap. Por defecto apunta al servidor publico
de demostracion; para lotes grandes conviene un OSRM propio (RUTAS_OSRM_URL).

Las calles de un solo sentido hacen que ir de A a B no mida lo mismo que de B a A. Las formulaciones
GPS y QUBO de este proyecto asumen una matriz simetrica, asi que se usa el promedio de ambos sentidos
(DEC-07).
"""

import json
import urllib.error
import urllib.request

import numpy as np

OSRM_PUBLICO = "https://router.project-osrm.org"


class ErrorDeDistancias(ValueError):
    """No se pudo obtener la matriz de distancias por calles."""


def _coordenadas_osrm(coordenadas: list) -> str:
    # OSRM espera longitud,latitud
    return ";".join(f"{lon:.6f},{lat:.6f}" for lat, lon in coordenadas)


def matriz_vial(coordenadas: list, url: str = OSRM_PUBLICO, timeout: float = 30.0,
                abrir=urllib.request.urlopen, con_tiempos: bool = False):
    """Matriz simetrica de distancias por calles, en km. Con con_tiempos=True devuelve (km, minutos)."""
    anotaciones = "distance,duration" if con_tiempos else "distance"
    consulta = f"{url.rstrip('/')}/table/v1/driving/{_coordenadas_osrm(coordenadas)}?annotations={anotaciones}"
    try:
        with abrir(consulta, timeout=timeout) as respuesta:
            datos = json.loads(respuesta.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise ErrorDeDistancias(
            f"No se pudo consultar el servicio de rutas en {url}: {exc}. "
            "Revisa la conexion o usa RUTAS_DISTANCIA=linea_recta"
        ) from exc
    except json.JSONDecodeError as exc:
        raise ErrorDeDistancias(f"El servicio de rutas devolvio una respuesta que no es JSON: {exc}") from exc

    if datos.get("code") != "Ok":
        raise ErrorDeDistancias(f"El servicio de rutas respondio {datos.get('code')}: {datos.get('message', '')}")
    metros = datos.get("distances")
    n = len(coordenadas)
    if not metros or len(metros) != n or any(len(fila) != n for fila in metros):
        raise ErrorDeDistancias("El servicio de rutas no devolvio una matriz de n x n distancias")
    if any(x is None for fila in metros for x in fila):
        raise ErrorDeDistancias("Algun cajero no tiene camino por calles hacia otro (OSRM devolvio null)")

    d = _simetrica(np.array(metros, dtype=float) / 1000.0)  # DEC-07: promedio de ambos sentidos
    if not con_tiempos:
        return d
    segundos = datos.get("durations")
    if not segundos or any(x is None for fila in segundos for x in fila):
        raise ErrorDeDistancias("El servicio de rutas no devolvio los tiempos de manejo")
    return d, _simetrica(np.array(segundos, dtype=float) / 60.0)


def _simetrica(m: np.ndarray) -> np.ndarray:
    m = (m + m.T) / 2.0
    np.fill_diagonal(m, 0.0)
    return m
