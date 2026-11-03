"""Validacion en dos niveles del archivo de intercambio y migracion entre versiones del esquema.

Nivel 1: estructura, contra el esquema JSON compartido con el visor (schema/).
Nivel 2: reglas entre entidades que JSON Schema no puede expresar.
El visor (CMP-06) aplica las mismas reglas en JavaScript al cargar el archivo.
"""

import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

from . import VERSION_ESQUEMA

RUTA_ESQUEMA = Path(__file__).resolve().parents[3] / "schema" / "esquema_archivo_intercambio.schema.json"


def _1_0_a_1_1(doc: dict) -> dict:
    """La version 1.0 asumia QPU: se marca el sampler de cada corrida como 'qpu'."""
    for corrida in doc.get("corridas", []):
        corrida.setdefault("sampler", "qpu")
    doc["version_esquema"] = "1.1"
    return doc


def _1_1_a_1_2(doc: dict) -> dict:
    """La 1.2 solo agrega valores opcionales (sampler ibm, metrica de distancias): no cambia los datos."""
    doc["version_esquema"] = "1.2"
    return doc


MIGRACIONES = {"1.0": ("1.1", _1_0_a_1_1), "1.1": ("1.2", _1_1_a_1_2)}


def migrar(doc: dict) -> dict:
    version = doc.get("version_esquema")
    while version != VERSION_ESQUEMA:
        if version not in MIGRACIONES:
            raise ValueError(f"No existe migracion desde la version {version!r}")
        version, funcion = MIGRACIONES[version]
        doc = funcion(doc)
    return doc


def validar_estructura(doc: dict) -> list[str]:
    esquema = json.loads(RUTA_ESQUEMA.read_text(encoding="utf-8"))
    validador = Draft202012Validator(esquema, format_checker=FormatChecker())
    return [f"{'/'.join(map(str, e.absolute_path)) or '(raiz)'}: {e.message}"
            for e in sorted(validador.iter_errors(doc), key=lambda e: list(e.absolute_path))]


def validar_reglas(doc: dict, tolerancia_km: float = 0.01) -> tuple[list[str], list[str]]:
    """Devuelve (errores, advertencias). Las advertencias no bloquean la carga."""
    errores, advertencias = [], []
    inst = doc["instancia"]
    n = len(inst["cajeros"])

    if [c["id_cajero"] for c in inst["cajeros"]] != list(range(n)):
        errores.append("id_cajero debe ser consecutivo de 0 a n-1 y en orden")

    d = inst["matriz_distancias"]["distancias"]
    if len(d) != n or any(len(fila) != n for fila in d):
        errores.append(f"la matriz de distancias debe ser de {n} x {n}")
        return errores, advertencias
    if any(d[i][i] != 0 for i in range(n)):
        errores.append("la diagonal de la matriz de distancias debe ser 0")

    if sorted(inst["linea_base"]["ruta"]) != list(range(n)):
        errores.append("la ruta de la linea base debe visitar cada cajero exactamente una vez")

    ids = [c["id_corrida"] for c in doc["corridas"]]
    if len(ids) != len(set(ids)):
        errores.append("id_corrida debe ser unico")

    for c in doc["corridas"]:
        sec = c["ruta"]["secuencia"]
        if any(i >= n for i in sec):
            errores.append(f"corrida {c['id_corrida']}: referencia a un cajero inexistente")
            continue
        if c["ruta"]["factible"] != (sorted(sec) == list(range(n))):
            errores.append(f"corrida {c['id_corrida']}: 'factible' no coincide con la secuencia")
        if c["sampler"] == "qpu" and c["metricas"]["tiempo_anneal"] is None:
            errores.append(f"corrida {c['id_corrida']}: una corrida en QPU debe registrar tiempo_anneal")
        recalculada = sum(d[sec[k]][sec[(k + 1) % len(sec)]] for k in range(len(sec))) if len(sec) > 1 else 0
        if abs(recalculada - c["metricas"]["distancia_total"]) > tolerancia_km:
            advertencias.append(f"corrida {c['id_corrida']}: la distancia almacenada no coincide con la recalculada")
    return errores, advertencias


def validar(doc: dict) -> tuple[list[str], list[str]]:
    errores = validar_estructura(doc)
    if errores:
        return errores, []
    return validar_reglas(doc)
