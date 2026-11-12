"""Brecha al fundamental y grupos exactamente-uno violados, por replica.

Lee los .pkl ya cerrados. No escribe en salidas/ de produccion ni llama a IBM.
E* del QUBO es el minimo de la enumeracion completa. E* del GPS es el minimo
entre las codificaciones estrictas de todos los tours que salen del deposito:
en el lote n=3 de ibm_fez ese valor coincidio con la enumeracion de 2^30.
"""

import json
import pickle
import sys
from itertools import permutations
from pathlib import Path

import matplotlib
import numpy as np
from scipy.stats import mannwhitneyu

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from rutas_atm.experimento import LoteCrudo  # noqa: E402
from rutas_atm.formulacion_tsp import construir_modelo, factible_estricto  # noqa: E402

CRUDOS = RAIZ / "salidas" / "crudos"
SALIDA = RAIZ / "salidas" / "runs_test"
INFORME = SALIDA / "brecha_fundamental_vs_aleatorio.json"

LOTES = {
    (3, "ibm"): ("corridas_i3_n3_ibm_20261111-211121-481.pkl", "ibm_fez"),
    (3, "aleatorio"): ("corridas_i31_n3_aleatorio_20261111-223814-073.pkl", None),
    (4, "ibm"): ("corridas_i4_n4_ibm_20261111-201713-615.pkl", "ibm_kingston"),
    (4, "aleatorio"): ("corridas_i41_n4_aleatorio_20261111-223808-052.pkl", None),
    (4, "ibm_rampa"): ("corridas_i42_n4_ibm_20261111-230125-642.pkl", "ibm_kingston"),
}


def grupos_exactamente_uno(modelo) -> list[list]:
    if modelo.formulacion == "QUBO":
        n = modelo.n
        grupos = [[i * n + p for p in range(n)] for i in range(n)]
        grupos += [[i * n + p for i in range(n)] for p in range(n)]
        return grupos
    N, vi = modelo.N, modelo.var_index
    fin, num_aug = N + 1, N + 2
    pares = {(i, j) for (i, j, _) in vi}
    grupos = [[vi[(i, j, r)] for r in range(3)] for i, j in pares]
    grupos += [[vi[(i, j, 1)] for j in range(num_aug) if (i, j) in pares] for i in range(0, N + 1)]
    grupos += [[vi[(i, j, 1)] for i in range(0, N + 1) if (i, j) in pares] for j in range(1, N + 2)]
    grupos += [
        [vi[(i, j, 2)], vi[(j, i, 2)]]
        for i, j in pares if i < j and {i, j} != {0, fin}
    ]
    return grupos


def violaciones(grupos, bits) -> int:
    return sum(sum(bits.get(v, 0) for v in grupo) != 1 for grupo in grupos)


def codificar_gps(modelo, ruta: list, mascara: int) -> dict:
    fin = modelo.N + 1
    camino = list(ruta) + [fin]
    tour = set(zip(camino, camino[1:]))
    bits = {v: 0 for v in modelo.bqm.variables}
    vi = modelo.var_index
    pares = {(i, j) for (i, j, _) in vi}
    for i, j in pares:
        if (i, j) in tour:
            bits[vi[(i, j, 1)]] = 1
        elif (j, i) in tour:
            bits[vi[(i, j, 2)]] = 1
    libres = []
    vistos = set()
    for i, j in pares:
        if (i, j) in vistos or (j, i) in vistos:
            continue
        vistos.add((i, j))
        vistos.add((j, i))
        if (i, j) not in tour and (j, i) not in tour:
            a, b = (i, j) if i < j else (j, i)
            libres.append((a, b))
    for k, (a, b) in enumerate(libres):
        for r in range(3):
            bits[vi[(a, b, r)]] = 0
            bits[vi[(b, a, r)]] = 0
        if (mascara >> k) & 1:
            bits[vi[(a, b, 2)]] = 1
            bits[vi[(b, a, 0)]] = 1
        else:
            bits[vi[(b, a, 2)]] = 1
            bits[vi[(a, b, 0)]] = 1
    return bits


