"""Diagnostico clasico del GPS en n=3. No usa hardware ni escribe en salidas/.

Enumeracion del hamiltoniano en bloques de numpy. En una EC2 t2.2xlarge (32 GiB)
un bloque de 2^22 estados en float64 ocupa cerca de 1 GiB de bits y otro de
producto, con pico de unos 2.5 GiB. No hace falta guardar las 2^30 energias
(8 GiB en float64). Este equipo tiene 8 GB, asi que el bloque es 2^18.
"""

import json
import pickle
import sys
import time
from pathlib import Path

import numpy as np

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from rutas_atm.experimento import LoteCrudo  # noqa: E402
from rutas_atm.formulacion_tsp import construir_modelo, decodificar, es_permutacion  # noqa: E402

LOTE = RAIZ / "salidas" / "corridas_i3_n3_ibm_20261111-211121-481"
BLOQUE = 1 << 18
TOL = 1e-6


def matriz_q(bqm) -> tuple[np.ndarray, list]:
    variables = sorted(bqm.variables)
    puesto = {v: k for k, v in enumerate(variables)}
    q = np.zeros((len(variables), len(variables)))
    for v, coef in bqm.linear.items():
        q[puesto[v], puesto[v]] += coef
    for (u, v), coef in bqm.quadratic.items():
        q[puesto[u], puesto[v]] += coef / 2
        q[puesto[v], puesto[u]] += coef / 2
    return q, variables


def bits_de_entero(valor: int, variables: list) -> dict:
    return {v: (valor >> k) & 1 for k, v in enumerate(variables)}


def energia_hamiltoniano(bqm, bits: dict) -> tuple[float, float, float]:
    """Misma convencion que hamiltoniano_ising: H = (E_bqm - offset) / escala.

    El offset de to_ising no entra en el SparsePauliOp. La escala es el maximo
    valor absoluto de h y J, redondeada a 4 decimales en el JSON del lote.
    """
    h, j, offset = bqm.to_ising()
    escala = max([abs(c) for c in (*h.values(), *j.values())] or [1.0]) or 1.0
    espin = {v: 2 * bits[v] - 1 for v in bits}
    autovalor = 0.0
    for v, coef in h.items():
        autovalor += (-coef / escala) * (-espin[v])
    for (u, v), coef in j.items():
        autovalor += (coef / escala) * (-espin[u]) * (-espin[v])
    energia = bqm.energy(bits)
    return float(energia), float(autovalor), float(escala)


def codificar_ruta(modelo, ruta: list) -> dict:
    """Aristas r=1 del camino 0..fin. La inversa queda en r=2 y el resto en r=0 o r=2."""
    fin = modelo.N + 1
    camino = list(ruta) + [fin]
    tour = set(zip(camino, camino[1:]))
    bits = {v: 0 for v in modelo.bqm.variables}
    pares = {(i, j) for (i, j, _) in modelo.var_index}
    for i, j in pares:
        if (i, j) in tour:
            bits[modelo.var_index[(i, j, 1)]] = 1
        elif (j, i) in tour:
            bits[modelo.var_index[(i, j, 2)]] = 1
    vistos = set()
    for i, j in pares:
        if (i, j) in vistos or (j, i) in vistos:
            continue
        if any(bits[modelo.var_index[(i, j, r)]] for r in range(3)):
            vistos.add((i, j))
            vistos.add((j, i))
            continue
        a, b = (i, j) if i < j else (j, i)
        bits[modelo.var_index[(a, b, 2)]] = 1
        bits[modelo.var_index[(b, a, 0)]] = 1
        vistos.add((i, j))
        vistos.add((j, i))
    return bits


def grupos_exactamente_uno(modelo) -> list[tuple[str, list]]:
    n_var = modelo.N
    fin = n_var + 1
    num_aug = n_var + 2
    vi = modelo.var_index
    pares = {(i, j) for (i, j, _) in vi}
    grupos = []
    for i, j in sorted(pares):
        grupos.append((f"one-hot ({i},{j})", [vi[(i, j, r)] for r in range(3)]))
    for i in range(0, n_var + 1):
        terminos = [vi[(i, j, 1)] for j in range(num_aug) if (i, j) in pares]
        grupos.append((f"salida r=1 de {i}", terminos))
    for j in range(1, n_var + 2):
        terminos = [vi[(i, j, 1)] for i in range(0, n_var + 1) if (i, j) in pares]
        grupos.append((f"entrada r=1 a {j}", terminos))
    for i, j in sorted(pares):
        if i < j and {i, j} != {0, fin}:
            grupos.append((f"orientacion r=2 {{{i},{j}}}", [vi[(i, j, 2)], vi[(j, i, 2)]]))
    return grupos


def diagnostico_estado(modelo, bits: dict, penalizacion: float) -> list[str]:
    lineas = []
    for nombre, terminos in grupos_exactamente_uno(modelo):
        activos = sum(bits[v] for v in terminos)
        if activos != 1:
            lineas.append(f"{nombre}: {activos} activos, no exactamente uno (penalizacion {penalizacion})")
    return lineas


