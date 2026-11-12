"""Figuras y tabla del poster a partir de lotes ya cerrados.

Lee los JSON que se le pasan. Si junto a un JSON existe su copia
*_estricto.json, usa la copia y no el original. La energia, la factibilidad
estricta y la distancia salen del .pkl (la matriz del JSON esta redondeada).
No escribe en salidas/ ni llama a IBM.
"""

import argparse
import json
import math
import pickle
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from scipy.stats import mannwhitneyu  # noqa: E402

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from rutas_atm.experimento import LoteCrudo  # noqa: E402
from rutas_atm.formulacion_tsp import (  # noqa: E402
    construir_modelo,
    decodificar,
    es_permutacion,
    factible_estricto,
)
from brecha_fundamental_vs_aleatorio import fundamental_gps  # noqa: E402

Z_WILSON = 1.96
TOLERANCIA_KM = 1e-3
CAPACIDAD_KINGSTON = 156

GRIS = "#7A7A7A"
VIOLETA_CLARO = "#B38BD3"
VIOLETA = "#57068C"
ROSA = "#DB2777"

ORDEN_N4 = (
    ("QUBO", "azar", "Azar\n(QUBO)", GRIS),
    ("QUBO", "rampa_fija", "QUBO\nrampa fija", VIOLETA_CLARO),
    ("QUBO", "angulos_optimizados", "QUBO\nángulos\noptimizados", VIOLETA),
    ("GPS", "azar", "Azar\n(GPS)", GRIS),
    ("GPS", "rampa_fija", "GPS\nrampa fija", ROSA),
)
NOMBRE_CONDICION = {
    "azar": "azar",
    "rampa_fija": "rampa fija",
    "angulos_optimizados": "ángulos optimizados",
}
ORDEN_CONDICION = ("azar", "rampa_fija", "angulos_optimizados")


def wilson(aciertos: int, n: int) -> tuple[float, float] | None:
    if n <= 0:
        return None
    p = aciertos / n
    z2 = Z_WILSON ** 2
    den = 1 + z2 / n
    centro = (p + z2 / (2 * n)) / den
    margen = Z_WILSON * math.sqrt(p * (1 - p) / n + z2 / (4 * n * n)) / den
    return max(0.0, centro - margen), min(1.0, centro + margen)


def condicion_de(sampler: str, parametros: dict) -> str | None:
    if sampler == "aleatorio":
        return "azar"
    bruto = parametros.get("metodo_angulos") or parametros.get("optimizador")
    if bruto in ("COBYLA", "optimizado_local", "optimizado"):
        return "angulos_optimizados"
    if bruto == "rampa_lineal":
        return "rampa_fija"
    return None


def formato_p(p: float) -> str:
    if p >= 0.001:
        return f"p = {p:.2f}"
    mantisa, exponente = f"{p:.1e}".split("e")
    return f"p = {mantisa}e{int(exponente)}"


def coma(valor: float, decimales: int) -> str:
    return f"{valor:.{decimales}f}".replace(".", "{,}")


def texto_brecha(valor: float | None) -> str:
    if valor is None:
        return "pendiente"
    if valor == 0:
        return "0"
    if abs(valor) < 0.001:
        return coma(valor, 5)
    if abs(valor) < 0.01:
        return coma(valor, 4)
    return coma(valor, 3)


def fundamental_qubo(modelo) -> tuple[float, int]:
    variables = list(modelo.bqm.variables)
    mejor = float("inf")
    cuantos = 0
    for indice in range(1 << len(variables)):
        bits = {v: (indice >> k) & 1 for k, v in enumerate(variables)}
        energia = float(modelo.bqm.energy(bits))
        if energia < mejor - 1e-9:
            mejor = energia
            cuantos = 1
        elif abs(energia - mejor) <= 1e-9:
            cuantos += 1
    return mejor, cuantos


def cache_estrella(modelo, firma: bytes, cache: dict) -> tuple[float, int | None]:
    clave = (modelo.formulacion, firma)
    if clave in cache:
        return cache[clave]
    if modelo.formulacion == "QUBO":
        mejor, cuantos = fundamental_qubo(modelo)
        cache[clave] = (mejor, cuantos)
    else:
        mejor, cuantos, _evaluadas = fundamental_gps(modelo)
        cache[clave] = (mejor, cuantos)
    return cache[clave]


def json_preferido(ruta: Path) -> tuple[Path, bool]:
    """Devuelve (json a leer, uso la copia estricta)."""
    if ruta.name.endswith("_estricto.json"):
        return ruta, True
    copia = ruta.with_name(f"{ruta.stem}_estricto.json")
    if copia.exists():
        return copia, True
    return ruta, False


def pkl_de(json_path: Path, crudos: Path) -> Path:
    stem = json_path.stem
    if stem.endswith("_estricto"):
        stem = stem[: -len("_estricto")]
    return crudos / f"{stem}.pkl"


def cargar_pkl(ruta: Path) -> LoteCrudo:
    with ruta.open("rb") as archivo:
        lote = pickle.load(archivo)
    if not isinstance(lote, LoteCrudo):
        raise TypeError(f"{ruta} no contiene un lote del pipeline")
    return lote


