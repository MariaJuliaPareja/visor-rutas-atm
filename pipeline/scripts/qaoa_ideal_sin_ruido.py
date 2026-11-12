"""QAOA reps=1 sin ruido, en CPU. No llama a IBM ni escribe en salidas/ salvo runs_test/.

El statevector de 30 qubits en complex128 pesa 16 GiB. Esta maquina tiene 8 GB:
esa simulacion no se ejecuta. En una t2.2xlarge (32 GiB) el vector solo cabe;
el mezclador de energia_qaoa copia otro vector de 16 GiB y, con la diagonal,
el pico pasa de 32 GiB.
"""

import json
import pickle
import sys
from pathlib import Path

import numpy as np

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from rutas_atm.experimento import LoteCrudo  # noqa: E402
from rutas_atm.formulacion_tsp import construir_modelo, decodificar  # noqa: E402

SALIDA = RAIZ / "salidas" / "runs_test" / "qaoa_ideal_verificacion_1000.json"
LOTES = {
    3: RAIZ / "salidas" / "crudos" / "corridas_i3_n3_ibm_20261111-211121-481.pkl",
    4: RAIZ / "salidas" / "crudos" / "corridas_i4_n4_ibm_20261111-201713-615.pkl",
}
RAMPA = [0.375, 0.375]
SHOTS = 200
REPETICIONES = 1000
SEMILLA_MUESTREO = 42


def memoria_disponible() -> tuple[int, int]:
    import ctypes

    class Estado(ctypes.Structure):
        _fields_ = [
            ("dwLength", ctypes.c_ulong),
            ("dwMemoryLoad", ctypes.c_ulong),
            ("ullTotalPhys", ctypes.c_ulonglong),
            ("ullAvailPhys", ctypes.c_ulonglong),
            ("ullTotalPageFile", ctypes.c_ulonglong),
            ("ullAvailPageFile", ctypes.c_ulonglong),
            ("ullTotalVirtual", ctypes.c_ulonglong),
            ("ullAvailVirtual", ctypes.c_ulonglong),
            ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
        ]

    estado = Estado()
    estado.dwLength = ctypes.sizeof(Estado)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(estado)):
        raise OSError("GlobalMemoryStatusEx fallo")
    return int(estado.ullTotalPhys), int(estado.ullAvailPhys)


def diagonal_ising(bqm) -> tuple[np.ndarray, list, float]:
    """Autovalores de H con la escala de hamiltoniano_ising, sin construir la matriz."""
    variables = list(bqm.variables)
    puesto = {v: k for k, v in enumerate(variables)}
    h, j, _ = bqm.to_ising()
    escala = max([abs(c) for c in (*h.values(), *j.values())] or [1.0]) or 1.0
    n = len(variables)
    indice = np.arange(1 << n, dtype=np.uint32)
    diagonal = np.zeros(1 << n, dtype=np.float64)
    for v, coef in h.items():
        bit = ((indice >> puesto[v]) & 1).astype(np.float64)
        diagonal += (-coef / escala) * (1.0 - 2.0 * bit)
    for (u, v), coef in j.items():
        zu = 1.0 - 2.0 * ((indice >> puesto[u]) & 1).astype(np.float64)
        zv = 1.0 - 2.0 * ((indice >> puesto[v]) & 1).astype(np.float64)
        diagonal += (coef / escala) * zu * zv
    return diagonal, variables, float(escala)


def estado_qaoa(diagonal: np.ndarray, angulos: list[float], reps: int = 1) -> np.ndarray:
    """Misma evolucion que energia_qaoa. Coincide con QAOAAnsatz en los 9 qubits de prueba."""
    n = int(np.log2(len(diagonal)))
    betas, gammas = angulos[:reps], angulos[reps:]
    psi = np.full(1 << n, 2 ** (-n / 2), dtype=np.complex128)
    for beta, gamma in zip(betas, gammas, strict=True):
        psi *= np.exp(-1j * gamma * diagonal)
        c, s = np.cos(beta), -1j * np.sin(beta)
        t = psi.reshape([2] * n)
        for q in range(n):
            a, b = np.take(t, 0, axis=q), np.take(t, 1, axis=q)
            t = np.stack([c * a + s * b, s * a + c * b], axis=q)
        psi = t.reshape(-1)
    return psi


def bits_de_indice(indice: int, variables: list) -> dict:
    return {v: (indice >> k) & 1 for k, v in enumerate(variables)}


def distancia(secuencia: list, matriz: np.ndarray) -> float:
    if len(secuencia) < 2:
        return 0.0
    return float(sum(matriz[secuencia[k], secuencia[(k + 1) % len(secuencia)]] for k in range(len(secuencia))))


