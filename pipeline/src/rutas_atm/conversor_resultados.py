"""CMP-05 Conversor de resultados: transforma el lote crudo (.pkl) en el archivo de intercambio .json.

El documento se valida contra el esquema y las reglas entre entidades antes de escribirse (RNF08, RNF12).
"""

import json
from pathlib import Path

from . import VERSION_ESQUEMA
from .experimento import LoteCrudo
from .validacion import validar


class ArchivoInvalido(ValueError):
    """El documento generado no cumple el contrato; no se escribe."""


def convertir(lote: LoteCrudo) -> dict:
    inst = lote.instancia
    etiquetas = getattr(inst, "etiquetas", None)  # los .pkl anteriores no tienen estos campos
    tiempos = getattr(inst, "tiempos", None)
    fuente = getattr(inst, "fuente", None)
    doc = {
        "version_esquema": VERSION_ESQUEMA,
        "fecha_generacion": lote.fecha,
        "instancia": {
            "id_instancia": inst.id_instancia,
            "tipo_instancia": inst.tipo,
            "cajeros": [_cajero(i, lat, lon, etiquetas[i] if etiquetas else None)
                        for i, (lat, lon) in enumerate(inst.coordenadas)],
            "matriz_distancias": {
                "unidad": "km",
                "metrica": getattr(inst, "metrica", "linea_recta"),  # .pkl anteriores no la tienen
                "distancias": [[round(float(x), 3) for x in fila] for fila in inst.distancias],
            },
            "linea_base": {"dist_optima": round(lote.dist_optima, 3), "ruta": lote.ruta_optima},
        },
        "corridas": [{
            "id_corrida": c.id_corrida,
            "formulacion": c.formulacion,
            "sampler": c.sampler,
            "parametros": c.parametros,
            "ruta": {"factible": c.factible, "secuencia": c.secuencia},
            "metricas": {
                "distancia_total": round(c.distancia_total, 3),
                "tiempo_anneal": c.tiempo_anneal_us,
                "chain_break_fraction": c.chain_break_fraction,
            },
        } for c in lote.corridas],
    }
    if tiempos is not None:
        doc["instancia"]["matriz_tiempos"] = {"unidad": "min",
                                              "tiempos": [[round(float(x), 2) for x in fila] for fila in tiempos]}
    if fuente:
        doc["instancia"]["fuente"] = {k: v for k, v in fuente.items() if v is not None}
    return doc


def _cajero(i: int, lat: float, lon: float, etiqueta: dict | None) -> dict:
    cajero = {"id_cajero": i, "latitud": lat, "longitud": lon}
    if etiqueta:
        cajero.update({k: v for k, v in etiqueta.items() if v is not None})
    return cajero


def escribir(doc: dict, ruta: Path) -> list[str]:
    """Valida el documento y lo escribe. Devuelve las advertencias; lanza ArchivoInvalido si hay errores."""
    errores, advertencias = validar(doc)
    if errores:
        raise ArchivoInvalido("; ".join(errores))
    ruta.parent.mkdir(parents=True, exist_ok=True)
    if ruta.exists():
        raise FileExistsError(f"{ruta} ya existe: el pipeline nunca sobrescribe un archivo de resultados")
    ruta.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    return advertencias
