import numpy as np

from rutas_atm.cli import main
from rutas_atm.cliente_dwave import muestrear_aleatorio
from rutas_atm.config import Configuracion
from rutas_atm.conversor_resultados import convertir
from rutas_atm.experimento import ejecutar_experimento, nombres_csv
from rutas_atm.formulacion_tsp import construir_modelo
from rutas_atm.preparacion_datos import generar_instancia
from rutas_atm.validacion import validar


def test_aleatorio_repite_la_muestra_y_el_archivo_es_valido(tmp_path):
    modelo = construir_modelo("QUBO", generar_instancia(3, semilla=1).distancias)
    primera = muestrear_aleatorio(modelo, 15, 7)
    segunda = muestrear_aleatorio(modelo, 15, 7)
    assert primera.bits == segunda.bits and primera.energia == segunda.energia
    cfg = Configuracion("aleatorio", num_reads=8, semilla=3, directorio_salida=tmp_path, nivel_log="WARNING")
    lote = ejecutar_experimento(3, 1, cfg, ruta_pkl=tmp_path / "crudos" / "aleatorio.pkl")
    errores, _ = validar(convertir(lote))
    assert errores == []
    assert {c.sampler for c in lote.corridas} == {"aleatorio"}
    assert all(c.parametros["criterio_factibilidad"] == "estricto" for c in lote.corridas)


def test_angulos_gps_optimizado_con_ibm_se_rechaza(capsys):
    codigo = main(["--sampler", "ibm", "--angulos-gps", "optimizado", "--cajeros", "3", "--corridas", "1"])
    assert codigo == 2
    assert "cuota" in capsys.readouterr().err


def test_semilla_base_52_no_choca_con_las_replicas_42_a_51(tmp_path):
    nuevos = {ruta.name for ruta in nombres_csv(tmp_path, 4, ("GPS", "QUBO"), 10, 52)}
    existentes = {f"4_{form}_{replica}_{42 + replica}.csv" for form in ("GPS", "QUBO") for replica in range(10)}
    assert nuevos.isdisjoint(existentes)
    assert "4_QUBO_0_52.csv" in nuevos and "4_GPS_9_61.csv" in nuevos


def test_id_instancia_no_cambia_la_matriz():
    una = generar_instancia(4, semilla=42, id_instancia=1, metrica="linea_recta")
    otra = generar_instancia(4, semilla=42, id_instancia=4, metrica="linea_recta")
    assert una.id_instancia != otra.id_instancia
    assert np.array_equal(una.distancias, otra.distancias)
