"""CMP-03 Cliente IBM Quantum: resuelve el mismo modelo QUBO con QAOA en hardware de compuerta de IBM.

Alternativa a D-Wave Leap, que no da servicio desde Peru (INC-08, DEC-08). El flujo:

1. El BQM de la formulacion (GPS o QUBO) se convierte a un Hamiltoniano de Ising: un qubit por variable.
2. Se arma el circuito QAOA con `reps` capas.
3. Los angulos (gamma, beta) se eligen en local, sin gastar tiempo del QPU: con pocas variables se
   optimizan sobre el vector de estado; con muchas se usa una rampa lineal fija (aproximacion adiabatica).
4. El circuito se transpila al backend y se envia UNA sola vez con SamplerV2 (un solo job por corrida).
5. De todas las cadenas medidas se devuelve la de menor energia del BQM, igual que `respuesta.first` en D-Wave.

La cuenta se configura fuera del codigo con `QiskitRuntimeService.save_account(...)` o con las variables
QISKIT_IBM_TOKEN y QISKIT_IBM_INSTANCE. El plan Open de IBM da 10 minutos de QPU al mes (RNF04).
"""

import logging
import os
from collections.abc import Callable

import numpy as np

from .cliente_dwave import ErrorDeMuestreo, ResultadoMuestreo
from .formulacion_tsp import ModeloQUBO

log = logging.getLogger(__name__)

MAX_QUBITS_OPTIMIZACION_LOCAL = 18  # 2^18 amplitudes: optimizar en local tarda segundos
PASO_RAMPA = 0.75


def _importar_qiskit():
    try:
        from qiskit.circuit.library import QAOAAnsatz
        from qiskit.quantum_info import SparsePauliOp
        from qiskit.transpiler import generate_preset_pass_manager
        from qiskit_ibm_runtime import QiskitRuntimeService, SamplerV2
    except ImportError as exc:
        raise ErrorDeMuestreo(
            "La ejecucion en IBM Quantum requiere Qiskit: pip install -r requirements-ibm.txt") from exc
    return QAOAAnsatz, SparsePauliOp, generate_preset_pass_manager, QiskitRuntimeService, SamplerV2


def hamiltoniano_ising(modelo: ModeloQUBO):
    """BQM binario -> (SparsePauliOp, variables en orden de qubit, escala).

    dimod usa espines s = 2x - 1; en Qiskit el bit 1 es el autovalor -1 de Z, asi que s = -Z.
    Los coeficientes se normalizan a |coef| <= 1 para que los angulos sean comparables entre instancias.
    """
    _, SparsePauliOp, *_ = _importar_qiskit()
    variables = list(modelo.bqm.variables)
    indice = {v: k for k, v in enumerate(variables)}
    h, J, _ = modelo.bqm.to_ising()
    escala = max([abs(c) for c in (*h.values(), *J.values())] or [1.0]) or 1.0
    terminos = [("Z", [indice[v]], -c / escala) for v, c in h.items() if c]
    terminos += [("ZZ", [indice[u], indice[v]], c / escala) for (u, v), c in J.items() if c]
    if not terminos:
        terminos = [("I", [0], 0.0)]
    return SparsePauliOp.from_sparse_list(terminos, num_qubits=len(variables)), variables, escala


def _rampa(reps: int) -> list[float]:
    """Angulos de una rampa lineal: gamma crece y beta decrece en cada capa."""
    fr = [(k + 0.5) / reps for k in range(reps)]
    betas = [(1 - f) * PASO_RAMPA for f in fr]
    gammas = [f * PASO_RAMPA for f in fr]
    return betas + gammas  # orden de parametros de QAOAAnsatz: beta, gamma


def energia_qaoa(diagonal: np.ndarray, angulos, reps: int) -> float:
    """Valor esperado de H tras el circuito QAOA, simulado en NumPy (exacto: H es diagonal).

    Misma convencion que QAOAAnsatz: angulos = [beta_1..beta_p, gamma_1..gamma_p], costo exp(-i gamma H)
    y mezclador exp(-i beta X) en cada qubit. Mucho mas rapido que sintetizar el circuito en cada paso.
    """
    n = int(np.log2(len(diagonal)))
    betas, gammas = angulos[:reps], angulos[reps:]
    psi = np.full(2 ** n, 2 ** (-n / 2), dtype=complex)  # |+>^n
    for beta, gamma in zip(betas, gammas, strict=True):
        psi = psi * np.exp(-1j * gamma * diagonal)
        c, s = np.cos(beta), -1j * np.sin(beta)
        t = psi.reshape([2] * n)
        for q in range(n):
            a, b = np.take(t, 0, axis=q), np.take(t, 1, axis=q)
            t = np.stack([c * a + s * b, s * a + c * b], axis=q)
        psi = t.reshape(-1)
    return float(np.real(np.vdot(psi, diagonal * psi)))


def elegir_angulos(ansatz, hamiltoniano, reps: int, semilla: int) -> tuple[list[float], str]:
    """Angulos de QAOA sin usar el QPU. Devuelve (valores, metodo)."""
    if ansatz.num_qubits > MAX_QUBITS_OPTIMIZACION_LOCAL:
        return _rampa(reps), "rampa_lineal"
    from scipy.optimize import minimize

    diagonal = np.real(hamiltoniano.to_matrix(sparse=True).diagonal())  # H solo tiene Z y ZZ
    rng = np.random.default_rng(semilla)
    inicios = [np.array(_rampa(reps))] + [rng.uniform(0, np.pi / 2, 2 * reps) for _ in range(3)]
    mejor = min((minimize(lambda x: energia_qaoa(diagonal, x, reps), x0, method="COBYLA",
                          options={"maxiter": 120}) for x0 in inicios), key=lambda r: r.fun)
    return [float(v) for v in mejor.x], "optimizado_local"


