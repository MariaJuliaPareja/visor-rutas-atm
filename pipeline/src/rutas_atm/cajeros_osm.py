"""CMP-01 Preparacion de datos: catalogo de cajeros reales de Arequipa desde OpenStreetMap.

Consulta la API Overpass por cajeros (amenity=atm) y agencias con cajero (amenity=bank) cuyo nombre,
marca u operador coincida con la entidad pedida (por defecto BBVA). Son ubicaciones PUBLICAS publicadas
en OpenStreetMap, no datos operativos del banco (montos, horarios de carga, rutas actuales), asi que el
proyecto sigue sin usar informacion reservada de ninguna entidad (RNF06).

Los datos de OpenStreetMap estan bajo licencia ODbL: el catalogo guarda la atribucion y el visor la muestra.
"""

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

OVERPASS = "https://overpass-api.de/api/interpreter"
# Arequipa metropolitana: Cercado, Yanahuara, Cayma, Cerro Colorado, JLByR, Paucarpata, Socabaya, etc.
BBOX_AREQUIPA = (-16.48, -71.62, -16.33, -71.47)  # sur, oeste, norte, este
ATRIBUCION = "© Colaboradores de OpenStreetMap, datos bajo licencia ODbL (openstreetmap.org/copyright)"


class ErrorDeCatalogo(ValueError):
    """No se pudo obtener o leer el catalogo de cajeros."""


def consulta_overpass(bbox: tuple = BBOX_AREQUIPA) -> str:
    s, o, n, e = bbox
    caja = f"({s},{o},{n},{e})"
    return (f'[out:json][timeout:60];(nwr["amenity"="atm"]{caja};'
            f'nwr["amenity"="bank"]["atm"="yes"]{caja};);out center tags;')


def _coincide(tags: dict, entidad: str) -> bool:
    patron = re.compile(re.escape(entidad), re.IGNORECASE)
    return any(patron.search(tags.get(k, "")) for k in ("name", "brand", "operator", "network"))


def _direccion(tags: dict) -> str | None:
    calle = tags.get("addr:street")
    if not calle:
        return None
    numero = tags.get("addr:housenumber")
    return f"{calle} {numero}" if numero else calle


def extraer_cajeros(datos: dict, entidad: str = "BBVA") -> list[dict]:
    """Filtra la respuesta de Overpass y devuelve cajeros ordenados de forma estable (por osm_id)."""
    cajeros, vistos = [], set()
    for el in datos.get("elements", []):
        tags = el.get("tags", {})
        if not _coincide(tags, entidad):
            continue
        lat = el.get("lat", el.get("center", {}).get("lat"))
        lon = el.get("lon", el.get("center", {}).get("lon"))
        if lat is None or lon is None:
            continue
        clave = (round(lat, 5), round(lon, 5))  # el mismo cajero mapeado como nodo y como agencia
        if clave in vistos:
            continue
        vistos.add(clave)
        cajeros.append({
            "osm_id": f"{el['type']}/{el['id']}",
            "nombre": tags.get("name") or f"Cajero {entidad}",
            "direccion": _direccion(tags),
            "latitud": round(float(lat), 6),
            "longitud": round(float(lon), 6),
        })
    return sorted(cajeros, key=lambda c: c["osm_id"])


def descargar(entidad: str = "BBVA", bbox: tuple = BBOX_AREQUIPA, url: str = OVERPASS,
              timeout: float = 90.0, abrir=urllib.request.urlopen) -> dict:
    """Descarga el catalogo de cajeros de la entidad dentro del recuadro."""
    cuerpo = urllib.parse.urlencode({"data": consulta_overpass(bbox)}).encode()
    peticion = urllib.request.Request(url, data=cuerpo, headers={"User-Agent": "visor-rutas-atm/0.9 (tesis UCSM)"})
    try:
        with abrir(peticion, timeout=timeout) as respuesta:
            datos = json.loads(respuesta.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        raise ErrorDeCatalogo(f"No se pudo consultar OpenStreetMap (Overpass): {exc}") from exc
    cajeros = extraer_cajeros(datos, entidad)
    if not cajeros:
        raise ErrorDeCatalogo(f"OpenStreetMap no tiene cajeros de {entidad!r} en el recuadro {bbox}")
    return {
        "entidad": entidad,
        "fuente": "OpenStreetMap (API Overpass)",
        "atribucion": ATRIBUCION,
        "descargado": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "recuadro": list(bbox),
        "cajeros": cajeros,
    }


def guardar_catalogo(catalogo: dict, ruta: Path) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps(catalogo, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def cargar_catalogo(ruta: Path) -> dict:
    try:
        catalogo = json.loads(Path(ruta).read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ErrorDeCatalogo(
            f"No existe el catalogo {ruta}. Descargalo con: python -m rutas_atm --descargar-cajeros BBVA") from exc
    except json.JSONDecodeError as exc:
        raise ErrorDeCatalogo(f"El catalogo {ruta} no es JSON valido: {exc}") from exc
    if not catalogo.get("cajeros"):
        raise ErrorDeCatalogo(f"El catalogo {ruta} no tiene cajeros")
    return catalogo
