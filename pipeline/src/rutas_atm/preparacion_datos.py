"""CMP-01 Preparacion de datos: instancias sinteticas de cajeros y su matriz de distancias.

Las coordenadas son ficticias, generadas alrededor del centro de Arequipa con semilla fija,
para no usar datos operativos reales de ninguna entidad bancaria (RNF06).
"""

import math
from dataclasses import dataclass

import numpy as np

CENTRO_AREQUIPA = (-16.3989, -71.5350)
RADIO_TIERRA_KM = 6371.0088
MIN_CAJEROS, MAX_CAJEROS = 3, 100
METRICAS_VALIDAS = ("linea_recta", "vial")


@dataclass(frozen=True)
class Instancia:
    id_instancia: int
    tipo: str
    coordenadas: list  # [(lat, lon), ...]; el indice es el id_cajero
    distancias: np.ndarray  # km, simetrica, diagonal en 0
    metrica: str = "linea_recta"  # linea_recta (haversine) o vial (por calles, OSRM)
    tiempos: np.ndarray | None = None  # minutos de manejo, solo con metrica vial
    etiquetas: tuple | None = None  # por nodo: {"nombre", "direccion", "osm_id", "rol"}
    fuente: dict | None = None  # {"tipo": "sintetica" | "osm", "entidad", "atribucion", ...}

    @property
    def n(self) -> int:
        return len(self.coordenadas)


def haversine_km(a: tuple, b: tuple) -> float:
    lat1, lon1, lat2, lon2 = map(math.radians, (*a, *b))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 2 * RADIO_TIERRA_KM * math.asin(math.sqrt(h))


def matriz_distancias(coordenadas: list) -> np.ndarray:
    n = len(coordenadas)
    d = np.zeros((n, n))
    for i in range(n):
        for j in range(i + 1, n):
            d[i, j] = d[j, i] = haversine_km(coordenadas[i], coordenadas[j])
    return d


def generar_instancia(n: int, semilla: int = 42, id_instancia: int = 1,
                      radio_grados: float = 0.03, metrica: str = "linea_recta",
                      calcular_vial=None) -> Instancia:
    """Genera n cajeros dentro de un cuadrado de +-radio_grados alrededor del centro de Arequipa.

    Con metrica="vial" las distancias siguen las calles de OpenStreetMap; calcular_vial recibe las
    coordenadas y devuelve la matriz en km (por defecto, distancias_viales.matriz_vial).
    """
    if metrica not in METRICAS_VALIDAS:
        raise ValueError(f"La metrica debe ser una de {METRICAS_VALIDAS}; se recibio {metrica!r}")
    if not MIN_CAJEROS <= n <= MAX_CAJEROS:
        raise ValueError(f"El numero de cajeros debe estar entre {MIN_CAJEROS} y {MAX_CAJEROS} (RNF05); se recibio {n}")
    rng = np.random.default_rng(semilla)
    desplazamientos = rng.uniform(-radio_grados, radio_grados, size=(n, 2))
    coordenadas = [(round(CENTRO_AREQUIPA[0] + dy, 6), round(CENTRO_AREQUIPA[1] + dx, 6))
                   for dy, dx in desplazamientos]
    tipo = "reducida" if n <= 10 else "representativa"
    distancias, tiempos = _matrices(coordenadas, metrica, calcular_vial)
    return Instancia(id_instancia, tipo, coordenadas, distancias, metrica, tiempos,
                     fuente={"tipo": "sintetica", "descripcion": "Coordenadas ficticias alrededor de Arequipa"})


def _matrices(coordenadas: list, metrica: str, calcular_vial) -> tuple:
    """(distancias km, tiempos min | None). calcular_vial puede devolver la matriz o (km, min)."""
    if metrica != "vial":
        return matriz_distancias(coordenadas), None
    if calcular_vial is None:
        from .distancias_viales import matriz_vial

        def calcular_vial(c):
            return matriz_vial(c, con_tiempos=True)
    resultado = calcular_vial(coordenadas)
    return resultado if isinstance(resultado, tuple) else (resultado, None)


def instancia_desde_catalogo(catalogo: dict, n: int, semilla: int = 42, id_instancia: int = 1,
                             deposito: tuple = CENTRO_AREQUIPA, radio_km: float = 4.0,
                             metrica: str = "linea_recta", calcular_vial=None) -> Instancia:
    """Instancia con cajeros reales: el nodo 0 es la base de operaciones y los n-1 restantes se eligen
    al azar (con semilla) entre los cajeros del catalogo a menos de radio_km de la base.

    Los ids siguen el orden del catalogo, como una planilla de reabastecimiento: ese orden es la
    'ruta habitual' con la que el visor compara el ahorro (DEC-09).
    """
    if not MIN_CAJEROS <= n <= MAX_CAJEROS:
        raise ValueError(f"El numero de nodos debe estar entre {MIN_CAJEROS} y {MAX_CAJEROS} (RNF05); se recibio {n}")
    if metrica not in METRICAS_VALIDAS:
        raise ValueError(f"La metrica debe ser una de {METRICAS_VALIDAS}; se recibio {metrica!r}")
    cercanos = [c for c in catalogo["cajeros"]
                if haversine_km(deposito, (c["latitud"], c["longitud"])) <= radio_km]
    if len(cercanos) < n - 1:
        raise ValueError(f"Solo hay {len(cercanos)} cajeros de {catalogo.get('entidad', '?')} a menos de "
                         f"{radio_km} km de la base; se pidieron {n - 1}. Sube RUTAS_RADIO_KM o baja --cajeros")
    rng = np.random.default_rng(semilla)
    indices = sorted(rng.choice(len(cercanos), size=n - 1, replace=False))
    elegidos = [cercanos[i] for i in indices]
    coordenadas = [(round(deposito[0], 6), round(deposito[1], 6))] + [(c["latitud"], c["longitud"]) for c in elegidos]
    etiquetas = ({"nombre": "Base de operaciones", "direccion": None, "osm_id": None, "rol": "deposito"},
                 *({"nombre": c["nombre"], "direccion": c.get("direccion"), "osm_id": c.get("osm_id"),
                    "rol": "cajero"} for c in elegidos))
    distancias, tiempos = _matrices(coordenadas, metrica, calcular_vial)
    fuente = {"tipo": "osm", "entidad": catalogo.get("entidad"), "atribucion": catalogo.get("atribucion"),
              "descargado": catalogo.get("descargado")}
    tipo = "reducida" if n <= 10 else "representativa"
    return Instancia(id_instancia, tipo, coordenadas, distancias, metrica, tiempos, etiquetas, fuente)


def distancia_ruta(secuencia: list, distancias: np.ndarray) -> float:
    """Distancia de una ruta cerrada: recorre la secuencia y vuelve al primer cajero."""
    if len(secuencia) < 2:
        return 0.0
    return float(sum(distancias[secuencia[k], secuencia[(k + 1) % len(secuencia)]]
                     for k in range(len(secuencia))))
