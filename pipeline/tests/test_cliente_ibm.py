"""Ruta de IBM Quantum probada sin gastar tiempo de QPU: backends simulados de Qiskit (fake_provider y Aer)."""

import numpy as np
import pytest

pytest.importorskip("qiskit")
pytest.importorskip("qiskit_aer")

from qiskit.circuit.library import QAOAAnsatz  # noqa: E402
from qiskit.quantum_info import Statevector  # noqa: E402
from qiskit_aer import AerSimulator  # noqa: E402
from qiskit_ibm_runtime.fake_provider import FakeGuadalupeV2  # noqa: E402

from rutas_atm.cliente_ibm import energia_qaoa, hamiltoniano_ising, muestrear_ibm  # noqa: E402
from rutas_atm.config import Configuracion  # noqa: E402
from rutas_atm.conversor_resultados import convertir  # noqa: E402
from rutas_atm.experimento import ejecutar_experimento  # noqa: E402
from rutas_atm.formulacion_tsp import construir_modelo, decodificar  # noqa: E402
from rutas_atm.preparacion_datos import generar_instancia  # noqa: E402
from rutas_atm.validacion import validar  # noqa: E402


@pytest.fixture(scope="module")
def modelo_qubo():
    return construir_modelo("QUBO", generar_instancia(3).distancias)


def test_hamiltoniano_reproduce_la_energia_del_bqm(modelo_qubo):
    H, variables, escala = hamiltoniano_ising(modelo_qubo)
    diagonal = np.real(H.to_matrix(sparse=True).diagonal())
    _, _, offset = modelo_qubo.bqm.to_ising()
    rng = np.random.default_rng(0)
    for k in rng.integers(0, 2 ** len(variables), 20):
        bits = {v: (int(k) >> i) & 1 for i, v in enumerate(variables)}  # qubit i = bit i del indice
        assert diagonal[k] * escala + offset == pytest.approx(modelo_qubo.bqm.energy(bits))


def test_simulacion_numpy_coincide_con_qiskit(modelo_qubo):
    H, _, _ = hamiltoniano_ising(modelo_qubo)
    ansatz = QAOAAnsatz(H, reps=2)
    angulos = [0.3, 0.2, 0.5, 0.7]
    esperado = float(np.real(Statevector(ansatz.assign_parameters(angulos)).expectation_value(H)))
    diagonal = np.real(H.to_matrix(sparse=True).diagonal())
    assert energia_qaoa(diagonal, angulos, 2) == pytest.approx(esperado)


def test_qaoa_en_backend_simulado_de_ibm(modelo_qubo):
    r = muestrear_ibm(modelo_qubo, shots=1000, semilla=42, fabrica_backend=FakeGuadalupeV2)
    secuencia, factible = decodificar(modelo_qubo, r.bits)
    assert factible and sorted(secuencia) == [0, 1, 2]
    p = r.parametros
    assert p["backend"] == "fake_guadalupe" and p["qubits_logicos"] == 9 and p["puertas_2q"] > 0
    assert r.tiempo_anneal_us is None and r.chain_break_fraction is None


def test_lote_ibm_produce_un_archivo_valido():
    cfg = Configuracion.desde_entorno().con_sampler("ibm")
    lote = ejecutar_experimento(3, 1, cfg, fabrica_qpu=lambda: AerSimulator(method="matrix_product_state"))
    doc = convertir(lote)
    errores, _ = validar(doc)
    assert errores == []
    assert {c["sampler"] for c in doc["corridas"]} == {"ibm"}
    assert {c["parametros"]["metodo_angulos"] for c in doc["corridas"]} == {"optimizado_local", "rampa_lineal"}
