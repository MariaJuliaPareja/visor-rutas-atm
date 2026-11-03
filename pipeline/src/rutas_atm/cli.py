"""Punto de entrada del pipeline: python -m rutas_atm --cajeros 5 --corridas 3

Para cada formulacion (GPS y QUBO) ejecuta el numero de corridas pedido sobre la misma instancia,
calcula la linea base exacta y escribe un unico archivo de intercambio .json.
"""

import argparse
import logging
import sys
import time
from datetime import datetime
from pathlib import Path

from .config import Configuracion, ErrorDeConfiguracion, cargar_env
from .conversor import ArchivoInvalido, documento_intercambio, escribir
from .formulaciones import construir_modelo, decodificar
from .held_karp import held_karp
from .instancia import distancia_ruta, generar_instancia
from .muestreo import ErrorDeMuestreo, muestrear
from .validacion import migrar, validar

log = logging.getLogger("rutas_atm")


def ejecutar(cajeros: int, corridas_por_formulacion: int, cfg: Configuracion, id_instancia: int = 1) -> dict:
    instancia = generar_instancia(cajeros, semilla=cfg.semilla, id_instancia=id_instancia)
    log.info("Instancia %d: %d cajeros (%s)", id_instancia, instancia.n, instancia.tipo)

    t0 = time.perf_counter()
    dist_optima, ruta_optima = held_karp(instancia.distancias)
    log.info("Held-Karp: %.3f km en %.1f ms, ruta %s", dist_optima, (time.perf_counter() - t0) * 1000, ruta_optima)

    corridas, id_corrida = [], 1
    for formulacion in ("GPS", "QUBO"):
        modelo = construir_modelo(formulacion, instancia.distancias)
        log.info("%s: %d variables binarias", formulacion, modelo.num_variables)
        for replica in range(corridas_por_formulacion):
            resultado = muestrear(modelo, cfg.sampler, cfg.num_reads, cfg.semilla + replica)
            secuencia, factible = decodificar(modelo, resultado.bits)
            corridas.append({
                "id_corrida": id_corrida,
                "formulacion": formulacion,
                "sampler": cfg.sampler,
                "parametros": {**resultado.parametros, "replica": replica, "num_variables": modelo.num_variables},
                "ruta": {"factible": factible, "secuencia": secuencia},
                "metricas": {
                    "distancia_total": round(distancia_ruta(secuencia, instancia.distancias), 3),
                    "tiempo_anneal": resultado.tiempo_anneal_us,
                    "chain_break_fraction": resultado.chain_break_fraction,
                },
            })
            log.info("  corrida %d (%s, replica %d): %s %s", id_corrida, formulacion, replica,
                     "factible" if factible else "INFACTIBLE", secuencia)
            id_corrida += 1
    return documento_intercambio(instancia, dist_optima, ruta_optima, corridas)


def _subcomando_validar(ruta: str) -> int:
    import json
    doc = migrar(json.loads(open(ruta, encoding="utf-8").read()))
    errores, advertencias = validar(doc)
    for a in advertencias:
        print(f"ADVERTENCIA: {a}")
    if errores:
        print("Archivo rechazado:")
        for e in errores:
            print(f"  - {e}")
        return 1
    print(f"Archivo valido (version {doc['version_esquema']})")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="rutas_atm", description=__doc__.splitlines()[0])
    parser.add_argument("--cajeros", type=int, default=5, help="numero de cajeros de la instancia (3 a 7 recomendado)")
    parser.add_argument("--corridas", type=int, default=3, help="corridas por formulacion")
    parser.add_argument("--instancia", type=int, default=1, help="identificador de la instancia")
    parser.add_argument("--validar", metavar="ARCHIVO", help="solo valida un archivo de intercambio existente")
    args = parser.parse_args(argv)

    cargar_env(Path(".env"))
    try:
        cfg = Configuracion.desde_entorno()
    except ErrorDeConfiguracion as exc:
        print(f"Error de configuracion: {exc}", file=sys.stderr)
        return 2
    logging.basicConfig(level=cfg.nivel_log, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    if args.validar:
        return _subcomando_validar(args.validar)

    try:
        doc = ejecutar(args.cajeros, args.corridas, cfg, args.instancia)
    except (ValueError, ErrorDeMuestreo) as exc:
        log.error("%s", exc)
        return 1

    marca = datetime.now().strftime("%Y%m%d-%H%M%S-%f")[:-3]
    ruta = cfg.directorio_salida / f"corridas_i{args.instancia}_n{args.cajeros}_{cfg.sampler}_{marca}.json"
    try:
        for advertencia in escribir(doc, ruta):
            log.warning("%s", advertencia)
    except (ArchivoInvalido, FileExistsError) as exc:
        log.error("No se escribio el archivo: %s", exc)
        return 1
    log.info("Archivo de intercambio escrito en %s", ruta)
    return 0


if __name__ == "__main__":
    sys.exit(main())
