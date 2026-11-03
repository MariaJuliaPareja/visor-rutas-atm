# Registro de incidencias técnicas

| ID | Componente | Síntoma | Causa | Solución | Evidencia |
|---|---|---|---|---|---|
| INC-01 | CMP-04 → CMP-05 | El conversor rechazó el primer archivo: `instancia/linea_base/ruta/1: np.int64(2) is not of type 'integer'` | Held-Karp devolvía `numpy.int64`; JSON Schema exige enteros | Conversión explícita a `int` en `linea_base.py` | Prueba `test_held_karp_devuelve_enteros_de_python` |
| INC-02 | CMP-05 | Dos ejecuciones en el mismo segundo producían el mismo nombre de archivo y la segunda se negaba a escribir | Marca de tiempo con resolución de segundos | Nombre con milisegundos; se mantiene la regla de no sobrescribir | Prueba `test_no_escribe_archivo_invalido_ni_sobrescribe` |
| INC-03 | CMP-08 | El panel de detalle tapaba la mitad de los cajeros, incluido uno no visitado | Panel sobre el mapa sin ajustar el encuadre | Reencuadre del mapa con el ancho del panel (DEC-06) | `evidencias/05_detalle_infactible.png` |
| INC-04 | CMP-06 | Los errores del esquema aparecían en inglés (`must be equal to one of the allowed values`) | Mensajes por defecto de Ajv | Traducción por palabra clave, con el valor recibido y los permitidos | `evidencias/02_rechazo_estructura.png` |
| INC-05 | CMP-02 | Una prueba esperaba "infactible" para un estado con dos cajeros en una posición, y la ruta decodificada era válida | La regla de factibilidad no estaba precisada | DEC-03 y prueba `test_factibilidad_se_evalua_sobre_la_ruta_decodificada` | `pipeline/tests/test_formulacion_tsp.py` |
| INC-06 | CMP-09 | La construcción del visor advertía un paquete de casi 900 kB | jsPDF incluido en la carga inicial | Carga diferida del generador de reportes al pulsar **Exportar reporte** | Salida de `npm run build` sin advertencias |
| INC-07 | PAN-03 | Un clic sobre "No comparable" abría la nota pero no seleccionaba la corrida | `stopPropagation` en la nota | Se quitó; el clic abre la nota y selecciona la fila | `evidencias/05_detalle_infactible.png` |