def excluir_lote(doc: dict, corrida: dict) -> str | None:
    sampler = corrida.get("sampler")
    parametros = corrida.get("parametros") or {}
    backend = (parametros.get("backend") or "") or ""
    shots = parametros.get("shots")
    if parametros.get("shots") is None:
        shots = parametros.get("num_reads")
    n = len(doc["instancia"]["cajeros"])
    if sampler == "simulado":
        return "recocido simulado"
    if n == 5:
        return "n=5 excluido de estas figuras"
    if "marrakesh" in str(backend).lower():
        return "prueba de humo ibm_marrakesh"
    if shots == 1000:
        return "lote de 1000 shots"
    if shots != 200:
        return f"shots={shots}, esta tabla usa 200"
    return None


def reunir(rutas_json: list[Path], crudos: Path) -> tuple[list[dict], list[str], list[str]]:
    replicas = []
    avisos = []
    usados = []
    cache = {}
    vistos = set()
    for ruta in rutas_json:
        elegido, es_copia = json_preferido(ruta)
        if elegido in vistos:
            continue
        vistos.add(elegido)
        pkl_path = pkl_de(elegido, crudos)
        if not pkl_path.exists():
            raise FileNotFoundError(f"no hay .pkl para {elegido.name} en {crudos}")
        doc = json.loads(elegido.read_text(encoding="utf-8"))
        lote = cargar_pkl(pkl_path)
        por_id = {c.id_corrida: c for c in lote.corridas}
        if len(por_id) != len(doc["corridas"]):
            raise RuntimeError(f"{elegido.name} y {pkl_path.name} no tienen las mismas corridas")
        firma = np.asarray(lote.instancia.distancias, dtype=np.float64).tobytes()
        n = int(lote.instancia.n)
        modelos = {}
        for corrida_json in doc["corridas"]:
            motivo = excluir_lote(doc, corrida_json)
            if motivo:
                avisos.append(f"excluida {elegido.name} id {corrida_json['id_corrida']}: {motivo}")
                continue
            cruda = por_id[corrida_json["id_corrida"]]
            if cruda.formulacion != corrida_json["formulacion"]:
                raise RuntimeError(f"formulacion distinta en {elegido.name} id {cruda.id_corrida}")
            formulacion = cruda.formulacion
            if formulacion not in modelos:
                modelos[formulacion] = construir_modelo(
                    formulacion, np.asarray(lote.instancia.distancias, dtype=float)
                )
            modelo = modelos[formulacion]
            secuencia, _ = decodificar(modelo, cruda.bits)
            factible = factible_estricto(modelo, cruda.bits) and es_permutacion(secuencia, modelo.n)
            flag_json = bool(corrida_json["ruta"]["factible"])
            if es_copia and flag_json != factible:
                raise RuntimeError(
                    f"{elegido.name} id {cruda.id_corrida}: la copia estricta dice "
                    f"{flag_json} y el .pkl recalculado dice {factible}"
                )
            if not es_copia and (cruda.parametros or {}).get("criterio_factibilidad") == "estricto":
                if bool(cruda.factible) != factible:
                    raise RuntimeError(
                        f"{pkl_path.name} id {cruda.id_corrida}: el flag estricto guardado "
                        f"no coincide con el recalculo"
                    )
            parametros = cruda.parametros or {}
            condicion = condicion_de(cruda.sampler, parametros)
            if condicion is None:
                avisos.append(
                    f"sin condicion reconocida: {elegido.name} id {cruda.id_corrida}"
                )
                continue
            estrella, cuantos = cache_estrella(modelo, firma, cache)
            energia = float(modelo.bqm.energy(cruda.bits))
            if energia < estrella - 1e-6:
                raise RuntimeError(
                    f"energia {energia} por debajo de E* {estrella} en {pkl_path.name}"
                )
            brecha = (energia - estrella) / abs(estrella)
            optima = factible and abs(cruda.distancia_total - lote.dist_optima) <= TOLERANCIA_KM
            shots = parametros.get("shots")
            if shots is None:
                shots = parametros.get("num_reads")
            replicas.append({
                "archivo_json": elegido.name,
                "archivo_pkl": pkl_path.name,
                "copia_estricta": es_copia,
                "n": n,
                "formulacion": formulacion,
                "condicion": condicion,
                "sampler": cruda.sampler,
                "backend": parametros.get("backend"),
                "shots": shots,
                "semilla": parametros.get("semilla"),
                "replica": parametros.get("replica"),
                "factible": factible,
                "optima": optima,
                "brecha": brecha,
                "E": energia,
                "E_estrella": estrella,
                "codificaciones_en_E": cuantos,
                "qubits": parametros.get("qubits_logicos"),
                "puertas_2q": parametros.get("puertas_2q"),
                "firma": firma,
                "dist_optima": float(lote.dist_optima),
            })
        usados.append(elegido.name)
        usados.append(pkl_path.name)
    return replicas, avisos, usados


