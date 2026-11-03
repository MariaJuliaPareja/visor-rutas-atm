"""Ruta de ejecucion en D-Wave Leap, probada con MockDWaveSampler del Ocean SDK.

El mock reproduce la interfaz del QPU (topologia, embedding, cadenas, timing) sin conectarse a Leap,
asi las pruebas y la integracion continua no gastan tiempo de QPU ni necesitan el token.
"""

import warnings

import pytest

pytest.importorskip("dwave.system")
from dwave.system import EmbeddingComposite  # noqa: E402
from dwave.system.testing import MockDWaveSampler  # noqa: E402

from rutas_atm.cliente_dwave import ErrorDeMuestreo, muestrear  # noqa: E402
from rutas_atm.config import Configuracion  # noqa: E402
from rutas_atm.conversor_resultados import convertir  # noqa: E402
from rutas_atm.experimento import ejecutar_experimento  # noqa: E402
from rutas_atm.formulacion_tsp import construir_modelo  # noqa: E402
from rutas_atm.preparacion_datos import generar_instancia  # noqa: E402
from rutas_atm.validacion import validar  # noqa: E402

warnings.filterwarnings("ignore", message=".*not mocked in MockDWaveSampler.*")


def qpu_simulado():
    return EmbeddingComposite(MockDWaveSampler())


def test_muestreo_en_qpu_registra_metricas_y_metadatos():
    modelo = construir_modelo("QUBO", generar_instancia(3).distancias)
    r = muestrear(modelo, "qpu", num_reads=20, semilla=1, fabrica_qpu=qpu_simulado)
    assert r.tiempo_anneal_us is not None and r.tiempo_anneal_us > 0
    assert 0 <= r.chain_break_fraction <= 1
    assert r.parametros["qubits_fisicos"] >= modelo.num_variables  # cada variable usa al menos un qubit
    assert r.parametros["qpu_access_time_us"] > 0
    assert r.parametros["annealing_time"] == 20.0


def test_lote_en_qpu_produce_un_archivo_valido():
    cfg = Configuracion("qpu", num_reads=20, semilla=3, directorio_salida=None, nivel_log="WARNING")
    lote = ejecutar_experimento(3, 1, cfg, fabrica_qpu=qpu_simulado)
    doc = convertir(lote)
    errores, _ = validar(doc)
    assert errores == []
    assert all(c["sampler"] == "qpu" and c["metricas"]["tiempo_anneal"] > 0 for c in doc["corridas"])


def test_falla_del_qpu_se_reporta_de_forma_controlada():
    class QpuQueFalla:
        def sample(self, *a, **k):
            raise ConnectionError("sin red")

    modelo = construir_modelo("QUBO", generar_instancia(3).distancias)
    with pytest.raises(ErrorDeMuestreo, match="sin red"):
        muestrear(modelo, "qpu", num_reads=5, semilla=0, fabrica_qpu=QpuQueFalla)
