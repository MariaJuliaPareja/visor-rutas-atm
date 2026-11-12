"""Agrega corridas por celda experimental.

No mezcla lotes con criterio_factibilidad distinto. Si junto a un JSON laxo
existe su copia *_estricto.json, el original no entra. Las rutas bajo runs_test
tampoco entran.
"""

import json
import math
import sys
from collections import defaultdict
from pathlib import Path

Z_WILSON = 1.96


def criterio_de(corrida: dict) -> str:
    valor = (corrida.get("parametros") or {}).get("criterio_factibilidad")
    return valor if valor else "laxo"


def metodo_de(parametros: dict) -> str:
    bruto = parametros.get("metodo_angulos") or parametros.get("optimizador") or "sin_angulos"
    if bruto in ("COBYLA", "optimizado_local", "optimizado"):
        return "optimizado"
    return bruto


def lecturas_de(parametros: dict):
    if parametros.get("shots") is not None:
        return parametros["shots"]
    return parametros.get("num_reads")


def archivos_a_leer(directorio: Path) -> tuple[list[Path], list[Path]]:
    """Devuelve (elegidos, ignorados). Ignora el laxo cuando existe *_estricto.json."""
    candidatos = [
        ruta for ruta in sorted(directorio.glob("*.json"))
        if "runs_test" not in ruta.parts
    ]
    nombres = {ruta.name for ruta in candidatos}
    elegidos, ignorados = [], []
    for ruta in candidatos:
        if ruta.name.endswith("_estricto.json"):
            elegidos.append(ruta)
            continue
        if f"{ruta.stem}_estricto.json" in nombres:
            ignorados.append(ruta)
            continue
        elegidos.append(ruta)
    return elegidos, ignorados


def _semilla(corrida: dict):
    parametros = corrida.get("parametros") or {}
    if parametros.get("semilla") is not None:
        return parametros["semilla"]
    return parametros.get("seed")


def _optima(corrida: dict, dist_optima: float) -> bool:
    if not corrida["ruta"]["factible"]:
        return False
    return abs(corrida["metricas"]["distancia_total"] - dist_optima) <= 1e-3


def wilson(aciertos: int, n: int) -> tuple[float, float] | None:
    if n == 0:
        return None
    p = aciertos / n
    den = 1 + Z_WILSON ** 2 / n
    centro = (p + Z_WILSON ** 2 / (2 * n)) / den
    margen = Z_WILSON * math.sqrt(p * (1 - p) / n + Z_WILSON ** 2 / (4 * n * n)) / den
    return centro - margen, centro + margen


def agrupar(documentos: list[tuple[Path, dict]]) -> tuple[dict, list[str]]:
    """Agrupa por n, optimo, formulacion, metodo, lecturas, backend, sampler y criterio."""
    celdas = defaultdict(list)
    avisos = []
    for ruta, doc in documentos:
        n = len(doc["instancia"]["cajeros"])
        optimo = doc["instancia"]["linea_base"]["dist_optima"]
        for corrida in doc["corridas"]:
            parametros = corrida.get("parametros") or {}
            clave = (
                n, optimo, corrida["formulacion"], metodo_de(parametros),
                lecturas_de(parametros), parametros.get("backend"), corrida["sampler"],
                criterio_de(corrida),
            )
            celdas[clave].append((ruta.name, corrida, optimo))
    separadas = defaultdict(set)
    for clave in celdas:
        separadas[clave[:4] + clave[6:8]].add((clave[4], clave[5]))
    for comun, variantes in separadas.items():
        if len(variantes) > 1:
            avisos.append(
                "celdas separadas por lecturas o backend: "
                f"n={comun[0]} optimo={comun[1]} {comun[2]} {comun[3]} {comun[4]} {comun[5]} -> {sorted(variantes)}"
            )
    limpias = {}
    for clave, filas in celdas.items():
        vistas = set()
        unicas = []
        for nombre, corrida, optimo in filas:
            semilla = _semilla(corrida)
            if semilla in vistas:
                avisos.append(f"semilla {semilla} repetida en {clave}; se cuenta una vez ({nombre})")
                continue
            vistas.add(semilla)
            unicas.append((corrida, optimo))
        limpias[clave] = unicas
    return limpias, avisos


def resumir(clave, filas) -> dict:
    n, optimo, formulacion, metodo, lecturas, backend, sampler, criterio = clave
    factibles = [(c, o) for c, o in filas if c["ruta"]["factible"]]
    optimas = sum(1 for c, o in filas if _optima(c, o))
    dists = [c["metricas"]["distancia_total"] for c, _ in factibles]
    if len(dists) >= 2:
        media = sum(dists) / len(dists)
        varianza = sum((d - media) ** 2 for d in dists) / (len(dists) - 1)
        sd = math.sqrt(varianza)
    else:
        media = dists[0] if dists else None
        sd = None
    intervalo = wilson(len(factibles), len(filas))

    def rango(campo):
        valores = [
            c["parametros"].get(campo)
            for c, _ in filas
            if c.get("parametros") and c["parametros"].get(campo) is not None
        ]
        if not valores:
            return None, None
        return min(valores), max(valores)

    qubits = next((c["parametros"].get("qubits_logicos") or c["parametros"].get("num_variables")
                   for c, _ in filas if c.get("parametros")), None)
    prof = rango("profundidad")
    puertas = rango("puertas_2q")
    return {
        "n": n,
        "optimo": optimo,
        "formulacion": formulacion,
        "metodo": metodo,
        "lecturas": lecturas,
        "backend": backend,
        "sampler": sampler,
        "criterio": criterio,
        "N": len(filas),
        "factibles": len(factibles),
        "wilson": intervalo,
        "media": media,
        "sd": sd,
        "optimas": optimas,
        "qubits": qubits,
        "profundidad": prof,
        "puertas_2q": puertas,
    }


def cargar(directorio: Path) -> tuple[list[tuple[Path, dict]], list[Path]]:
    elegidos, ignorados = archivos_a_leer(directorio)
    documentos = []
    for ruta in elegidos:
        documentos.append((ruta, json.loads(ruta.read_text(encoding="utf-8"))))
    return documentos, ignorados


def main(argv: list[str]) -> None:
    directorio = Path(argv[1] if len(argv) > 1 else "salidas")
    documentos, ignorados = cargar(directorio)
    for ruta in ignorados:
        print(f"ignora laxo {ruta.name}")
    if not documentos:
        print("pendiente")
        return
    celdas, avisos = agrupar(documentos)
    for aviso in avisos:
        print(aviso)
    for clave in sorted(celdas, key=lambda c: tuple(str(x) for x in c)):
        fila = resumir(clave, celdas[clave])
        intervalo = "n/a" if fila["wilson"] is None else f"[{fila['wilson'][0]:.3f}, {fila['wilson'][1]:.3f}]"
        sd = "n/a" if fila["sd"] is None else f"{fila['sd']:.3f}"
        media = "n/a" if fila["media"] is None else f"{fila['media']:.3f}"
        print(
            f"n={fila['n']} {fila['formulacion']} {fila['sampler']} {fila['metodo']} "
            f"criterio={fila['criterio']} shots={fila['lecturas']} backend={fila['backend']} "
            f"factibles={fila['factibles']}/{fila['N']} wilson={intervalo} "
            f"media={media} sd={sd} optimas={fila['optimas']}/{fila['N']}"
        )


if __name__ == "__main__":
    main(sys.argv)
