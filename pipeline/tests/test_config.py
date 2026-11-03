import pytest

from rutas_atm.config import Configuracion, ErrorDeConfiguracion, cargar_env


def test_valores_por_defecto(monkeypatch):
    for var in ("RUTAS_SAMPLER", "RUTAS_NUM_READS", "RUTAS_SEMILLA"):
        monkeypatch.delenv(var, raising=False)
    cfg = Configuracion.desde_entorno()
    assert cfg.sampler == "simulado" and cfg.num_reads == 200 and cfg.semilla == 42


@pytest.mark.parametrize("var,valor", [("RUTAS_SAMPLER", "gpu"), ("RUTAS_NUM_READS", "cien"), ("RUTAS_NUM_READS", "0")])
def test_valores_invalidos(monkeypatch, var, valor):
    monkeypatch.setenv(var, valor)
    with pytest.raises(ErrorDeConfiguracion):
        Configuracion.desde_entorno()


def test_env_no_pisa_variables_existentes(monkeypatch, tmp_path):
    archivo = tmp_path / ".env"
    archivo.write_text("# comentario\nRUTAS_SAMPLER=qpu\nRUTAS_NUM_READS=50\n", encoding="utf-8")
    monkeypatch.setenv("RUTAS_SAMPLER", "simulado")
    monkeypatch.delenv("RUTAS_NUM_READS", raising=False)
    assert cargar_env(archivo) == ["RUTAS_NUM_READS"]
    cfg = Configuracion.desde_entorno()
    assert cfg.sampler == "simulado" and cfg.num_reads == 50