def semilla_unica(filas: list[dict], avisos: list[str]) -> list[dict]:
    vistas = set()
    unicas = []
    for fila in sorted(filas, key=lambda f: (f["archivo_json"], f["semilla"] if f["semilla"] is not None else -1)):
        clave = (fila["n"], fila["formulacion"], fila["condicion"], fila["semilla"])
        if fila["semilla"] in vistas or (
            fila["semilla"] is not None and any(
                previa["semilla"] == fila["semilla"] for previa in unicas
            )
        ):
            avisos.append(
                f"semilla {fila['semilla']} repetida en n={fila['n']} {fila['formulacion']} "
                f"{fila['condicion']}; no se vuelve a contar ({fila['archivo_json']})"
            )
            continue
        if fila["semilla"] is not None:
            vistas.add(fila["semilla"])
        unicas.append(fila)
    return unicas


def agrupar(replicas: list[dict], avisos: list[str]) -> dict[tuple, list[dict]]:
    """Una celda es (n, formulacion, condicion). Solo entra un backend y una matriz."""
    bruto = defaultdict(list)
    for fila in replicas:
        bruto[(fila["n"], fila["formulacion"], fila["condicion"])].append(fila)
    celdas = {}
    for clave, filas in bruto.items():
        if clave[2] == "azar":
            firmas = {f["firma"] for f in filas}
            if len(firmas) > 1:
                avisos.append(f"{clave}: el azar mezcla matrices; la celda queda pendiente")
                celdas[clave] = []
                continue
            celdas[clave] = semilla_unica(filas, avisos)
            continue
        backends = {f["backend"] for f in filas}
        shots = {f["shots"] for f in filas}
        if len(backends) != 1 or len(shots) != 1:
            avisos.append(
                f"{clave}: no se suman lotes con backend {sorted(map(str, backends))} "
                f"o shots {sorted(shots)}"
            )
            celdas[clave] = []
            continue
        firmas = {f["firma"] for f in filas}
        if len(firmas) != 1:
            avisos.append(f"{clave}: matrices distintas; no se suman en la misma celda")
            celdas[clave] = []
            continue
        celdas[clave] = semilla_unica(filas, avisos)
    return celdas


def misma_matriz(hardware: list[dict], azar: list[dict]) -> bool:
    if not hardware or not azar:
        return False
    return hardware[0]["firma"] == azar[0]["firma"]


def mann_whitney(hardware: list[dict], azar: list[dict]) -> dict:
    if not hardware or not azar or not misma_matriz(hardware, azar):
        return {"U": None, "p": None, "estado": "pendiente"}
    prueba = mannwhitneyu(
        [f["brecha"] for f in hardware],
        [f["brecha"] for f in azar],
        alternative="two-sided",
        method="auto",
    )
    return {"U": float(prueba.statistic), "p": float(prueba.pvalue), "estado": "calculado"}


def estilo():
    plt.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": ["DejaVu Sans"],
        "axes.labelsize": 20,
        "axes.titlesize": 24,
        "xtick.labelsize": 20,
        "ytick.labelsize": 20,
        "legend.fontsize": 20,
        "axes.linewidth": 1.4,
        "axes.edgecolor": "black",
        "xtick.major.width": 1.2,
        "ytick.major.width": 1.2,
        "xtick.major.size": 6,
        "ytick.major.size": 6,
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "savefig.facecolor": "white",
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
    })


def _caja_y_puntos(ax, posiciones, series, colores):
    datos = [serie for serie in series if serie]
    pos = [p for p, serie in zip(posiciones, series) if serie]
    cols = [c for c, serie in zip(colores, series) if serie]
    if not datos:
        return
    caja = ax.boxplot(
        datos,
        positions=pos,
        widths=0.55,
        patch_artist=True,
        showfliers=False,
        medianprops={"color": "black", "linewidth": 2.2},
        whiskerprops={"color": "black", "linewidth": 1.4},
        capprops={"color": "black", "linewidth": 1.4},
        boxprops={"linewidth": 1.4, "edgecolor": "black"},
    )
    for parche, color in zip(caja["boxes"], cols):
        parche.set_facecolor(color)
        parche.set_alpha(0.55)
    for x, serie, color in zip(posiciones, series, colores):
        if not serie:
            continue
        orden = np.argsort(serie)
        n = len(serie)
        for i, indice in enumerate(orden):
            desplazamiento = 0.0 if n == 1 else (i / (n - 1) - 0.5) * 0.22
            ax.scatter(
                x + desplazamiento, serie[indice],
                s=70, color="black", edgecolors="white", linewidths=0.8, zorder=3,
            )


def _etiquetas_verticales(ax, posiciones, etiquetas):
    ax.set_xticks(posiciones)
    textos = ax.set_xticklabels(etiquetas, rotation=90, ha="center", va="top", fontsize=20)
    for texto in textos:
        texto.set_linespacing(0.85)
    ax.tick_params(axis="x", pad=1)


def _corchete(ax, x1, x2, y, alto, texto):
    ax.plot(
        [x1, x1, x2, x2], [y, y + alto, y + alto, y],
        color="black", linewidth=1.6, solid_capstyle="butt", clip_on=False, zorder=4,
    )
    ax.text(
        (x1 + x2) / 2, y + alto, texto,
        ha="center", va="bottom", fontsize=20, color="black", clip_on=False, zorder=4,
    )