def clasificar(modelo, variables, matriz, dist_optima):
    n = len(variables)
    factible = np.zeros(1 << n, dtype=bool)
    optima = np.zeros(1 << n, dtype=bool)
    energia = np.empty(1 << n, dtype=np.float64)
    for i in range(1 << n):
        bits = bits_de_indice(i, variables)
        energia[i] = modelo.bqm.energy(bits)
        secuencia, es_factible = decodificar(modelo, bits)
        factible[i] = es_factible
        optima[i] = es_factible and abs(distancia(secuencia, matriz) - dist_optima) <= 1e-6
    return factible, optima, energia


def muestrear(prob, energia, optima) -> dict:
    """Dos sucesos distintos.

    P_decodifica = suma de |psi|^2 sobre cadenas cuya secuencia decodificada es la ruta optima.
    P(alguna de 200 decodifica optima) = 1 - (1 - P_decodifica)^200.

    La cadena de menor energia es argmin de E_BQM entre las 200 muestras. Solo coincide con
    el suceso anterior si toda cadena que decodifica la ruta optima tiene la energia fundamental.
    El decodificador tambien acepta asignaciones one-hot rotas que deletrean esa ruta.
    """
    rng = np.random.default_rng(SEMILLA_MUESTREO)
    pesos = np.clip(prob, 0, None)
    pesos /= pesos.sum()
    argmin_optima = 0
    alguna_optima = 0
    for _ in range(REPETICIONES):
        tiros = rng.choice(len(pesos), size=SHOTS, p=pesos)
        if optima[tiros].any():
            alguna_optima += 1
        presentes = np.unique(tiros)
        mejor = int(presentes[np.argmin(energia[presentes])])
        if optima[mejor]:
            argmin_optima += 1
    return {
        "shots": SHOTS,
        "repeticiones": REPETICIONES,
        "semilla_generador": SEMILLA_MUESTREO,
        "argmin_bqm_decodifica_optima": argmin_optima,
        "fraccion_argmin": argmin_optima / REPETICIONES,
        "alguna_de_200_decodifica_optima": alguna_optima,
        "fraccion_alguna": alguna_optima / REPETICIONES,
    }


def simular(modelo, matriz, dist_optima, angulos, etiqueta: str) -> dict:
    diagonal, variables, escala = diagonal_ising(modelo.bqm)
    psi = estado_qaoa(diagonal, angulos, reps=1)
    prob = np.abs(psi) ** 2
    factible, optima, energia = clasificar(modelo, variables, matriz, dist_optima)
    p_fac = float(prob[factible].sum())
    p_opt = float(prob[optima].sum())
    e_star = float(energia[optima].min())
    fundamental = optima & (np.abs(energia - e_star) <= 1e-6)
    p_fund = float(prob[fundamental].sum())
    return {
        "etiqueta": etiqueta,
        "angulos": angulos,
        "qubits": len(variables),
        "escala_hamiltoniano": escala,
        "norma": float(prob.sum()),
        "probabilidad_factible": p_fac,
        "probabilidad_decodifica_optima": p_opt,
        "probabilidad_energia_fundamental": p_fund,
        "energia_fundamental_bqm": e_star,
        "cadenas_que_decodifican_optima": int(optima.sum()),
        "cadenas_en_energia_fundamental": int(fundamental.sum()),
        "formula_alguna": 1 - (1 - p_opt) ** SHOTS,
        "formula_fundamental": 1 - (1 - p_fund) ** SHOTS,
        "muestreo": muestrear(prob, energia, optima),
    }


def hardware(lote, formulacion: str, matriz, dist_optima) -> list[dict]:
    filas = []
    for corrida in lote.corridas:
        if corrida.formulacion != formulacion:
            continue
        dist = distancia(corrida.secuencia, matriz)
        filas.append({
            "replica": corrida.parametros.get("replica"),
            "semilla": corrida.parametros.get("semilla"),
            "angulos": corrida.parametros.get("angulos"),
            "optimizador": corrida.parametros.get("optimizador"),
            "escala_hamiltoniano": corrida.parametros.get("escala_hamiltoniano"),
            "energia_bqm": corrida.energia,
            "factible": corrida.factible,
            "optima": bool(corrida.factible and abs(dist - dist_optima) <= 1e-3),
            "secuencia": corrida.secuencia,
            "distancia_km": dist,
            "shots": corrida.parametros.get("shots"),
            "backend": corrida.parametros.get("backend"),
        })
    return filas


def resumen_hardware(filas: list[dict]) -> dict:
    n = len(filas)
    return {
        "N": n,
        "factibles": sum(1 for f in filas if f["factible"]),
        "optimas": sum(1 for f in filas if f["optima"]),
        "energia_min": min(f["energia_bqm"] for f in filas),
        "energia_max": max(f["energia_bqm"] for f in filas),
    }


