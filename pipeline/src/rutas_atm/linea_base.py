"""CMP-04 Linea base clasica: solucion exacta del TSP por programacion dinamica (Held-Karp).

Complejidad O(n^2 * 2^n): practica hasta unos 15-20 cajeros, holgada para la escala validada (DA-003).
"""

import numpy as np

MAX_CAJEROS_HELD_KARP = 18


def held_karp(d: np.ndarray) -> tuple[float, list]:
    """Devuelve (distancia_optima, ruta) con la ruta abierta empezando en el cajero 0."""
    n = d.shape[0]
    if n < 2:
        raise ValueError("Se necesitan al menos 2 cajeros.")
    if n > MAX_CAJEROS_HELD_KARP:
        raise ValueError(f"Held-Karp no es practico con {n} cajeros (maximo {MAX_CAJEROS_HELD_KARP}).")

    INF = float("inf")
    tam = 1 << (n - 1)  # subconjuntos de {1..n-1}
    costo = np.full((tam, n), INF)
    padre = np.full((tam, n), -1, dtype=int)
    for k in range(1, n):
        costo[1 << (k - 1), k] = d[0, k]

    for mascara in range(1, tam):
        for k in range(1, n):
            bit_k = 1 << (k - 1)
            if not mascara & bit_k or costo[mascara, k] == INF:
                continue
            for m in range(1, n):
                bit_m = 1 << (m - 1)
                if mascara & bit_m:
                    continue
                nueva = mascara | bit_m
                c = costo[mascara, k] + d[k, m]
                if c < costo[nueva, m]:
                    costo[nueva, m] = c
                    padre[nueva, m] = k

    completo = tam - 1
    mejor, ultimo = INF, -1
    for k in range(1, n):
        c = costo[completo, k] + d[k, 0]
        if c < mejor:
            mejor, ultimo = c, k

    ruta, mascara, k = [], completo, ultimo
    while k != -1:
        ruta.append(k)
        anterior = padre[mascara, k]
        mascara ^= 1 << (k - 1)
        k = anterior
    return float(mejor), [0] + [int(k) for k in ruta[::-1]]
