"""Orquestacion del lote experimental (CMP-01 a CMP-04) y resultados crudos en .pkl.

Diseno (Practica 05, CMP-05; Practica 06, controles de recuperacion): el pipeline guarda primero los
resultados crudos en un .pkl, que es la fuente original del lote y no se modifica. El conversor
(CMP-05) transforma ese .pkl en el archivo de intercambio .json; si el .json se pierde o se corrompe,
se regenera desde el .pkl. Cada corrida se agrega al lote en cuanto termina.
"""

import csv
import logging
import pickle
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from .cajeros_osm import cargar_catalogo
from .cliente_dwave import muestrear
from .config import Configuracion
from .distancias_viales import matriz_vial
from .formulacion_tsp import construir_modelo, decodificar, es_permutacion, factible_estricto
from .linea_base import held_karp
from .preparacion_datos import Instancia, distancia_ruta, generar_instancia, instancia_desde_catalogo

log = logging.getLogger("rutas_atm")
FORMULACIONES = ("GPS", "QUBO")
MAXITER_PRODUCCION = 120
COLUMNAS_CSV = (
    "instancia", "formulacion", "replica", "semilla", "maxiter", "optimizador",
    "backend", "shots", "qubits_logicos", "profundidad",
)


@dataclass
class CorridaCruda:
    id_corrida: int
    formulacion: str
    sampler: str
    parametros: dict
    secuencia: list
    factible: bool
    distancia_total: float
    energia: float
    tiempo_anneal_us: float | None
    chain_break_fraction: float | None
    bits: dict


@dataclass
class LoteCrudo:
    instancia: Instancia
    dist_optima: float
    ruta_optima: list
    fecha: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds"))
    corridas: list[CorridaCruda] = field(default_factory=list)


def es_corrida_de_prueba(cfg: Configuracion) -> bool:
    """Un maxiter por debajo del de produccion (120) es una prueba y no puede ir a salidas/."""
    return cfg.maxiter < MAXITER_PRODUCCION


def directorio_de_salida(cfg: Configuracion) -> Path:
    if es_corrida_de_prueba(cfg):
        return Path(cfg.directorio_salida) / "runs_test"
    return cfg.directorio_salida


def nombres_csv(directorio: Path, id_instancia: int, formulaciones, replicas: int, semilla_base: int) -> list[Path]:
    rutas = []
    for formulacion in formulaciones:
        for replica in range(replicas):
            semilla = semilla_base + replica
            rutas.append(Path(directorio) / f"{id_instancia}_{formulacion}_{replica}_{semilla}.csv")
    return rutas


def reservar_csv(rutas: list[Path]) -> None:
    ocupadas = [ruta for ruta in rutas if ruta.exists()]
    if ocupadas:
        raise FileExistsError("CSV ya existente; no se muestrea: " + ", ".join(map(str, ocupadas)))


def _es_salidas(ruta: Path) -> bool:
    return any(parte == "salidas" for parte in Path(ruta).parts)


def _csv_de_replica(directorio: Path, id_instancia: int, corrida: CorridaCruda) -> None:
    """Una fila, un archivo: instancia_formulacion_replica_semilla.csv. Se cierra antes de la replica siguiente."""
    p = corrida.parametros
    semilla = p.get("semilla", p.get("seed"))
    ruta = directorio / f"{id_instancia}_{corrida.formulacion}_{p['replica']}_{semilla}.csv"
    ruta.parent.mkdir(parents=True, exist_ok=True)
    if ruta.exists():
        raise FileExistsError(f"{ruta} ya existe: el pipeline nunca sobrescribe un archivo de resultados")
    profundidad = p.get("profundidad_decompose")
    fila = {
        "instancia": id_instancia,
        "formulacion": corrida.formulacion,
        "replica": p.get("replica"),
        "semilla": "" if semilla is None else semilla,
        "maxiter": "" if p.get("maxiter") is None else p.get("maxiter"),
        "optimizador": p.get("optimizador") or "",
        "backend": p.get("backend") or "",
        "shots": "" if p.get("shots") is None else p.get("shots"),
        "qubits_logicos": "" if p.get("qubits_logicos") is None else p.get("qubits_logicos"),
        "profundidad": "" if profundidad is None else profundidad,
    }
    with ruta.open("w", newline="", encoding="utf-8") as salida:
        escritor = csv.DictWriter(salida, fieldnames=COLUMNAS_CSV)
        escritor.writeheader()
        escritor.writerow(fila)
        salida.flush()


