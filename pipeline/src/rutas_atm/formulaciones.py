"""CMP-02 Formulacion del TSP como QUBO: tradicional (one-hot, Lucas 2014) y GPS (Gonzalez-Bermejo et al., 2022).

La construccion de ambas matrices se reutiliza de la tesis de la autora
(repositorio gps-vs-qubo-tsp, formulations.py), donde se valido contra fuerza bruta.
Aqui se agregan la conversion a modelo de dimod y la decodificacion "best effort" que
necesita el archivo de intercambio: una ruta infactible tambien se registra tal como salio.
"""

from dataclasses import dataclass

import dimod
import numpy as np


@dataclass(frozen=True)
class ModeloQUBO:
    formulacion: str  # "GPS" o "QUBO"
    bqm: dimod.BinaryQuadraticModel
    n: int
    var_index: dict | None = None  # solo GPS: (i, j, r) -> indice
    N: int | None = None  # solo GPS: n - 1

    @property
    def num_variables(self) -> int:
        return self.bqm.num_variables


def _penalizacion_por_defecto(d: np.ndarray) -> float:
    return float(np.sum(d)) * 2.0


def matriz_qubo_tradicional(d: np.ndarray, penalizacion: float | None = None) -> np.ndarray:
    """Variables x_{i,p}: cajero i en la posicion p. n^2 variables."""
    n = d.shape[0]
    A = penalizacion if penalizacion is not None else _penalizacion_por_defecto(d)
    Q = np.zeros((n * n, n * n))

    def idx(i, p):
        return i * n + p

    for i in range(n):
        for j in range(n):
            if i != j:
                for p in range(n):
                    Q[idx(i, p), idx(j, (p + 1) % n)] += d[i, j]
    for i in range(n):
        for p in range(n):
            Q[idx(i, p), idx(i, p)] += -A
            for p2 in range(n):
                if p2 != p:
                    Q[idx(i, p), idx(i, p2)] += A
    for p in range(n):
        for i in range(n):
            Q[idx(i, p), idx(i, p)] += -A
            for j in range(n):
                if j != i:
                    Q[idx(i, p), idx(j, p)] += A
    return Q


def matriz_qubo_gps(d: np.ndarray, penalizacion: float | None = None, lam: float | None = None):
    """Variables x_{i,j,r}, i,j en {0..N+1} (N = n-1), r en {0,1,2}. Devuelve (Q, var_index, N)."""
    n = d.shape[0]
    if n < 2:
        raise ValueError("Se necesitan al menos 2 cajeros.")
    N = n - 1
    num_aug = N + 2
    A = penalizacion if penalizacion is not None else _penalizacion_por_defecto(d)
    lam_val = lam if lam is not None else A

    def real(i):
        return 0 if i in (0, N + 1) else i

    pares = [(i, j) for i in range(num_aug) for j in range(num_aug) if i != j and {i, j} != {0, N + 1}]
    var_index = {(i, j, r): k for k, (i, j, r) in enumerate((i, j, r) for (i, j) in pares for r in range(3))}
    Q = np.zeros((len(var_index), len(var_index)))

    def quad(v1, v2, c):
        if v1 == v2:
            Q[v1, v1] += c
        else:
            Q[v1, v2] += c / 2
            Q[v2, v1] += c / 2

    def exactamente_uno(terminos, w):
        for v in terminos:
            Q[v, v] += -w
        for a in range(len(terminos)):
            for b in range(a + 1, len(terminos)):
                quad(terminos[a], terminos[b], 2 * w)

    for (i, j) in pares:
        Q[var_index[(i, j, 1)], var_index[(i, j, 1)]] += d[real(i), real(j)]
    for (i, j) in pares:
        exactamente_uno([var_index[(i, j, r)] for r in range(3)], A)
    for i in range(0, N + 1):
        exactamente_uno([var_index[(i, j, 1)] for j in range(num_aug) if j != i and {i, j} != {0, N + 1}], A)
    for j in range(1, N + 2):
        exactamente_uno([var_index[(i, j, 1)] for i in range(0, N + 1) if i != j and {i, j} != {0, N + 1}], A)
    for i in range(num_aug):
        for j in range(num_aug):
            if i < j and {i, j} != {0, N + 1}:
                exactamente_uno([var_index[(i, j, 2)], var_index[(j, i, 2)]], A)
    for i in range(1, N + 1):
        for j in range(1, N + 1):
            for k in range(1, N + 1):
                if len({i, j, k}) < 3:
                    continue
                v_ji, v_kj, v_ki = var_index[(j, i, 2)], var_index[(k, j, 2)], var_index[(k, i, 2)]
                quad(v_ji, v_kj, lam_val)
                quad(v_ji, v_ki, -lam_val)
                quad(v_kj, v_ki, -lam_val)
                Q[v_ki, v_ki] += lam_val
    return Q, var_index, N


