# Registro de cambios

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
