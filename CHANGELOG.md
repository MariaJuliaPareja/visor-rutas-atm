# Registro de cambios

## Ayuda contextual del visor

### Visor web
- El encabezado abre un glosario con búsqueda. Los términos técnicos de la comparación, la tabla de corridas, el detalle y la leyenda del mapa muestran su definición al pasar el cursor, al enfocarlos o al tocarlos.
- El esquema del archivo de intercambio y la validación no cambian.

## Factibilidad estricta

### Pipeline (Python)
- `factible` es verdadero solo si la cadena cumple las restricciones exactamente-uno de la formulación y la secuencia decodificada es una permutación. Los lotes nuevos guardan `parametros.criterio_factibilidad = "estricto"`.
- Los lotes ya escritos no se modifican. `scripts/copias_estrictas.py` genera `*_estricto.json` desde el `.pkl`.
- `scripts/resumen_celdas.py` no mezcla criterios y, si existe la copia estricta, ignora el JSON laxo original.
- Esquema 1.3: el sampler admite `aleatorio`. Flags `--formulaciones`, `--angulos-gps`, `--angulos-qubo`, `--shots`, `--backend` y `--semilla-base`. La semilla de la instancia no cambia con `--semilla-base`. `--angulos-gps optimizado` con IBM se rechaza antes de muestrear.

### Visor web
- La validación solo rechaza `factible: true` cuando la secuencia no es una permutación. `factible: false` sigue siendo válido aunque la secuencia sí lo sea.

### Contrato
- La descripción del campo `factible` pasa a ser la factibilidad estricta de la formulación, no solo la permutación de la secuencia.

## v0.9.0 · Hardware cuántico real, cajeros reales y resumen para gerencia

### Pipeline (Python)
- Ejecución con QAOA en IBM Quantum (`--sampler ibm`, `--probar-ibm`), con ángulos elegidos en local y un solo job por corrida (DEC-08). D-Wave Leap no da servicio desde Perú (INC-08).
- Distancias y tiempos de manejo por calles con OSRM (`--distancia vial`, DEC-07).
- Cajeros BBVA reales de Arequipa desde OpenStreetMap (`--descargar-cajeros`, `--fuente osm`), con base de operaciones configurable (DEC-09).

### Visor web
- Rutas trazadas por las calles de OpenStreetMap.
- Resumen para gerencia: ahorro en soles, litros de diésel, km, minutos y CO₂ frente a la ruta habitual, también en la primera página del PDF. Supuestos editables y guardados en IndexedDB.
- El historial conserva tiempos de manejo y fuente de los cajeros (INC-09).
- Rediseño: tinta, papel y óxido, IBM Plex instalada en el proyecto, tablas compactas.

### Contrato
- Esquema 1.2: sampler `ibm`, métrica de distancias, tiempos de manejo, nombre y rol de cada punto y fuente de las ubicaciones. Migración desde 1.1 sin cambios de datos.

## v0.8.0 · Práctica 08: implementación e integración

### Pipeline (Python)
- Un módulo por componente: preparación de datos (CMP-01), formulación TSP GPS y QUBO (CMP-02), cliente D-Wave (CMP-03), línea base Held-Karp (CMP-04) y conversor de resultados (CMP-05).
- Ejecución en D-Wave Leap (`--sampler qpu`) y verificación de la conexión sin usar el QPU (`--probar-leap`); recocido simulado para desarrollo.
- Lote crudo `.pkl` guardado tras cada corrida y regeneración del `.json` con `--convertir`.

### Visor web (React + Leaflet)
- Carga y validación en seis pasos con el mismo esquema que el pipeline (CMP-06).
- Métricas con rutas infactibles marcadas y excluidas del resumen (CMP-07).
- Mapa con ruta óptima y ruta seleccionada, y detalle de corrida (CMP-08).
- Reporte consolidado en PDF (CMP-09).
- Historial de lotes en IndexedDB (persistencia NoSQL local).

### Contrato
- Esquema del archivo de intercambio 1.1, con migración desde la versión 1.0.