def ejecutar_experimento(cajeros: int, corridas_por_formulacion: int, cfg: Configuracion,
                         id_instancia: int = 1, ruta_pkl: Path | None = None, fabrica_qpu=None,
                         formulaciones=FORMULACIONES, angulos=None, semilla_base=None) -> LoteCrudo:
    calcular_vial = None
    if cfg.distancia == "vial":
        def calcular_vial(coordenadas):
            return matriz_vial(coordenadas, url=cfg.osrm_url, con_tiempos=True)
    if cfg.fuente == "osm":
        catalogo = cargar_catalogo(cfg.catalogo)
        instancia = instancia_desde_catalogo(catalogo, cajeros, semilla=cfg.semilla, id_instancia=id_instancia,
                                             deposito=cfg.base, radio_km=cfg.radio_km,
                                             metrica=cfg.distancia, calcular_vial=calcular_vial)
        log.info("Cajeros reales de %s (OpenStreetMap): base + %d cajeros a menos de %.1f km",
                 catalogo.get("entidad"), cajeros - 1, cfg.radio_km)
    else:
        instancia = generar_instancia(cajeros, semilla=cfg.semilla, id_instancia=id_instancia,
                                      metrica=cfg.distancia, calcular_vial=calcular_vial)
    log.info("Instancia %d: %d cajeros (%s), distancias %s", id_instancia, instancia.n, instancia.tipo,
             "por calles (OSRM)" if instancia.metrica == "vial" else "en linea recta")

    t0 = time.perf_counter()
    dist_optima, ruta_optima = held_karp(instancia.distancias)
    log.info("Held-Karp: %.3f km en %.1f ms, ruta %s", dist_optima, (time.perf_counter() - t0) * 1000, ruta_optima)

    if (ruta_pkl is not None and es_corrida_de_prueba(cfg) and _es_salidas(ruta_pkl)
            and "runs_test" not in Path(ruta_pkl).parts):
        ruta_pkl = directorio_de_salida(cfg) / "crudos" / ruta_pkl.name
    lote = LoteCrudo(instancia, dist_optima, ruta_optima)
    id_corrida = 1
    carpeta_csv = directorio_de_salida(cfg) if es_corrida_de_prueba(cfg) else (
        ruta_pkl.parent.parent if ruta_pkl is not None and ruta_pkl.parent.name == "crudos" else
        (ruta_pkl.parent if ruta_pkl is not None else None)
    )
    base = cfg.semilla if semilla_base is None else semilla_base
    if carpeta_csv is not None:
        reservar_csv(nombres_csv(
            carpeta_csv, id_instancia, formulaciones, corridas_por_formulacion, base))
    for formulacion in formulaciones:
        modelo = construir_modelo(formulacion, instancia.distancias)
        log.info("%s: %d variables binarias", formulacion, modelo.num_variables)
        for replica in range(corridas_por_formulacion):
            semilla = base + replica
            if cfg.sampler == "ibm":
                from .cliente_ibm import muestrear_ibm
                metodo = None if angulos is None else angulos[formulacion]
                r = muestrear_ibm(modelo, cfg.num_reads, semilla, reps=cfg.qaoa_reps,
                                  fabrica_backend=fabrica_qpu, maxiter=cfg.maxiter,
                                  metodo_angulos=metodo, backend_nombre=cfg.ibm_backend)
            elif cfg.sampler == "aleatorio":
                from .cliente_dwave import muestrear_aleatorio
                r = muestrear_aleatorio(modelo, cfg.num_reads, semilla)
            else:
                r = muestrear(modelo, cfg.sampler, cfg.num_reads, semilla,
                              annealing_time_us=cfg.annealing_time_us, fabrica_qpu=fabrica_qpu)
            secuencia, _ = decodificar(modelo, r.bits)
            factible = factible_estricto(modelo, r.bits) and es_permutacion(secuencia, modelo.n)
            corrida = CorridaCruda(
                id_corrida=id_corrida, formulacion=formulacion, sampler=cfg.sampler,
                parametros={**r.parametros, "replica": replica, "semilla": semilla,
                            "num_variables": modelo.num_variables,
                            "criterio_factibilidad": "estricto"},
                secuencia=secuencia, factible=factible,
                distancia_total=distancia_ruta(secuencia, instancia.distancias),
                energia=r.energia, tiempo_anneal_us=r.tiempo_anneal_us,
                chain_break_fraction=r.chain_break_fraction, bits=r.bits,
            )
            lote.corridas.append(corrida)
            if carpeta_csv is not None:
                _csv_de_replica(carpeta_csv, id_instancia, corrida)
            if ruta_pkl is not None:
                guardar_crudos(lote, ruta_pkl)  # guardado incremental: una caida solo pierde la corrida en curso
            log.info("  corrida %d (%s, replica %d): %s %s", id_corrida, formulacion, replica,
                     "factible" if factible else "INFACTIBLE", secuencia)
            id_corrida += 1
    return lote


def guardar_crudos(lote: LoteCrudo, ruta: Path) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    temporal = ruta.with_suffix(".pkl.tmp")
    with temporal.open("wb") as f:
        pickle.dump(lote, f)
    temporal.replace(ruta)  # escritura atomica: nunca queda un .pkl a medio escribir


def cargar_crudos(ruta: Path) -> LoteCrudo:
    """Abre un .pkl generado por este pipeline. Nunca debe abrirse un .pkl de origen desconocido:
    deserializarlo puede ejecutar codigo arbitrario (Practica 06, controles de seguridad)."""
    with Path(ruta).open("rb") as f:
        lote = pickle.load(f)  # noqa: S301 - solo archivos propios del pipeline
    if not isinstance(lote, LoteCrudo):
        raise TypeError(f"{ruta} no contiene un lote del pipeline")
    return lote