def ideal_qubo_optimizado(ruta: Path) -> list[dict]:
    doc = json.loads(ruta.read_text(encoding="utf-8"))
    grupos = doc.get("grupos") or doc.get("resultados") or doc
    if isinstance(doc, dict) and "grupos" not in doc:
        # el archivo guarda la lista bajo la primera clave que sea una lista de etiquetas
        for valor in doc.values():
            if isinstance(valor, list) and valor and isinstance(valor[0], dict) and "etiqueta" in valor[0]:
                grupos = valor
                break
    elegidos = []
    for grupo in grupos:
        etiqueta = str(grupo.get("etiqueta", ""))
        if "QUBO n=4" in etiqueta and "COBYLA" in etiqueta:
            muestreo = grupo["muestreo"]
            elegidos.append({
                "etiqueta": etiqueta,
                "angulos": grupo.get("angulos"),
                "fraccion": muestreo["argmin_bqm_decodifica_optima"] / muestreo["repeticiones"],
                "aciertos": muestreo["argmin_bqm_decodifica_optima"],
                "repeticiones": muestreo["repeticiones"],
                "fundamentales": grupo.get("cadenas_en_energia_fundamental"),
                "qubits": grupo.get("qubits"),
            })
    if not elegidos:
        raise RuntimeError(f"{ruta} no tiene la columna de QUBO n=4 optimizado")
    return elegidos


def figura_central(celdas: dict, comparaciones: dict, ideales: list[dict], azar_analitico: float | None, salida: Path):
    estilo()
    fig, ejes = plt.subplots(1, 2, figsize=(36 / 2.54, 14 / 2.54))
    ax_a, ax_b = ejes
    posiciones = list(range(len(ORDEN_N4)))
    series = []
    colores = []
    etiquetas = []
    optimas = []
    intervalos = []
    for formulacion, condicion, titulo, color in ORDEN_N4:
        filas = celdas.get((4, formulacion, condicion), [])
        series.append([f["brecha"] for f in filas])
        colores.append(color)
        n = len(filas)
        etiquetas.append(f"{titulo}\nN = {n}" if n else f"{titulo}\npendiente")
        k = sum(f["optima"] for f in filas)
        optimas.append((k, n))
        intervalos.append(wilson(k, n) if n else None)

    _caja_y_puntos(ax_a, posiciones, series, colores)
    _etiquetas_verticales(ax_a, posiciones, etiquetas)
    ax_a.set_ylabel("menor\nes mejor\n(E−E*)\n/|E*|")
    ax_a.set_title("Brecha de energía\nal fundamental, n = 4", pad=4)
    ax_a.set_xlim(-0.6, len(ORDEN_N4) - 0.4)
    ax_a.grid(False)
    techos = [max(serie) if serie else 0.0 for serie in series]
    span = max(techos) if any(techos) else 1.0
    ax_a.set_ylim(0, span * 1.85)

    for x, (k, n), color, intervalo in zip(posiciones, optimas, colores, intervalos):
        if n == 0:
            ax_b.text(x, 0.02, "pendiente", ha="center", va="bottom", fontsize=20, rotation=90)
            continue
        lo, hi = intervalo
        ax_b.bar(
            x, k / n, width=0.62, color=color, edgecolor="black", linewidth=1.3, zorder=2,
        )
        ax_b.errorbar(
            x, k / n, yerr=[[k / n - lo], [hi - k / n]],
            fmt="none", ecolor="black", elinewidth=1.5, capsize=7, capthick=1.5, zorder=3,
        )
        ax_b.text(x, hi + 0.025, f"{k}/{n}", ha="center", va="bottom", fontsize=20)

    from matplotlib.lines import Line2D
    leyenda = []
    if ideales:
        xs = [2.55] * len(ideales)
        ys = [item["fraccion"] for item in ideales]
        ax_b.scatter(
            xs, ys, s=220, marker="D", facecolors="none", edgecolors="black",
            linewidths=2.0, zorder=4,
        )
        leyenda.append(Line2D(
            [], [], marker="D", linestyle="None", markersize=14,
            markerfacecolor="none", markeredgecolor="black", markeredgewidth=2,
            label="ideal sin ruido, QUBO optimizado",
        ))
    if azar_analitico is not None:
        ax_b.axhline(
            azar_analitico, color="black", linestyle="--", linewidth=1.8, zorder=1,
        )
        leyenda.append(Line2D(
            [], [], color="black", linestyle="--", linewidth=1.8,
            label=f"azar analítico ({azar_analitico * 100:.2f} %)",
        ))
    _etiquetas_verticales(ax_b, posiciones, etiquetas)
    ax_b.set_ylabel("mayor\nes mejor\nfracción\nréplicas")
    ax_b.set_title("Rutas óptimas factibles\n(criterio estricto)", pad=4)
    ax_b.set_xlim(-0.6, len(ORDEN_N4) - 0.4)
    ax_b.set_ylim(0, 1.22)
    ax_b.grid(False)
    if leyenda:
        fig.legend(
            handles=leyenda, loc="lower center", bbox_to_anchor=(0.5, 0.006),
            ncol=2, frameon=False, fontsize=20, columnspacing=1.4,
        )
    fig.subplots_adjust(left=0.18, right=0.985, bottom=0.525, top=0.855, wspace=0.42)
    fig.canvas.draw()
    y0, y1 = ax_a.get_ylim()
    alto_eje = ax_a.get_window_extent().height
    alto_texto = (22 / 72) * fig.dpi / alto_eje * (y1 - y0)
    alto_corchete = alto_texto * 0.22
    hueco = alto_texto * 0.35

    def poner(indice_h, indice_a, y_minimo):
        formulacion, condicion = ORDEN_N4[indice_h][0], ORDEN_N4[indice_h][1]
        prueba = comparaciones.get((formulacion, condicion), {})
        texto = formato_p(prueba["p"]) if prueba.get("estado") == "calculado" else "pendiente"
        base = max(max(techos[indice_h], techos[indice_a]) + hueco, y_minimo)
        _corchete(ax_a, indice_a, indice_h, base, alto_corchete, texto)
        return base + alto_corchete + alto_texto

    tope_rampa = poner(1, 0, 0)
    tope_opt = poner(2, 0, tope_rampa + hueco)
    tope_gps = poner(4, 3, 0)
    ax_a.set_ylim(0, max(tope_rampa, tope_opt, tope_gps) + hueco)
    fig.savefig(salida / "fig_central_n4.pdf")
    fig.savefig(salida / "fig_central_n4.png", dpi=120)
    plt.close(fig)