def _bqm_desde_matriz(Q: np.ndarray) -> dimod.BinaryQuadraticModel:
    """Convierte x^T Q x en un BQM binario: lineal = diagonal, cuadratico = Q[i,j] + Q[j,i]."""
    n = Q.shape[0]
    lineal = {i: float(Q[i, i]) for i in range(n)}
    cuadratico = {}
    for i in range(n):
        for j in range(i + 1, n):
            c = float(Q[i, j] + Q[j, i])
            if c != 0.0:
                cuadratico[(i, j)] = c
    return dimod.BinaryQuadraticModel(lineal, cuadratico, 0.0, dimod.BINARY)


def construir_modelo(formulacion: str, d: np.ndarray) -> ModeloQUBO:
    n = d.shape[0]
    if formulacion == "QUBO":
        return ModeloQUBO("QUBO", _bqm_desde_matriz(matriz_qubo_tradicional(d)), n)
    if formulacion == "GPS":
        Q, var_index, N = matriz_qubo_gps(d)
        return ModeloQUBO("GPS", _bqm_desde_matriz(Q), n, var_index, N)
    raise ValueError(f"Formulacion desconocida: {formulacion!r} (validas: GPS, QUBO)")


def _rotar_al_deposito(secuencia: list) -> list:
    if 0 in secuencia:
        k = secuencia.index(0)
        return secuencia[k:] + secuencia[:k]
    return secuencia


def es_permutacion(secuencia: list, n: int) -> bool:
    """Una ruta es factible si visita cada cajero exactamente una vez."""
    return len(secuencia) == n and sorted(secuencia) == list(range(n))


def decodificar(modelo: ModeloQUBO, bits: dict) -> tuple[list, bool]:
    """Devuelve (secuencia, factible). La secuencia es abierta y empieza en el cajero 0 si aparece.

    Una ruta infactible se reconstruye igual (repeticiones u omisiones incluidas) para que
    el visor pueda mostrar donde falla; nunca se 'repara'.
    """
    n = modelo.n
    if modelo.formulacion == "QUBO":
        # Se listan TODOS los cajeros activos de cada posicion: si una posicion tiene dos,
        # ambos aparecen y la ruta queda como infactible, en lugar de ocultar el conflicto.
        secuencia = [i for p in range(n) for i in range(n) if bits.get(i * n + p, 0) == 1]
        secuencia = _rotar_al_deposito(secuencia) or [0]
        return secuencia, es_permutacion(secuencia, n)

    N, vi = modelo.N, modelo.var_index
    sucesor = {}
    for (i, j, r), v in vi.items():
        if r == 1 and bits.get(v, 0) == 1 and i not in sucesor:
            sucesor[i] = j
    secuencia, actual, vistos = [0], 0, {0}
    for _ in range(N + 1):
        siguiente = sucesor.get(actual)
        if siguiente is None or siguiente == N + 1:
            break
        secuencia.append(siguiente)
        if siguiente in vistos:
            break
        vistos.add(siguiente)
        actual = siguiente
    return secuencia, es_permutacion(secuencia, n)
