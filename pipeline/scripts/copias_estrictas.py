"""Copia estricta de un lote ya cerrado. No modifica el .pkl ni el .json original.

Lee cada .pkl de salidas/crudos, recalcula factible con el criterio estricto y
escribe salidas/<nombre>_estricto.json. Si esa copia ya existe, se detiene.
"""

import sys
from pathlib import Path

import numpy as np

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from rutas_atm.conversor_resultados import ArchivoInvalido, convertir, escribir  # noqa: E402
from rutas_atm.experimento import LoteCrudo, cargar_crudos  # noqa: E402
from rutas_atm.formulacion_tsp import construir_modelo, decodificar, es_permutacion, factible_estricto  # noqa: E402

CRUDOS = RAIZ / "salidas" / "crudos"
SALIDAS = RAIZ / "salidas"


def aplicar_criterio(lote: LoteCrudo) -> list[tuple[int, bool, bool]]:
    """Recalcula el flag en memoria. Devuelve (id, flag_anterior, flag_nuevo)."""
    distancias = np.array(lote.instancia.distancias, dtype=float)
    modelos = {}
    cambios = []
    for corrida in lote.corridas:
        modelo = modelos.get(corrida.formulacion)
        if modelo is None:
            modelo = construir_modelo(corrida.formulacion, distancias)
            modelos[corrida.formulacion] = modelo
        secuencia, _ = decodificar(modelo, corrida.bits)
        nuevo = factible_estricto(modelo, corrida.bits) and es_permutacion(secuencia, modelo.n)
        cambios.append((corrida.id_corrida, corrida.factible, nuevo))
        corrida.secuencia = secuencia
        corrida.factible = nuevo
        corrida.parametros = {**corrida.parametros, "criterio_factibilidad": "estricto"}
    return cambios


def destino_de(pkl: Path) -> Path:
    return SALIDAS / f"{pkl.stem}_estricto.json"


def main() -> None:
    origenes = sorted(CRUDOS.glob("*.pkl"))
    if not origenes:
        raise SystemExit(f"no hay .pkl en {CRUDOS}")
    ocupados = [destino_de(pkl) for pkl in origenes if destino_de(pkl).exists()]
    if ocupados:
        raise SystemExit("la copia ya existe; no se sobrescribe: " + ", ".join(str(p) for p in ocupados))
    for pkl in origenes:
        lote = cargar_crudos(pkl)
        cambios = aplicar_criterio(lote)
        doc = convertir(lote)
        try:
            escribir(doc, destino_de(pkl))
        except ArchivoInvalido as exc:
            raise SystemExit(f"{pkl.name}: {exc}") from exc
        vueltas = [c for c in cambios if c[1] != c[2]]
        print(f"{destino_de(pkl).name}: {len(vueltas)} flags cambian de {len(cambios)}")
        for id_corrida, antes, despues in vueltas:
            print(f"  id {id_corrida}: {antes} -> {despues}")


if __name__ == "__main__":
    main()