def _conectar_servicio():
    *_, QiskitRuntimeService, _ = _importar_qiskit()
    token, instancia = os.getenv("QISKIT_IBM_TOKEN"), os.getenv("QISKIT_IBM_INSTANCE")
    try:
        if token:
            return QiskitRuntimeService(channel="ibm_quantum_platform", token=token, instance=instancia or None)
        return QiskitRuntimeService()  # cuenta guardada con save_account
    except Exception as exc:
        raise ErrorDeMuestreo(
            "No se pudo conectar con IBM Quantum. Guarda tu cuenta con QiskitRuntimeService.save_account(...) "
            f"o define QISKIT_IBM_TOKEN. Causa: {type(exc).__name__}: {exc}") from exc


_backend_en_cache = None


def _backend(qubits: int, fabrica: Callable | None):
    """Un solo backend por ejecucion del pipeline. RUTAS_IBM_BACKEND fija uno; si no, el menos ocupado."""
    global _backend_en_cache
    if fabrica is not None:
        return fabrica()
    if _backend_en_cache is not None and _backend_en_cache.num_qubits >= qubits:
        return _backend_en_cache
    servicio = _conectar_servicio()
    nombre = os.getenv("RUTAS_IBM_BACKEND", "").strip()
    try:
        backend = (servicio.backend(nombre) if nombre
                   else servicio.least_busy(operational=True, simulator=False, min_num_qubits=qubits))
    except Exception as exc:
        raise ErrorDeMuestreo(f"No hay un backend de IBM Quantum disponible con {qubits} qubits: {exc}") from exc
    _backend_en_cache = backend
    return backend


def probar_conexion_ibm() -> dict:
    """Verifica la cuenta y lista los backends reales disponibles, sin enviar ningun circuito."""
    servicio = _conectar_servicio()
    backends = servicio.backends(operational=True, simulator=False)
    if not backends:
        raise ErrorDeMuestreo("La cuenta de IBM Quantum no tiene backends reales disponibles")
    return {
        "backends": sorted(f"{b.name} ({b.num_qubits} qubits)" for b in backends),
        "menos_ocupado": servicio.least_busy(operational=True, simulator=False).name,
    }


def _qubits_usados(circuito) -> int:
    usados = set()
    for instr in circuito.data:
        if instr.operation.name != "barrier":
            usados.update(circuito.find_bit(q).index for q in instr.qubits)
    return len(usados)


def muestrear_ibm(modelo: ModeloQUBO, shots: int, semilla: int, reps: int = 1,
                  fabrica_backend: Callable | None = None) -> ResultadoMuestreo:
    """Ejecuta QAOA en IBM Quantum y devuelve la cadena medida de menor energia.
    `fabrica_backend` permite inyectar un backend simulado (fake_provider) en las pruebas."""
    QAOAAnsatz, _, generate_preset_pass_manager, _, SamplerV2 = _importar_qiskit()
    hamiltoniano, variables, escala = hamiltoniano_ising(modelo)
    ansatz = QAOAAnsatz(hamiltoniano, reps=reps)
    angulos, metodo = elegir_angulos(ansatz, hamiltoniano, reps, semilla)
    circuito = ansatz.assign_parameters(angulos)
    circuito.measure_all()

    backend = _backend(len(variables), fabrica_backend)
    transpilado = generate_preset_pass_manager(optimization_level=3, backend=backend,
                                               seed_transpiler=semilla).run(circuito)
    ops = transpilado.count_ops()
    puertas_2q = sum(ops.get(g, 0) for g in ("ecr", "cz", "cx", "rzz"))
    log.info("%s en %s: %d qubits logicos, %d fisicos, profundidad %d, %d puertas de 2 qubits", modelo.formulacion,
             backend.name, len(variables), _qubits_usados(transpilado), transpilado.depth(), puertas_2q)
    try:
        job = SamplerV2(mode=backend).run([transpilado], shots=shots)
        resultado = job.result()
    except Exception as exc:
        raise ErrorDeMuestreo(f"IBM Quantum rechazo o no completo la ejecucion: {type(exc).__name__}: {exc}") from exc

    conteos = resultado[0].data.meas.get_counts()
    mejor_bits, mejor_energia = None, float("inf")
    for cadena in conteos:
        bits = {v: int(cadena[-1 - k]) for k, v in enumerate(variables)}  # Qiskit: el qubit 0 es el ultimo
        e = modelo.bqm.energy(bits)
        if e < mejor_energia:
            mejor_bits, mejor_energia = bits, e

    uso = None
    try:
        uso = job.usage()  # segundos de QPU facturados (solo en hardware real)
    except Exception:  # noqa: BLE001 - los backends simulados no informan uso
        pass
    parametros = {
        "backend": backend.name,
        "job_id": job.job_id(),
        "shots": shots,
        "reps": reps,
        "angulos": [round(a, 4) for a in angulos],
        "metodo_angulos": metodo,
        "qubits_logicos": len(variables),
        "qubits_fisicos": _qubits_usados(transpilado),
        "profundidad": transpilado.depth(),
        "puertas_2q": puertas_2q,
        "cadenas_distintas": len(conteos),
        "escala_hamiltoniano": round(float(escala), 4),
        "qpu_segundos": uso,
    }
    log.info("%s: %d cadenas distintas, energia minima %.3f", modelo.formulacion, len(conteos), mejor_energia)
    return ResultadoMuestreo(mejor_bits, float(mejor_energia), None, None, parametros)
