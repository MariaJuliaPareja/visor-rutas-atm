import copy
import json
from pathlib import Path

import pytest

from rutas_atm import VERSION_ESQUEMA
from rutas_atm.config import Configuracion
from rutas_atm.conversor_resultados import ArchivoInvalido, convertir, escribir
from rutas_atm.experimento import ejecutar_experimento
from rutas_atm.validacion import migrar, validar

EJEMPLO = Path(__file__).resolve().parents[2] / "ejemplos" / "corridas_ejemplo.json"


@pytest.fixture(scope="module")
def documento():
    cfg = Configuracion("simulado", num_reads=20, semilla=42, directorio_salida=Path("."), nivel_log="WARNING")
    return convertir(ejecutar_experimento(cajeros=4, corridas_por_formulacion=2, cfg=cfg))


def test_documento_generado_es_valido(documento):
    errores, advertencias = validar(documento)
    assert errores == [] and advertencias == []


def test_ejemplo_del_repositorio_es_valido():
    errores, _ = validar(migrar(json.loads(EJEMPLO.read_text(encoding="utf-8"))))
    assert errores == []


@pytest.mark.parametrize("romper,fragmento", [
    (lambda d: d["corridas"][0].update(formulacion="GPU"), "formulacion"),
    (lambda d: d["instancia"]["matriz_distancias"]["distancias"][1].pop(), "matriz"),
    (lambda d: d["corridas"][0]["ruta"].update(secuencia=[0, 1, 7]), "inexistente"),
    (lambda d: d["corridas"][0]["ruta"].update(factible=not d["corridas"][0]["ruta"]["factible"]), "factible"),
    (lambda d: d["corridas"][0].update(sampler="qpu"), "tiempo_anneal"),
])
def test_rechazos(documento, romper, fragmento):
    roto = copy.deepcopy(documento)
    romper(roto)
    errores, _ = validar(roto)
    assert errores and any(fragmento in e for e in errores)


def test_advertencia_por_distancia_inconsistente(documento):
    alterado = copy.deepcopy(documento)
    alterado["corridas"][0]["metricas"]["distancia_total"] += 5
    errores, advertencias = validar(alterado)
    assert errores == [] and len(advertencias) == 1


def test_migracion_1_0_a_1_1(documento):
    viejo = copy.deepcopy(documento)
    viejo["version_esquema"] = "1.0"
    for c in viejo["corridas"]:
        del c["sampler"]
        c["metricas"]["tiempo_anneal"] = 20.0
    migrado = migrar(viejo)
    assert migrado["version_esquema"] == VERSION_ESQUEMA
    assert all(c["sampler"] == "qpu" for c in migrado["corridas"])


def test_version_desconocida(documento):
    with pytest.raises(ValueError):
        migrar({**copy.deepcopy(documento), "version_esquema": "0.9"})


def test_no_escribe_archivo_invalido_ni_sobrescribe(documento, tmp_path):
    roto = copy.deepcopy(documento)
    roto["corridas"][0]["formulacion"] = "GPU"
    with pytest.raises(ArchivoInvalido):
        escribir(roto, tmp_path / "x.json")
    assert not (tmp_path / "x.json").exists()
    escribir(documento, tmp_path / "y.json")
    with pytest.raises(FileExistsError):
        escribir(documento, tmp_path / "y.json")
