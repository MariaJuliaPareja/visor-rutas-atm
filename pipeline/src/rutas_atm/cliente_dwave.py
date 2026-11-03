"""CMP-03 Cliente D-Wave: ejecuta un modelo QUBO por recocido.

- "qpu": DWaveSampler + EmbeddingComposite del Ocean SDK sobre D-Wave Leap (DA-002). El token se
  configura fuera del codigo (dwave config create o DWAVE_API_TOKEN) y cada ejecucion consume tiempo
  de QPU del plan de Leap (RNF04).
- "simulado": SimulatedAnnealingSampler de dwave-samplers; recibe el mismo modelo, corre en local y no
  consume tiempo de QPU. Se usa en desarrollo y en la integracion continua (DEC-01).
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass

from .formulacion_tsp import ModeloQUBO

log = logging.getLogger(__name__)


class ErrorDeMuestreo(RuntimeError):
    """Fallo controlado al obtener muestras (credenciales, red o proveedor)."""


@dataclass(frozen=True)
class ResultadoMuestreo:
    bits: dict
    energia: float
    tiempo_anneal_us: float | None
    chain_break_fraction: float | None
    parametros: dict


def _importar_ocean():
    try:
        from dwave.system import DWaveSampler, EmbeddingComposite
    except ImportError as exc:
        raise ErrorDeMuestreo(
            "La ejecucion en D-Wave Leap requiere dwave-system: pip install -r requirements-qpu.txt") from exc
    return DWaveSampler, EmbeddingComposite


def _conectar():
    """Crea el sampler del QPU. Solo consulta el solver disponible: no consume tiempo de QPU."""
    DWaveSampler, EmbeddingComposite = _importar_ocean()
    try:
        return EmbeddingComposite(DWaveSampler())
    except Exception as exc:  # el SDK lanza distintos tipos segun la causa (token, red, solver)
        raise ErrorDeMuestreo(
            "No se pudo conectar con D-Wave Leap. Revisa el token ('dwave config create' o DWAVE_API_TOKEN) "
            f"y la conexion a internet. Causa: {type(exc).__name__}: {exc}") from exc


_qpu_en_cache = None


def _sampler_qpu(fabrica: Callable | None):
    """Una sola conexion por ejecucion del pipeline; todas las corridas la reutilizan."""
    global _qpu_en_cache
    if fabrica is not None:
        return fabrica()
    if _qpu_en_cache is None:
        _qpu_en_cache = _conectar()
    return _qpu_en_cache


def probar_conexion() -> dict:
    """Verifica el token y el solver asignado en Leap sin enviar ningun problema al QPU."""
    sampler = _conectar().child
    props = sampler.properties
    return {
        "solver": sampler.solver.name,
        "topologia": props.get("topology", {}).get("type"),
        "qubits_activos": len(sampler.nodelist),
        "annealing_time_rango_us": props.get("annealing_time_range"),
    }


def _metadatos_qpu(respuesta, sampler) -> dict:
    info = respuesta.info
    contexto = info.get("embedding_context", {})
    embedding = contexto.get("embedding", {})
    cadenas = [len(c) for c in embedding.values()]
    timing = info.get("timing", {})
    hijo = getattr(sampler, "child", None)
    solver = getattr(getattr(hijo, "solver", None), "name", None) or getattr(hijo, "properties", {}).get("chip_id")
    return {
        "solver": solver,
        "problem_id": info.get("problem_id"),
        "qubits_fisicos": sum(cadenas) or None,
        "cadena_max": max(cadenas) if cadenas else None,
        "chain_strength": contexto.get("chain_strength"),
        "qpu_access_time_us": timing.get("qpu_access_time"),
    }


def muestrear(modelo: ModeloQUBO, sampler: str, num_reads: int, semilla: int,
              annealing_time_us: float = 20.0, fabrica_qpu: Callable | None = None) -> ResultadoMuestreo:
    """Devuelve la muestra de menor energia. `fabrica_qpu` permite inyectar un sampler en las pruebas."""
    if sampler == "simulado":
        from dwave.samplers import SimulatedAnnealingSampler
        parametros = {"num_reads": num_reads, "seed": semilla}
        respuesta = SimulatedAnnealingSampler().sample(modelo.bqm, **parametros)
    elif sampler == "qpu":
        parametros = {"num_reads": num_reads, "annealing_time": annealing_time_us}
        qpu = _sampler_qpu(fabrica_qpu)
        try:
            respuesta = qpu.sample(modelo.bqm, label=f"rutas-atm-{modelo.formulacion}", return_embedding=True,
                                   embedding_parameters={"random_seed": semilla}, **parametros)
            respuesta.resolve()
        except Exception as exc:
            raise ErrorDeMuestreo(f"El QPU rechazo o no completo la ejecucion: {type(exc).__name__}: {exc}") from exc
        parametros = {**parametros, **_metadatos_qpu(respuesta, qpu)}
    else:
        raise ValueError(f"Sampler desconocido: {sampler!r}")

    mejor = respuesta.first
    tiempo = cbf = None
    if sampler == "qpu":
        tiempo = respuesta.info.get("timing", {}).get("qpu_anneal_time_per_sample")
        if "chain_break_fraction" in respuesta.record.dtype.names:
            mejor_fila = next(respuesta.data(["energy", "chain_break_fraction"], sorted_by="energy"))
            cbf = float(mejor_fila.chain_break_fraction)
        log.info("%s en %s: %s qubits fisicos, %.1f us de acceso al QPU", modelo.formulacion,
                 parametros["solver"], parametros["qubits_fisicos"], parametros["qpu_access_time_us"] or 0)
    log.info("%s: %d variables, energia minima %.3f", modelo.formulacion, modelo.num_variables, mejor.energy)
    return ResultadoMuestreo(dict(mejor.sample), float(mejor.energy), tiempo, cbf, parametros)