def leer_sondeo(ruta: Path) -> dict:
    """Una réplica por formulación. No entra en las celdas de la tabla."""
    doc = json.loads(ruta.read_text(encoding="utf-8"))
    n = len(doc["instancia"]["cajeros"])
    grupos = {}
    for corrida in doc["corridas"]:
        parametros = corrida.get("parametros") or {}
        grupos.setdefault(corrida["formulacion"], []).append(parametros)
    resumen = {"n": n, "archivo": ruta.name, "formulaciones": {}}
    for formulacion, parametros in grupos.items():
        backends = {p.get("backend") for p in parametros}
        qubits = {p.get("qubits_logicos") for p in parametros}
        puertas = [p.get("puertas_2q") for p in parametros if p.get("puertas_2q") is not None]
        if len(backends) != 1 or None in backends or len(qubits) != 1 or None in qubits or not puertas:
            raise RuntimeError(f"{ruta.name}: {formulacion} no tiene un solo backend, qubits y puertas")
        resumen["formulaciones"][formulacion] = {
            "qubits": int(next(iter(qubits))),
            "puertas": int(puertas[0]) if len(set(puertas)) == 1 else None,
            "puertas_min": int(min(puertas)),
            "puertas_max": int(max(puertas)),
            "backend": next(iter(backends)),
            "N": len(parametros),
        }
    return resumen


def _qubits_de(celdas: dict, n: int, formulacion: str):
    valores = {
        fila["qubits"]
        for condicion in ("rampa_fija", "angulos_optimizados")
        for fila in celdas.get((n, formulacion, condicion), [])
        if fila["qubits"] is not None
    }
    if len(valores) != 1:
        return None
    return next(iter(valores))


def razon_qubits(celdas: dict, sondeo: dict | None):
    """Promedio de GPS/QUBO en los n medidos. None si falta un par."""
    if not sondeo:
        return None
    pares = []
    for n in (3, 4):
        qubo = _qubits_de(celdas, n, "QUBO")
        gps = _qubits_de(celdas, n, "GPS")
        if qubo is None or gps is None:
            return None
        pares.append((n, gps / qubo))
    formas = sondeo["formulaciones"]
    if "QUBO" not in formas or "GPS" not in formas:
        return None
    pares.append((sondeo["n"], formas["GPS"]["qubits"] / formas["QUBO"]["qubits"]))
    media = sum(razon for _, razon in pares) / len(pares)
    return {"pares": pares, "media": media}