def fundamental_gps(modelo) -> tuple[float, int, int]:
    mejor = float("inf")
    cuantos = 0
    evaluadas = 0
    clientes = range(1, modelo.n)
    for perm in permutations(clientes):
        bits0 = codificar_gps(modelo, [0, *perm], 0)
        libres = 0
        # la mascara recorre los pares que la codificacion dejo libres; se mide una vez
        ruta = [0, *perm]
        fin = modelo.N + 1
        camino = list(ruta) + [fin]
        tour = set(zip(camino, camino[1:]))
        pares = {(i, j) for (i, j, _) in modelo.var_index}
        vistos = set()
        for i, j in pares:
            if (i, j) in vistos or (j, i) in vistos:
                continue
            vistos.add((i, j))
            vistos.add((j, i))
            if (i, j) not in tour and (j, i) not in tour:
                libres += 1
        for mascara in range(1 << libres):
            bits = bits0 if mascara == 0 and libres == 0 else codificar_gps(modelo, ruta, mascara)
            if not factible_estricto(modelo, bits):
                continue
            evaluadas += 1
            energia = modelo.bqm.energy(bits)
            if energia < mejor - 1e-9:
                mejor = float(energia)
                cuantos = 1
            elif abs(energia - mejor) <= 1e-9:
                cuantos += 1
    if cuantos == 0:
        raise RuntimeError(f"GPS n={modelo.n} no produjo ninguna codificacion estricta")
    return mejor, cuantos, evaluadas


def fundamental_qubo(modelo) -> float:
    variables = list(modelo.bqm.variables)
    n = len(variables)
    mejor = float("inf")
    for indice in range(1 << n):
        bits = {v: (indice >> k) & 1 for k, v in enumerate(variables)}
        energia = modelo.bqm.energy(bits)
        if energia < mejor:
            mejor = float(energia)
    return mejor


def resumir(valores: list[float]) -> dict:
    arr = np.asarray(valores, dtype=float)
    sd = float(arr.std(ddof=1)) if len(arr) >= 2 else None
    return {
        "N": int(len(arr)),
        "media": float(arr.mean()) if len(arr) else None,
        "sd": sd,
        "mediana": float(np.median(arr)) if len(arr) else None,
    }


def comparar(hardware: list[float], aleatorio: list[float]) -> dict:
    if len(hardware) == 0 or len(aleatorio) == 0:
        return {"U": None, "p": None, "estado": "pendiente"}
    prueba = mannwhitneyu(hardware, aleatorio, alternative="two-sided", method="auto")
    return {"U": float(prueba.statistic), "p": float(prueba.pvalue), "estado": "calculado"}


def cargar(nombre: str) -> LoteCrudo:
    ruta = CRUDOS / nombre
    with ruta.open("rb") as archivo:
        lote = pickle.load(archivo)
    if not isinstance(lote, LoteCrudo):
        raise TypeError(ruta.name)
    return lote


def filas_de(lote, formulacion: str, backend: str | None) -> list[dict]:
    distancias = np.array(lote.instancia.distancias, dtype=float)
    modelo = construir_modelo(formulacion, distancias)
    grupos = grupos_exactamente_uno(modelo)
    if formulacion == "QUBO":
        estrella = fundamental_qubo(modelo)
        metodo = "enumeracion_completa"
        codificaciones = 1 << modelo.num_variables
        en_minimo = None
    else:
        estrella, en_minimo, codificaciones = fundamental_gps(modelo)
        metodo = "minimo_de_codificaciones_estrictas"
    filas = []
    for corrida in lote.corridas:
        if corrida.formulacion != formulacion:
            continue
        nombre_backend = (corrida.parametros or {}).get("backend")
        if backend is not None and nombre_backend != backend:
            continue
        energia = float(modelo.bqm.energy(corrida.bits))
        filas.append({
            "id_corrida": corrida.id_corrida,
            "replica": (corrida.parametros or {}).get("replica"),
            "semilla": (corrida.parametros or {}).get("semilla"),
            "backend": nombre_backend,
            "sampler": corrida.sampler,
            "optimizador": (corrida.parametros or {}).get("optimizador"),
            "metodo_angulos": (corrida.parametros or {}).get("metodo_angulos"),
            "angulos": (corrida.parametros or {}).get("angulos"),
            "energia_bqm": energia,
            "brecha": (energia - estrella) / abs(estrella),
            "grupos_violados": violaciones(grupos, corrida.bits),
            "grupos_totales": len(grupos),
            "factible_estricto": factible_estricto(modelo, corrida.bits),
        })
    return filas, {
        "id_instancia": lote.instancia.id_instancia,
        "n": lote.instancia.n,
        "dist_optima": float(lote.dist_optima),
        "ruta_optima": list(lote.ruta_optima),
        "E_estrella": estrella,
        "metodo_E_estrella": metodo,
        "codificaciones_evaluadas": codificaciones,
        "codificaciones_en_E_estrella": en_minimo if formulacion == "GPS" else None,
        "firma_distancias": np.round(distancias, 6).tolist(),
    }


