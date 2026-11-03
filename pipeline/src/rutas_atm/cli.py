"""Punto de entrada del pipeline de experimentacion.

  python -m rutas_atm --cajeros 5 --corridas 3     ejecuta el lote: .pkl crudo y .json de intercambio
  python -m rutas_atm --convertir LOTE.pkl         regenera el .json desde un .pkl del pipeline
  python -m rutas_atm --validar ARCHIVO.json       valida un archivo de intercambio
  python -m rutas_atm --probar-leap                verifica el token y el solver de D-Wave Leap (sin usar el QPU)
  python -m rutas_atm --sampler qpu ...            ejecuta en el QPU de D-Wave Leap (o RUTAS_SAMPLER=qpu)
  python -m rutas_atm --probar-ibm                 verifica la cuenta de IBM Quantum y lista backends (sin usar el QPU)
  python -m rutas_atm --sampler ibm ...            ejecuta QAOA en hardware de IBM Quantum (o RUTAS_SAMPLER=ibm)
  python -m rutas_atm --descargar-cajeros BBVA     descarga los cajeros de la entidad en Arequipa (OpenStreetMap)
  python -m rutas_atm --fuente osm ...             usa cajeros reales del catalogo (o RUTAS_FUENTE=osm)
  python -m rutas_atm --distancia vial ...         distancias por calles de OpenStreetMap (o RUTAS_DISTANCIA=vial)
"""

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

from .cliente_dwave import ErrorDeMuestreo, probar_conexion
from .config import Configuracion, ErrorDeConfiguracion, cargar_env
from .conversor_resultados import ArchivoInvalido, convertir, escribir
from .distancias_viales import ErrorDeDistancias
from .experimento import cargar_crudos, ejecutar_experimento
from .validacion import migrar, validar

log = logging.getLogger("rutas_atm")


def _validar(ruta: str) -> int:
    doc = migrar(json.loads(Path(ruta).read_text(encoding="utf-8")))
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


def _escribir_json(lote, ruta_json: Path) -> int:
    try:
        for advertencia in escribir(convertir(lote), ruta_json):
            log.warning("%s", advertencia)
    except (ArchivoInvalido, FileExistsError) as exc:
        log.error("No se escribio el archivo: %s", exc)
        return 1
    log.info("Archivo de intercambio escrito en %s", ruta_json)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="rutas_atm", description="Pipeline de experimentacion de rutas ATM")
    parser.add_argument("--cajeros", type=int, default=5, help="numero de cajeros de la instancia (3 a 7 recomendado)")
    parser.add_argument("--corridas", type=int, default=3, help="corridas por formulacion")
    parser.add_argument("--instancia", type=int, default=1, help="identificador de la instancia")
    parser.add_argument("--sampler", choices=("simulado", "qpu", "ibm"), help="sobrescribe RUTAS_SAMPLER")
    parser.add_argument("--fuente", choices=("sintetica", "osm"),
                        help="sobrescribe RUTAS_FUENTE (osm = cajeros reales del catalogo de OpenStreetMap)")
    parser.add_argument("--distancia", choices=("linea_recta", "vial"),
                        help="sobrescribe RUTAS_DISTANCIA (vial = por calles de OpenStreetMap)")
    grupo = parser.add_mutually_exclusive_group()
    grupo.add_argument("--probar-leap", action="store_true", help="verifica la conexion con Leap sin usar el QPU")
    grupo.add_argument("--probar-ibm", action="store_true", help="verifica la cuenta de IBM Quantum sin usar el QPU")
    grupo.add_argument("--descargar-cajeros", metavar="ENTIDAD", nargs="?", const="BBVA",
                       help="descarga de OpenStreetMap los cajeros de la entidad en Arequipa (por defecto BBVA)")
    grupo.add_argument("--validar", metavar="ARCHIVO.json", help="solo valida un archivo de intercambio")
    grupo.add_argument("--convertir", metavar="LOTE.pkl", help="regenera el .json desde un .pkl del pipeline")
    args = parser.parse_args(argv)

    cargar_env(Path(".env"))
    try:
        cfg = Configuracion.desde_entorno()
        if args.sampler:
            cfg = cfg.con_sampler(args.sampler)
        if args.distancia:
            cfg = cfg.con_distancia(args.distancia)
        if args.fuente:
            cfg = cfg.con_fuente(args.fuente)
    except ErrorDeConfiguracion as exc:
        print(f"Error de configuracion: {exc}", file=sys.stderr)
        return 2
    logging.basicConfig(level=cfg.nivel_log, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    for ruidoso in ("qiskit", "qiskit_ibm_runtime", "stevedore"):  # sus INFO ocultan el progreso del lote
        logging.getLogger(ruidoso).setLevel(max(logging.WARNING, logging.getLevelName(cfg.nivel_log)))

    if args.validar:
        return _validar(args.validar)
    if args.probar_leap:
        try:
            info = probar_conexion()
        except ErrorDeMuestreo as exc:
            log.error("%s", exc)
            return 1
        print(f"Conexion con D-Wave Leap correcta. Solver: {info['solver']} ({info['topologia']}, "
              f"{info['qubits_activos']} qubits activos). No se uso tiempo de QPU.")
        return 0
    if args.descargar_cajeros:
        from .cajeros_osm import ErrorDeCatalogo, descargar, guardar_catalogo
        try:
            catalogo = descargar(args.descargar_cajeros)
        except ErrorDeCatalogo as exc:
            log.error("%s", exc)
            return 1
        guardar_catalogo(catalogo, cfg.catalogo)
        print(f"{len(catalogo['cajeros'])} cajeros de {catalogo['entidad']} guardados en {cfg.catalogo}")
        print(catalogo["atribucion"])
        return 0
    if args.probar_ibm:
        from .cliente_ibm import probar_conexion_ibm
        try:
            info = probar_conexion_ibm()
        except ErrorDeMuestreo as exc:
            log.error("%s", exc)
            return 1
        print("Conexion con IBM Quantum correcta. Backends: " + ", ".join(info["backends"]))
        print(f"Menos ocupado ahora: {info['menos_ocupado']}. No se uso tiempo de QPU.")
        return 0
    if args.convertir:
        origen = Path(args.convertir)
        try:
            lote = cargar_crudos(origen)
        except (OSError, TypeError) as exc:
            log.error("No se pudo abrir el lote: %s", exc)
            return 1
        return _escribir_json(lote, cfg.directorio_salida / f"{origen.stem}.json")

    marca = datetime.now().strftime("%Y%m%d-%H%M%S-%f")[:-3]
    nombre = f"corridas_i{args.instancia}_n{args.cajeros}_{cfg.sampler}_{marca}"
    ruta_pkl = cfg.directorio_salida / "crudos" / f"{nombre}.pkl"
    try:
        lote = ejecutar_experimento(args.cajeros, args.corridas, cfg, args.instancia, ruta_pkl)
    except (ErrorDeDistancias, ErrorDeCatalogo, ValueError, ErrorDeMuestreo) as exc:
        log.error("%s", exc)
        return 1
    log.info("Lote crudo guardado en %s", ruta_pkl)
    return _escribir_json(lote, cfg.directorio_salida / f"{nombre}.json")


if __name__ == "__main__":
    sys.exit(main())