def figura_recursos(celdas: dict, salida: Path, sondeo: dict | None = None):
    from matplotlib.lines import Line2D

    estilo()
    fig, ejes = plt.subplots(1, 2, figsize=(36 / 2.54, 11 / 2.54))
    ax_q, ax_g = ejes
    series = {"QUBO": VIOLETA, "GPS": ROSA}

    for formulacion, color in series.items():
        for n in (3, 4):
            filas = []
            for condicion in ("rampa_fija", "angulos_optimizados"):
                filas.extend(celdas.get((n, formulacion, condicion), []))
            qubits = sorted({f["qubits"] for f in filas if f["qubits"] is not None})
            puertas = [f["puertas_2q"] for f in filas if f["puertas_2q"] is not None]
            if len(qubits) == 1:
                ax_q.scatter([n], qubits, s=160, color=color, zorder=3)
                if formulacion == "GPS":
                    ax_q.annotate(
                        str(qubits[0]), (n, qubits[0]), textcoords="offset points",
                        xytext=(12, 4), fontsize=20, color="black", ha="left", va="bottom",
                    )
                else:
                    ax_q.annotate(
                        str(qubits[0]), (n, qubits[0]), textcoords="offset points",
                        xytext=(-10, 4), fontsize=20, color="black", ha="right", va="bottom",
                    )
            if puertas:
                lo, hi = min(puertas), max(puertas)
                ax_g.plot([n, n], [lo, hi], color=color, linewidth=4, solid_capstyle="butt", zorder=2)
                ax_g.scatter([n, n], [lo, hi], s=80, color=color, zorder=3)
                texto = str(lo) if lo == hi else f"{lo}–{hi}"
                if formulacion == "GPS":
                    ax_g.annotate(
                        texto, (n, hi), textcoords="offset points", xytext=(8, 2),
                        fontsize=20, color="black", ha="left", va="bottom",
                    )
                elif n == 3:
                    ax_g.annotate(
                        texto, (n, (lo + hi) / 2), textcoords="offset points", xytext=(-8, 0),
                        fontsize=20, color="black", ha="right", va="center",
                    )
                else:
                    ax_g.annotate(
                        texto, (n, lo), textcoords="offset points", xytext=(8, -6),
                        fontsize=20, color="black", ha="left", va="top",
                    )
        if sondeo and formulacion in sondeo["formulaciones"]:
            punto = sondeo["formulaciones"][formulacion]
            n = sondeo["n"]
            ax_q.scatter(
                [n], [punto["qubits"]], s=180, facecolors="none", edgecolors=color,
                linewidths=2.2, zorder=4,
            )
            ax_q.annotate(
                str(punto["qubits"]), (n, punto["qubits"]), textcoords="offset points",
                xytext=(12, 0) if formulacion == "GPS" else (-10, 0),
                fontsize=20, color="black",
                ha="left" if formulacion == "GPS" else "right", va="center",
            )
            if punto["puertas"] is not None:
                ax_g.scatter(
                    [n], [punto["puertas"]], s=140, facecolors="none", edgecolors=color,
                    linewidths=2.2, zorder=4,
                )
                ax_g.annotate(
                    str(punto["puertas"]), (n, punto["puertas"]), textcoords="offset points",
                    xytext=(10, 0), fontsize=20, color="black", ha="left", va="center",
                )

    ax_q.axhline(CAPACIDAD_KINGSTON, color="black", linewidth=1.5, linestyle="-")
    ax_q.text(
        2.3, CAPACIDAD_KINGSTON + 4, "capacidad de ibm_kingston",
        fontsize=20, ha="left", va="bottom", color="black",
    )
    razon = razon_qubits(celdas, sondeo)
    if razon is not None:
        ax_q.text(
            2.35, 128,
            f"GPS ≈ {razon['media']:.1f}× los qubits del QUBO",
            fontsize=20, ha="left", va="center", color="black",
        )
    for ax, titulo in (
        (ax_q, "Qubits lógicos"),
        (ax_g, "Puertas de 2 qubits"),
    ):
        ax.set_xticks([3, 4, 5])
        ax.set_xticklabels(["3", "4", "5"])
        ax.set_xlabel("n")
        ax.set_ylabel(titulo)
        ax.set_xlim(2.05, 5.85)
        ax.grid(False)
    ax_q.set_ylim(0, 190)
    handles = [
        Line2D([0], [0], marker="o", color=VIOLETA, linestyle="None", markersize=14, label="QUBO"),
        Line2D([0], [0], marker="o", color=ROSA, linestyle="None", markersize=14, label="GPS"),
    ]
    if sondeo:
        backends = {p["backend"] for p in sondeo["formulaciones"].values()}
        ns = {p["N"] for p in sondeo["formulaciones"].values()}
        if len(backends) == 1 and ns == {1}:
            handles.append(Line2D(
                [0], [0], marker="o", linestyle="None", markersize=14,
                markerfacecolor="none", markeredgecolor="black", markeredgewidth=2,
                label="sondeo, 1 corrida",
            ))
            fig.text(
                0.5, 0.03,
                f"n = {sondeo['n']}: sondeo de una réplica en {next(iter(backends))}",
                ha="center", va="bottom", fontsize=20, color="black",
            )
    fig.legend(
        handles=handles, loc="upper center", ncol=3, frameon=False, fontsize=20,
        bbox_to_anchor=(0.5, 0.985),
    )
    ymax = ax_g.get_ylim()[1]
    ax_g.set_ylim(0, ymax * 1.22 if ymax else 1)
    fig.subplots_adjust(left=0.11, right=0.985, bottom=0.24, top=0.84, wspace=0.28)
    fig.savefig(salida / "fig_recursos.pdf")
    fig.savefig(salida / "fig_recursos.png", dpi=120)
    plt.close(fig)
    return razon


def rango_enteros(valores: list) -> str:
    limpios = [v for v in valores if v is not None]
    if not limpios:
        return "pendiente"
    lo, hi = min(limpios), max(limpios)
    if lo == hi:
        return str(lo)
    return f"{lo}--{hi}"


def fila_tabla(n: int, formulacion: str, condicion: str, filas: list[dict]) -> str:
    nombre = f"{formulacion}, {NOMBRE_CONDICION[condicion]}"
    if filas and condicion != "azar" and filas[0]["backend"]:
        nombre += f" ({filas[0]['backend']})"
    if not filas:
        return f"{n} & {nombre} & pendiente & pendiente & pendiente & pendiente & pendiente & pendiente \\\\"
    N = len(filas)
    k_f = sum(f["factible"] for f in filas)
    k_o = sum(f["optima"] for f in filas)
    intervalo = wilson(k_f, N)
    factibles = f"{k_f}/{N} ({coma(intervalo[0], 2)}--{coma(intervalo[1], 2)})"
    optimas = f"{k_o}/{N}"
    brechas = sorted(f["brecha"] for f in filas)
    mediana = float(np.median(brechas))
    qubits = rango_enteros([f["qubits"] for f in filas])
    puertas = rango_enteros([f["puertas_2q"] for f in filas]).replace("–", "--")
    return (
        f"{n} & {nombre} & {N} & {factibles} & {optimas} & {texto_brecha(mediana)} "
        f"& {qubits} & {puertas} \\\\"
    )