def _guardar(figura, destino: Path) -> str:
    if destino.exists():
        raise FileExistsError(destino)
    figura.savefig(destino, dpi=140)
    plt.close(figura)
    return destino.name


def boxplot(n: int, formulacion: str, hardware: dict, aleatorio: dict,
            nombre: str | None = None, etiquetas: tuple[str, str] = ("hardware", "aleatorio"),
            titulo: str | None = None) -> str:
    figura, ejes = plt.subplots(1, 2, figsize=(8.4, 4.2))
    series = [
        ("brecha", "(E − E*) / |E*|"),
        ("grupos_violados", "Grupos exactamente-uno violados"),
    ]
    for eje, (clave, titulo_eje) in zip(ejes, series):
        datos = [
            [fila[clave] for fila in hardware["replicas"]],
            [fila[clave] for fila in aleatorio["replicas"]],
        ]
        eje.boxplot(datos, tick_labels=list(etiquetas), showmeans=True)
        eje.set_title(titulo_eje)
        eje.set_ylabel(titulo_eje)
    backend = hardware["replicas"][0]["backend"] if hardware["replicas"] else ""
    figura.suptitle(titulo or f"n={n} {formulacion}: {backend} vs aleatorio")
    figura.tight_layout()
    destino = SALIDA / (nombre or f"boxplot_n{n}_{formulacion}.png")
    return _guardar(figura, destino)


def boxplot_tres_brechas(series: list[tuple[str, list[float]]], nombre: str) -> str:
    figura, eje = plt.subplots(figsize=(6.2, 4.2))
    eje.boxplot([valores for _, valores in series], tick_labels=[nombre_serie for nombre_serie, _ in series],
                showmeans=True)
    eje.set_ylabel("(E − E*) / |E*|")
    eje.set_title("n=4 QUBO: COBYLA, rampa y aleatorio")
    figura.tight_layout()
    return _guardar(figura, SALIDA / nombre)


def celda_qubo_rampa(aleatorio_previo: dict | None) -> dict:
    nombre, backend = LOTES[(4, "ibm_rampa")]
    lote = cargar(nombre)
    filas, estrella = filas_de(lote, "QUBO", backend)
    if aleatorio_previo is None:
        nombre_a, _ = LOTES[(4, "aleatorio")]
        filas_a, estrella_a = filas_de(cargar(nombre_a), "QUBO", None)
        aleatorio_previo = {**estrella_a, "archivo": nombre_a, "backend_pedido": None, "replicas": filas_a,
                            "brecha": resumir([f["brecha"] for f in filas_a]),
                            "grupos_violados": resumir([f["grupos_violados"] for f in filas_a])}
    hardware = [fila["brecha"] for fila in filas]
    control = [fila["brecha"] for fila in aleatorio_previo["replicas"]]
    viol_h = [fila["grupos_violados"] for fila in filas]
    viol_a = [fila["grupos_violados"] for fila in aleatorio_previo["replicas"]]
    misma = estrella["firma_distancias"] == aleatorio_previo["firma_distancias"]
    if abs(estrella["E_estrella"] - aleatorio_previo["E_estrella"]) > 1e-6:
        raise RuntimeError("E* de la rampa y del aleatorio no coinciden")
    grafico = boxplot(
        4, "QUBO", {"replicas": filas}, {"replicas": aleatorio_previo["replicas"]},
        nombre="boxplot_n4_QUBO_rampa.png", etiquetas=("rampa", "aleatorio"),
        titulo="n=4 QUBO rampa: ibm_kingston vs aleatorio",
    )
    return {
        "n": 4,
        "formulacion": "QUBO",
        "metodo_angulos": "rampa_lineal",
        "misma_matriz": misma,
        "ibm": {**estrella, "archivo": nombre, "backend_pedido": backend, "replicas": filas,
                "brecha": resumir(hardware), "grupos_violados": resumir(viol_h)},
        "aleatorio": aleatorio_previo,
        "mannwhitney_brecha": comparar(hardware, control),
        "mannwhitney_grupos": comparar(viol_h, viol_a),
        "grafico": grafico,
    }


def grafico_tres_qubo_n4(cobyla: list[float], rampa: list[float], aleatorio: list[float]) -> str:
    return boxplot_tres_brechas(
        [("COBYLA", cobyla), ("rampa", rampa), ("aleatorio", aleatorio)],
        "boxplot_n4_QUBO_brecha_cobyla_rampa_aleatorio.png",
    )