def enumerar(q: np.ndarray) -> tuple[float, int, int]:
    n = q.shape[0]
    total = 1 << n
    shifts = np.arange(n, dtype=np.uint32)
    mejor = float("inf")
    argmin = 0
    cuantos = 0
    t0 = time.perf_counter()
    for base in range(0, total, BLOQUE):
        idx = np.arange(base, base + BLOQUE, dtype=np.uint32)
        bits = ((idx[:, None] >> shifts) & 1).astype(np.float64)
        energia = ((bits @ q) * bits).sum(axis=1)
        local = float(energia.min())
        if local < mejor - TOL:
            mejor = local
            argmin = int(idx[int(np.argmin(energia))])
            cuantos = int(np.count_nonzero(np.abs(energia - mejor) <= TOL))
        else:
            cuantos += int(np.count_nonzero(np.abs(energia - mejor) <= TOL))
        hecho = base + BLOQUE
        if hecho % (64 * BLOQUE) == 0 or hecho == total:
            print(f"  bloque {hecho}/{total}  min={mejor:.6f}  estados={cuantos}  "
                  f"{time.perf_counter() - t0:.0f}s", flush=True)
    return mejor, argmin, cuantos


def main() -> None:
    doc = json.loads(LOTE.with_suffix(".json").read_text(encoding="utf-8"))
    with LOTE.parent.joinpath("crudos", LOTE.name + ".pkl").open("rb") as archivo:
        lote = pickle.load(archivo)
    if not isinstance(lote, LoteCrudo):
        raise TypeError("el pkl no es un lote del pipeline")
    # El JSON redondea la matriz a 3 decimales. El Hamiltoniano del job uso la matriz del pkl.
    distancias = np.array(lote.instancia.distancias, dtype=float)
    optima = list(lote.ruta_optima)
    dist_optima = float(lote.dist_optima)
    print(f"JSON dist_optima={doc['instancia']['linea_base']['dist_optima']} "
          f"ruta={doc['instancia']['linea_base']['ruta']}", flush=True)
    modelo = construir_modelo("GPS", distancias)
    penalizacion = float(np.sum(distancias) * 2)
    print(f"variables={modelo.num_variables} penalizacion={penalizacion:.6f} "
          f"Held-Karp={dist_optima} ruta={optima}", flush=True)

    bits = codificar_ruta(modelo, optima)
    secuencia, factible = decodificar(modelo, bits)
    energia, autovalor, escala = energia_hamiltoniano(modelo.bqm, bits)
    _, _, offset = modelo.bqm.to_ising()
    print(f"ruta codificada {secuencia} factible={factible}")
    print(f"E_bqm={energia:.6f} offset_ising={offset:.6f} escala={escala:.6f} "
          f"escala_json=53.6947 E_H={(energia - offset) / escala:.6f} autovalor={autovalor:.6f}")
    print(f"restricciones rotas en la ruta optima: {diagnostico_estado(modelo, bits, penalizacion) or 'ninguna'}")

    otra = [0, 1, 2]
    bits_otra = codificar_ruta(modelo, otra)
    sec2, fac2 = decodificar(modelo, bits_otra)
    e2, _, _ = energia_hamiltoniano(modelo.bqm, bits_otra)
    print(f"otra direccion {sec2} factible={fac2} E_bqm={e2:.6f}")

    gps = [c for c in lote.corridas if c.formulacion == "GPS"]
    energias = [c.energia for c in gps]
    print(f"GPS en el pkl: N={len(gps)} E_min={min(energias):.6f} E_max={max(energias):.6f}")
    print("El JSON no guarda energia; estos valores salen del pkl, de cada corrida.energia.")
    for c in gps:
        print(f"  replica {c.parametros.get('replica')} semilla {c.parametros.get('semilla')} "
              f"E={c.energia:.6f} factible={c.factible} secuencia={c.secuencia}")

    print(f"enumeracion 2^{modelo.num_variables} en bloques de {BLOQUE}", flush=True)
    q, variables = matriz_q(modelo.bqm)
    mejor, argmin, cuantos = enumerar(q)
    bits_min = bits_de_entero(argmin, variables)
    sec, fac = decodificar(modelo, bits_min)
    e_min, aut_min, _ = energia_hamiltoniano(modelo.bqm, bits_min)
    print(f"minimo global E_bqm_matriz={mejor:.6f} E_bqm={e_min:.6f} E_H={aut_min:.6f}")
    print(f"estados en el minimo={cuantos} factible={fac} secuencia={sec} "
          f"es_optima={fac and es_permutacion(sec, modelo.n) and abs(sum(distancias[sec[k]][sec[(k + 1) % len(sec)]] for k in range(len(sec))) - dist_optima) < 0.001}")
    rotas = diagnostico_estado(modelo, bits_min, penalizacion)
    print(f"restricciones rotas en el minimo: {rotas or 'ninguna'}")
    print(f"comparacion: minimo {e_min:.6f} frente al rango del hardware GPS "
          f"[{min(energias):.6f}, {max(energias):.6f}]")


if __name__ == "__main__":
    main()
