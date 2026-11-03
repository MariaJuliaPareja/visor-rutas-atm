import json
import pickle

import pytest

from rutas_atm.cli import main
from rutas_atm.config import Configuracion
from rutas_atm.conversor_resultados import convertir
from rutas_atm.experimento import cargar_crudos, ejecutar_experimento


def test_lote_crudo_se_guarda_y_se_reconvierte_igual(tmp_path):
    cfg = Configuracion("simulado", num_reads=10, semilla=7, directorio_salida=tmp_path, nivel_log="WARNING")
    ruta = tmp_path / "crudos" / "lote.pkl"
    lote = ejecutar_experimento(4, 2, cfg, ruta_pkl=ruta)
    assert ruta.exists() and not ruta.with_suffix(".pkl.tmp").exists()
    recargado = cargar_crudos(ruta)
    assert len(recargado.corridas) == 4
    assert convertir(recargado) == convertir(lote)  # el .json se puede regenerar desde el .pkl


def test_rechaza_pkl_ajeno(tmp_path):
    ajeno = tmp_path / "ajeno.pkl"
    ajeno.write_bytes(pickle.dumps({"no": "es un lote"}))
    with pytest.raises(TypeError):
        cargar_crudos(ajeno)


def test_cli_genera_pkl_y_json_y_luego_convierte(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("RUTAS_DIR_SALIDA", str(tmp_path / "salidas"))
    monkeypatch.setenv("RUTAS_NUM_READS", "10")
    assert main(["--cajeros", "4", "--corridas", "1"]) == 0
    pkl = next((tmp_path / "salidas" / "crudos").glob("*.pkl"))
    original = next((tmp_path / "salidas").glob("*.json"))
    original.rename(original.with_suffix(".bak"))
    assert main(["--convertir", str(pkl)]) == 0
    regenerado = tmp_path / "salidas" / f"{pkl.stem}.json"
    assert json.loads(regenerado.read_text()) == json.loads(original.with_suffix(".bak").read_text())