def main() -> None:
    if INFORME.exists():
        raise FileExistsError(f"{INFORME} ya existe")
    SALIDA.mkdir(parents=True, exist_ok=True)
    informe = {"celdas": []}
    for n in (3, 4):
        for formulacion in ("GPS", "QUBO"):
            bloques = {}
            meta = {}
            for sampler in ("ibm", "aleatorio"):
                nombre, backend = LOTES[(n, sampler)]
                lote = cargar(nombre)
                filas, estrella = filas_de(lote, formulacion, backend)
                bloques[sampler] = filas
                meta[sampler] = {**estrella, "archivo": nombre, "backend_pedido": backend}
            hardware = [fila["brecha"] for fila in bloques["ibm"]]
            control = [fila["brecha"] for fila in bloques["aleatorio"]]
            viol_h = [fila["grupos_violados"] for fila in bloques["ibm"]]
            viol_a = [fila["grupos_violados"] for fila in bloques["aleatorio"]]
            misma_matriz = meta["ibm"]["firma_distancias"] == meta["aleatorio"]["firma_distancias"]
            celda = {
                "n": n,
                "formulacion": formulacion,
                "misma_matriz": misma_matriz,
                "ibm": {**meta["ibm"], "replicas": bloques["ibm"],
                        "brecha": resumir(hardware), "grupos_violados": resumir(viol_h)},
                "aleatorio": {**meta["aleatorio"], "replicas": bloques["aleatorio"],
                              "brecha": resumir(control), "grupos_violados": resumir(viol_a)},
                "mannwhitney_brecha": comparar(hardware, control),
                "mannwhitney_grupos": comparar(viol_h, viol_a),
            }
            celda["grafico"] = boxplot(
                n, formulacion,
                {"replicas": bloques["ibm"]},
                {"replicas": bloques["aleatorio"]},
            )
            informe["celdas"].append(celda)
            if n == 4 and formulacion == "QUBO":
                informe["celdas"].append(celda_qubo_rampa(celda["aleatorio"]))
                cobyla = [fila["brecha"] for fila in bloques["ibm"]]
                rampa = [fila["brecha"] for fila in informe["celdas"][-1]["ibm"]["replicas"]]
                informe["grafico_n4_qubo_tres_brechas"] = grafico_tres_qubo_n4(cobyla, rampa, control)
            print(
                f"n={n} {formulacion}: ibm N={len(hardware)} aleatorio N={len(control)} "
                f"E*={meta['ibm']['E_estrella']:.6f}/{meta['aleatorio']['E_estrella']:.6f} "
                f"misma_matriz={misma_matriz} "
                f"p_brecha={celda['mannwhitney_brecha']['p']} p_grupos={celda['mannwhitney_grupos']['p']}"
            )
    INFORME.write_text(json.dumps(informe, ensure_ascii=False, indent=2), encoding="utf-8")
    print(INFORME)


def completar_informe() -> None:
    """Agrega la celda de la rampa sin reescribir los boxplots ya guardados."""
    informe = json.loads(INFORME.read_text(encoding="utf-8"))
    if any(c.get("metodo_angulos") == "rampa_lineal" for c in informe["celdas"]):
        raise FileExistsError("la celda de la rampa ya esta en el informe")
    qubo_n4 = next(c for c in informe["celdas"] if c["n"] == 4 and c["formulacion"] == "QUBO"
                   and c.get("metodo_angulos") != "rampa_lineal")
    celda = celda_qubo_rampa(qubo_n4["aleatorio"])
    informe["celdas"].append(celda)
    informe["grafico_n4_qubo_tres_brechas"] = grafico_tres_qubo_n4(
        [fila["brecha"] for fila in qubo_n4["ibm"]["replicas"]],
        [fila["brecha"] for fila in celda["ibm"]["replicas"]],
        [fila["brecha"] for fila in qubo_n4["aleatorio"]["replicas"]],
    )
    INFORME.write_text(json.dumps(informe, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        f"n=4 QUBO rampa N={celda['ibm']['brecha']['N']} "
        f"p_brecha={celda['mannwhitney_brecha']['p']} p_grupos={celda['mannwhitney_grupos']['p']}"
    )
    print(INFORME)


if __name__ == "__main__":
    if INFORME.exists():
        completar_informe()
    else:
        main()