def escribir_tabla(celdas: dict, salida: Path):
    lineas = [
        "% Tabla del poster. Generada por scripts/figuras_poster.py.",
        "% Incluir el entorno table; el documento es compilable con XeLaTeX.",
        r"\documentclass{article}",
        r"\usepackage{fontspec}",
        r"\usepackage[spanish]{babel}",
        r"\usepackage{booktabs}",
        r"\usepackage[paperwidth=42cm,paperheight=16cm,margin=0.8cm]{geometry}",
        r"\begin{document}",
        r"\begin{table}[ht]",
        r"\centering",
        r"\begin{tabular}{@{}llrlllll@{}}",
        r"\toprule",
        r"$n$ & Formulación y condición & $N$ & Factibles estrictas & Rutas óptimas & "
        r"Brecha mediana & Qubits & Puertas de 2 qubits \\",
        r" &  &  & $k/N$ (Wilson 95\,\%) & $k/N$ & $(E-E^*)/|E^*|$ &  & mín.--máx. \\",
        r"\midrule",
    ]
    for n in (3, 4):
        for formulacion in ("QUBO", "GPS"):
            for condicion in ORDEN_CONDICION:
                lineas.append(fila_tabla(n, formulacion, condicion, celdas.get((n, formulacion, condicion), [])))
        if n == 3:
            lineas.append(r"\midrule")
    lineas.extend([
        r"\bottomrule",
        r"\end{tabular}",
        r"\par\vspace{0.5em}",
        r"{\normalsize criterio estricto; un solo backend por celda; 200 shots; "
        r"simulador e IBM no se mezclan\par}",
        r"\end{table}",
        r"\end{document}",
        "",
    ])
    (salida / "tabla_resultados.tex").write_text("\n".join(lineas), encoding="utf-8")


def escribir_fuentes(salida: Path, usados: list[str], ideal: Path, celdas: dict, comparaciones: dict,
                     ideales: list[dict], azar_analitico: float | None, avisos: list[str],
                     sondeo: dict | None = None, razon: dict | None = None):
    fecha = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %Z")
    lineas = [
        "# Fuentes de las figuras del póster",
        "",
        f"Generado: {fecha}.",
        "",
        "Cada cifra sale de estos archivos. Donde no hay medición, la tabla y las figuras dicen pendiente.",
        "",
        "## Archivos",
        "",
    ]
    for nombre in sorted(set(usados)):
        lineas.append(f"- `{nombre}`")
    lineas.append(f"- `{ideal.name}` (simulación ideal sin ruido; columna menor energía óptima)")
    if sondeo:
        lineas.append(
            f"- `{sondeo['archivo']}` (sondeo n={sondeo['n']}, una réplica; solo la figura de recursos)"
        )
    lineas.extend(["", "## N por celda", ""])
    lineas.append("| n | formulación | condición | N | backend | archivos |")
    lineas.append("|---|---|---|---|---|---|")
    for n in (3, 4):
        for formulacion in ("QUBO", "GPS"):
            for condicion in ORDEN_CONDICION:
                filas = celdas.get((n, formulacion, condicion), [])
                if not filas:
                    lineas.append(f"| {n} | {formulacion} | {NOMBRE_CONDICION[condicion]} | pendiente |  |  |")
                    continue
                backend = filas[0]["backend"] or "—"
                archivos = ", ".join(sorted({f["archivo_json"] for f in filas}))
                lineas.append(
                    f"| {n} | {formulacion} | {NOMBRE_CONDICION[condicion]} | {len(filas)} | {backend} | {archivos} |"
                )
    lineas.extend(["", "## Conteos y mediana exacta de la brecha", ""])
    for n in (3, 4):
        for formulacion in ("QUBO", "GPS"):
            for condicion in ORDEN_CONDICION:
                filas = celdas.get((n, formulacion, condicion), [])
                if not filas:
                    continue
                mediana = float(np.median([f["brecha"] for f in filas]))
                lineas.append(
                    f"- n={n} {formulacion} {NOMBRE_CONDICION[condicion]}: "
                    f"factibles {sum(f['factible'] for f in filas)}/{len(filas)}, "
                    f"óptimas {sum(f['optima'] for f in filas)}/{len(filas)}, "
                    f"mediana {(mediana)}"
                )
    lineas.extend(["", "## Mann-Whitney, brecha, hardware contra su azar", ""])
    for (formulacion, condicion), prueba in sorted(comparaciones.items()):
        if prueba.get("estado") != "calculado":
            lineas.append(f"- n=4 {formulacion} {NOMBRE_CONDICION[condicion]}: pendiente")
        else:
            lineas.append(
                f"- n=4 {formulacion} {NOMBRE_CONDICION[condicion]}: "
                f"U = {prueba['U']}, p = {prueba['p']}"
            )
    lineas.extend(["", "## Simulación ideal, QUBO n=4 ángulos optimizados", ""])
    for item in ideales:
        lineas.append(
            f"- {item['etiqueta']}: {item['aciertos']}/{item['repeticiones']} "
            f"= {item['fraccion']}"
        )
    if azar_analitico is None:
        lineas.append("- Azar analítico: pendiente")
    else:
        lineas.append(
            f"- Azar analítico: {azar_analitico} = 1-(1-k/2^q)^200, "
            "con k igual al número de cadenas en E* del QUBO n=4."
        )
    if sondeo:
        lineas.extend(["", "## Sondeo n=5, figura de recursos", ""])
        for formulacion, punto in sondeo["formulaciones"].items():
            lineas.append(
                f"- {formulacion}: N={punto['N']}, backend {punto['backend']}, "
                f"qubits {punto['qubits']}, puertas de 2 qubits {punto['puertas_min']}"
                + ("" if punto["puertas_min"] == punto["puertas_max"] else f"–{punto['puertas_max']}")
            )
    if razon:
        detalle = ", ".join(f"n={n}: {valor:.6f}" for n, valor in razon["pares"])
        lineas.append(f"- Promedio GPS/QUBO: {razon['media']} ({detalle})")
    lineas.extend([
        "",
        "## Qué no entra",
        "",
        "Lotes de 1000 shots, recocido simulado y la prueba de humo de ibm_marrakesh no entran en la tabla.",
        "El sondeo n=5 es una réplica en ibm_fez. Marcador hueco. No se suma a las celdas de n=3 ni n=4.",
        "No hay curva ajustada. La nota de qubits es el promedio de GPS/QUBO en n=3, n=4 y n=5.",
        "La brecha mediana usa todas las réplicas de la celda, factibles o no.",
        "Una ruta óptima cuenta si es factible estricta y su distancia está a lo sumo a 0,001 km del Held-Karp.",
        "",
    ])
    if avisos:
        lineas.append("## Avisos")
        lineas.append("")
        for aviso in avisos:
            lineas.append(f"- {aviso}")
        lineas.append("")
    (salida / "FUENTES.md").write_text("\n".join(lineas), encoding="utf-8")


