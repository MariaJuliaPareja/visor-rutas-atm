"""CMP-05 Conversor de resultados: arma el archivo de intercambio .json y lo valida antes de escribirlo."""

import json
from datetime import datetime, timezone
from pathlib import Path

from . import VERSION_ESQUEMA
from .instancia import Instancia
from .validacion import validar


class ArchivoInvalido(ValueError):
    """El documento generado no cumple el contrato; no se escribe."""


def documento_intercambio(instancia: Instancia, dist_optima: float, ruta_optima: list,
                          corridas: list[dict]) -> dict:
    return {
        "version_esquema": VERSION_ESQUEMA,
        "fecha_generacion": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "instancia": {
            "id_instancia": instancia.id_instancia,
            "tipo_instancia": instancia.tipo,
            "cajeros": [{"id_cajero": i, "latitud": lat, "longitud": lon}
                        for i, (lat, lon) in enumerate(instancia.coordenadas)],
            "matriz_distancias": {
                "unidad": "km",
                "distancias": [[round(float(x), 3) for x in fila] for fila in instancia.distancias],
            },
            "linea_base": {"dist_optima": round(dist_optima, 3), "ruta": ruta_optima},
        },
        "corridas": corridas,
    }


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
