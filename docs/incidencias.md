# Registro de incidencias técnicas

| ID | Componente | Síntoma | Causa | Solución | Evidencia |
|---|---|---|---|---|---|
| INC-01 | CMP-04 → CMP-05 | El conversor rechazó el primer archivo: `instancia/linea_base/ruta/1: np.int64(2) is not of type 'integer'` | Held-Karp devolvía `numpy.int64`; JSON Schema exige enteros de Python | Conversión explícita a `int` en `held_karp.py` | Prueba `test_held_karp_devuelve_enteros_de_python` |
| INC-02 | CMP-05 | Dos ejecuciones en el mismo segundo producían el mismo nombre de archivo y la segunda se negaba a sobrescribir | Marca de tiempo con resolución de segundos | Nombre con milisegundos; se mantiene la regla de no sobrescribir | `escribir()` lanza `FileExistsError`; prueba `test_no_escribe_archivo_invalido_ni_sobrescribe` |
| INC-03 | CMP-08 | El panel de detalle tapaba la mitad de los cajeros, incluido un cajero no visitado | Panel con posición absoluta sobre el mapa | Panel al lado del mapa y reencuadre con `ResizeObserver` (DEC-05) | `docs/evidencias/05_detalle_infactible.png` |
| INC-04 | CMP-06 | Los errores del esquema aparecían en inglés (`must be equal to one of the allowed values`) | Mensajes por defecto de Ajv | Traducción de los mensajes por palabra clave, con el valor recibido y los permitidos | `docs/evidencias/02_rechazo_estructura.png` |
| INC-05 | CMP-03 | La primera prueba de decodificación QUBO esperaba "infactible" para un estado con dos cajeros en una posición, y la ruta resultó válida | La regla de factibilidad no estaba precisada | DEC-03 y prueba `test_factibilidad_se_evalua_sobre_la_ruta_decodificada` | `pipeline/tests/test_formulaciones.py` |
