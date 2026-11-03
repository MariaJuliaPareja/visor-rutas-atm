"""Configuracion por ambiente. Todo valor que cambia entre ambientes se lee de variables de entorno.

El token de D-Wave Leap NO se lee aqui: lo toma directamente el Ocean SDK desde DWAVE_API_TOKEN
o desde su archivo de configuracion local, de modo que nunca pasa por el codigo del proyecto.
"""

import os
from dataclasses import dataclass, replace
from pathlib import Path

SAMPLERS_VALIDOS = ("simulado", "qpu", "ibm")
DISTANCIAS_VALIDAS = ("linea_recta", "vial")
OSRM_PUBLICO = "https://router.project-osrm.org"


class ErrorDeConfiguracion(ValueError):
    """La configuracion del ambiente es invalida."""


def cargar_env(ruta: Path) -> list[str]:
    """Carga un archivo .env sencillo (CLAVE=valor). No pisa variables ya definidas en el entorno,
    de modo que la configuracion del ambiente (CI, terminal) siempre tiene prioridad. Devuelve las claves cargadas."""
    if not ruta.is_file():
        return []
    cargadas = []
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        clave, valor = (p.strip() for p in linea.split("=", 1))
        if clave and clave not in os.environ:
            os.environ[clave] = valor.strip("'\"")
            cargadas.append(clave)
    return cargadas


def _entero(nombre: str, por_defecto: int, minimo: int = 1) -> int:
    crudo = os.getenv(nombre)
    if crudo is None or crudo == "":
        return por_defecto
    try:
        valor = int(crudo)
    except ValueError as exc:
        raise ErrorDeConfiguracion(f"{nombre} debe ser un entero; se recibio {crudo!r}") from exc
    if valor < minimo:
        raise ErrorDeConfiguracion(f"{nombre} debe ser >= {minimo}; se recibio {valor}")
    return valor


@dataclass(frozen=True)
class Configuracion:
    sampler: str
    num_reads: int
    semilla: int
    directorio_salida: Path
    nivel_log: str
    annealing_time_us: int = 20
    distancia: str = "linea_recta"
    osrm_url: str = OSRM_PUBLICO
    qaoa_reps: int = 1

    @classmethod
    def desde_entorno(cls) -> "Configuracion":
        sampler = os.getenv("RUTAS_SAMPLER", "simulado").strip().lower()
        if sampler not in SAMPLERS_VALIDOS:
            raise ErrorDeConfiguracion(
                f"RUTAS_SAMPLER debe ser uno de {SAMPLERS_VALIDOS}; se recibio {sampler!r}"
            )
        distancia = os.getenv("RUTAS_DISTANCIA", "linea_recta").strip().lower()
        if distancia not in DISTANCIAS_VALIDAS:
            raise ErrorDeConfiguracion(
                f"RUTAS_DISTANCIA debe ser una de {DISTANCIAS_VALIDAS}; se recibio {distancia!r}"
            )
        return cls(
            sampler=sampler,
            num_reads=_entero("RUTAS_NUM_READS", 200),
            semilla=_entero("RUTAS_SEMILLA", 42, minimo=0),
            directorio_salida=Path(os.getenv("RUTAS_DIR_SALIDA", "salidas")),
            nivel_log=os.getenv("RUTAS_NIVEL_LOG", "INFO").upper(),
            annealing_time_us=_entero("RUTAS_ANNEALING_TIME", 20),
            distancia=distancia,
            qaoa_reps=_entero("RUTAS_QAOA_REPS", 1),
            osrm_url=os.getenv("RUTAS_OSRM_URL", OSRM_PUBLICO).strip() or OSRM_PUBLICO,
        )

    def con_sampler(self, sampler: str) -> "Configuracion":
        if sampler not in SAMPLERS_VALIDOS:
            raise ErrorDeConfiguracion(f"El sampler debe ser uno de {SAMPLERS_VALIDOS}; se recibio {sampler!r}")
        return replace(self, sampler=sampler)

    def con_distancia(self, distancia: str) -> "Configuracion":
        if distancia not in DISTANCIAS_VALIDAS:
            raise ErrorDeConfiguracion(f"La distancia debe ser una de {DISTANCIAS_VALIDAS}; se recibio {distancia!r}")
        return replace(self, distancia=distancia)