def azar_analitico_de(celdas: dict, ideales: list[dict]) -> float | None:
    filas = celdas.get((4, "QUBO", "azar"), [])
    if not filas:
        return None
    cuantos = {f["codificaciones_en_E"] for f in filas}
    qubits = {f["qubits"] for f in filas}
    shots = {f["shots"] for f in filas}
    if len(cuantos) != 1 or len(qubits) != 1 or len(shots) != 1:
        return None
    k = cuantos.pop()
    q = qubits.pop()
    s = shots.pop()
    if k is None or q is None or s is None:
        return None
    ideales_k = {item["fundamentales"] for item in ideales}
    if ideales_k != {k}:
        raise RuntimeError(
            f"el JSON ideal cuenta {sorted(ideales_k)} cadenas en E* y la enumeración del lote cuenta {k}"
        )
    return 1 - (1 - k / 2 ** q) ** s


def main():
    parser = argparse.ArgumentParser(description="Figuras y tabla del poster")
    parser.add_argument("--lote", action="append", required=True, type=Path,
                        help="JSON de un lote. Se repite una vez por archivo.")
    parser.add_argument("--crudos", required=True, type=Path, help="Directorio con los .pkl")
    parser.add_argument("--ideal", required=True, type=Path,
                        help="JSON de la simulación ideal sin ruido")
    parser.add_argument("--salida", required=True, type=Path, help="Directorio de PDF, PNG, tex y FUENTES")
    parser.add_argument("--sondeo", type=Path, default=None,
                        help="JSON de un sondeo de una réplica. Solo entra en la figura de recursos.")
    args = parser.parse_args()
    args.salida.mkdir(parents=True, exist_ok=True)
    replicas, avisos, usados = reunir(args.lote, args.crudos)
    celdas = agrupar(replicas, avisos)
    comparaciones = {}
    for _formulacion, condicion, _titulo, _color in ORDEN_N4:
        if condicion == "azar":
            continue
        hardware = celdas.get((4, _formulacion, condicion), [])
        azar = celdas.get((4, _formulacion, "azar"), [])
        comparaciones[(_formulacion, condicion)] = mann_whitney(hardware, azar)
    ideales = ideal_qubo_optimizado(args.ideal)
    analitico = azar_analitico_de(celdas, ideales)
    sondeo = leer_sondeo(args.sondeo) if args.sondeo else None
    figura_central(celdas, comparaciones, ideales, analitico, args.salida)
    razon = figura_recursos(celdas, args.salida, sondeo)
    escribir_tabla(celdas, args.salida)
    escribir_fuentes(
        args.salida, usados, args.ideal, celdas, comparaciones, ideales, analitico, avisos,
        sondeo, razon,
    )
    for clave, filas in sorted(celdas.items()):
        print(f"celda n={clave[0]} {clave[1]} {clave[2]} N={len(filas)}")
    for clave, prueba in comparaciones.items():
        print(f"MW {clave}: {prueba}")
    print(f"azar analitico={analitico}")
    if razon:
        print(f"razon qubits media={razon['media']} pares={razon['pares']}")
    print(args.salida)


if __name__ == "__main__":
    main()
