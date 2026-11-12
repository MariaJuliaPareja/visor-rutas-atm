import importlib.util
import json
from pathlib import Path

RUTA = Path(__file__).resolve().parents[1] / "scripts" / "resumen_celdas.py"
spec = importlib.util.spec_from_file_location("resumen_celdas", RUTA)
resumen = importlib.util.module_from_spec(spec)
spec.loader.exec_module(resumen)


def _doc(criterio, semilla, factible=True):
    return {
        "instancia": {
            "cajeros": [{}, {}, {}],
            "linea_base": {"dist_optima": 1.0},
        },
        "corridas": [{
            "formulacion": "QUBO",
            "sampler": "ibm",
            "parametros": {
                "semilla": semilla,
                "shots": 200,
                "backend": "ibm_fez",
                "metodo_angulos": "optimizado_local",
                **({} if criterio is None else {"criterio_factibilidad": criterio}),
            },
            "ruta": {"factible": factible, "secuencia": [0, 1, 2]},
            "metricas": {"distancia_total": 1.0},
        }],
    }


def test_ignora_el_original_cuando_existe_la_copia(tmp_path):
    (tmp_path / "lote.json").write_text("{}", encoding="utf-8")
    (tmp_path / "lote_estricto.json").write_text("{}", encoding="utf-8")
    (tmp_path / "solo.json").write_text("{}", encoding="utf-8")
    elegidos, ignorados = resumen.archivos_a_leer(tmp_path)
    assert [p.name for p in elegidos] == ["lote_estricto.json", "solo.json"]
    assert [p.name for p in ignorados] == ["lote.json"]


def test_no_mezcla_criterios(tmp_path):
    laxo = tmp_path / "a.json"
    estricto = tmp_path / "b_estricto.json"
    laxo.write_text(json.dumps(_doc(None, 1)), encoding="utf-8")
    estricto.write_text(json.dumps(_doc("estricto", 2)), encoding="utf-8")
    documentos, _ = resumen.cargar(tmp_path)
    celdas, _ = resumen.agrupar(documentos)
    criterios = {clave[-1] for clave in celdas}
    assert criterios == {"laxo", "estricto"}
    assert all(len(filas) == 1 for filas in celdas.values())
