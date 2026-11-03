"""CMP-03 Cliente de recocido: ejecuta un modelo QUBO con el sampler configurado.

- "simulado": SimulatedAnnealingSampler de dwave-samplers; corre en local, sin token ni costo.
- "qpu": DWaveSampler + EmbeddingComposite del Ocean SDK; usa el token de D-Wave Leap
  configurado fuera del codigo y consume minutos del plan gratuito (RNF04).
"""

import logging
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


def _sampler_qpu():
    try:
        from dwave.system import DWaveSampler, EmbeddingComposite
    except ImportError as exc:
        raise ErrorDeMuestreo(
            "RUTAS_SAMPLER=qpu requiere dwave-system: pip install -r requirements-qpu.txt") from exc
    try:
        return EmbeddingComposite(DWaveSampler())
    except Exception as exc:  # el SDK lanza varios tipos segun la causa
        raise ErrorDeMuestreo(
            "No se pudo conectar con D-Wave Leap. Revisa DWAVE_API_TOKEN o 'dwave config create'. "
            f"Causa: {type(exc).__name__}") from exc


def muestrear(modelo: ModeloQUBO, sampler: str, num_reads: int, semilla: int) -> ResultadoMuestreo:
    """Devuelve la muestra de menor energia."""
    if sampler == "simulado":
        from dwave.samplers import SimulatedAnnealingSampler
        parametros = {"num_reads": num_reads, "seed": semilla}
        respuesta = SimulatedAnnealingSampler().sample(modelo.bqm, **parametros)
    elif sampler == "qpu":
        parametros = {"num_reads": num_reads, "annealing_time": 20, "return_embedding": True}
        try:
            respuesta = _sampler_qpu().sample(modelo.bqm, label=f"rutas-atm-{modelo.formulacion}", **parametros)
            respuesta.resolve()
        except ErrorDeMuestreo:
            raise
        except Exception as exc:
            raise ErrorDeMuestreo(f"El QPU rechazo o no completo la ejecucion: {type(exc).__name__}") from exc
    else:
        raise ValueError(f"Sampler desconocido: {sampler!r}")

    mejor = respuesta.first
    tiempo = None
    cbf = None
    if sampler == "qpu":
        tiempo = respuesta.info.get("timing", {}).get("qpu_anneal_time_per_sample")
        if "chain_break_fraction" in respuesta.record.dtype.names:
            mejor_fila = next(respuesta.data(["energy", "chain_break_fraction"], sorted_by="energy"))
            cbf = float(mejor_fila.chain_break_fraction)
    log.info("%s: %d variables, energia minima %.3f", modelo.formulacion, modelo.num_variables, mejor.energy)
    return ResultadoMuestreo(dict(mejor.sample), float(mejor.energy), tiempo, cbf, parametros)