def cabe_statevector(n: int) -> dict:
    total, libre = memoria_disponible()
    vector = (1 << n) * 16
    diagonal = (1 << n) * 8
    copia_mezclador = vector
    return {
        "qubits": n,
        "bytes_statevector_complex128": vector,
        "bytes_diagonal_float64": diagonal,
        "bytes_pico_con_copia_del_mezclador": vector + copia_mezclador + diagonal,
        "bytes_ram_total": total,
        "bytes_ram_libre": libre,
        "cabe": vector + diagonal < libre,
    }


def main() -> None:
    if SALIDA.exists():
        raise FileExistsError(f"{SALIDA} ya existe")
    lotes = {}
    for n, ruta in LOTES.items():
        with ruta.open("rb") as archivo:
            lote = pickle.load(archivo)
        if not isinstance(lote, LoteCrudo):
            raise TypeError(ruta.name)
        lotes[n] = lote

    memoria_gps = cabe_statevector(30)
    resultados = []
    if memoria_gps["cabe"]:
        lote = lotes[3]
        modelo = construir_modelo("GPS", np.array(lote.instancia.distancias, dtype=float))
        resultados.append(simular(
            modelo, np.array(lote.instancia.distancias, dtype=float), float(lote.dist_optima),
            RAMPA, "GPS n=3 rampa",
        ))
    else:
        resultados.append({
            "etiqueta": "GPS n=3 rampa",
            "angulos": RAMPA,
            "estado": "no_cabe",
            "memoria": memoria_gps,
        })

    for n, formulacion in ((3, "QUBO"), (4, "QUBO")):
        lote = lotes[n]
        matriz = np.array(lote.instancia.distancias, dtype=float)
        modelo = construir_modelo(formulacion, matriz)
        hw = hardware(lote, formulacion, matriz, float(lote.dist_optima))
        vistos = []
        for fila in hw:
            angulos = [float(a) for a in fila["angulos"]]
            if any(np.allclose(angulos, previo, atol=0, rtol=0) for previo in vistos):
                continue
            vistos.append(angulos)
            sim = simular(modelo, matriz, float(lote.dist_optima), angulos, f"QUBO n={n} COBYLA {angulos}")
            sim["hardware_replicas_con_estos_angulos"] = [
                f["replica"] for f in hw if np.allclose(f["angulos"], angulos, atol=0, rtol=0)
            ]
            resultados.append(sim)
        resultados.append(simular(modelo, matriz, float(lote.dist_optima), RAMPA, f"QUBO n={n} rampa"))

    informe = {
        "circuito": "QAOA reps=1 sin ruido, evolucion de energia_qaoa / QAOAAnsatz",
        "shots": SHOTS,
        "repeticiones": REPETICIONES,
        "semilla_muestreo": SEMILLA_MUESTREO,
        "memoria_gps_30": memoria_gps,
        "memoria_gps_30_ec2_32gib": {
            "complex64_bytes": (1 << 30) * 8,
            "diagonal_float32_bytes": (1 << 30) * 4,
            "temporal_mitad_complex64_bytes": (1 << 29) * 8,
            "pico_bytes": (1 << 30) * 8 + (1 << 30) * 4 + (1 << 29) * 8,
            "cabe_bajo_28gib": True,
            "ejecutado": False,
        },
        "hardware": {
            "n3_archivo": LOTES[3].name,
            "n4_archivo": LOTES[4].name,
            "GPS_n3": resumen_hardware(hardware(
                lotes[3], "GPS", np.array(lotes[3].instancia.distancias, float), float(lotes[3].dist_optima))),
            "QUBO_n3": resumen_hardware(hardware(
                lotes[3], "QUBO", np.array(lotes[3].instancia.distancias, float), float(lotes[3].dist_optima))),
            "QUBO_n4": resumen_hardware(hardware(
                lotes[4], "QUBO", np.array(lotes[4].instancia.distancias, float), float(lotes[4].dist_optima))),
        },
        "simulaciones": resultados,
    }
    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    SALIDA.write_text(json.dumps(informe, ensure_ascii=False, indent=2), encoding="utf-8")
    print(SALIDA)
    for sim in resultados:
        if sim.get("estado") == "no_cabe":
            print("GPS n=3 no cabe", memoria_gps["bytes_ram_libre"], "<", memoria_gps["bytes_statevector_complex128"])
            continue
        m = sim["muestreo"]
        print(f"{sim['etiqueta']}: P(factible)={sim['probabilidad_factible']:.6f} "
              f"P(decodifica)={sim['probabilidad_decodifica_optima']:.6f} "
              f"P(fundamental)={sim['probabilidad_energia_fundamental']:.6f} "
              f"alguna {m['alguna_de_200_decodifica_optima']}/{m['repeticiones']} "
              f"argmin {m['argmin_bqm_decodifica_optima']}/{m['repeticiones']}")


if __name__ == "__main__":
    main()
