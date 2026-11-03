# Visor de Rutas ATM

Prototipo del Proyecto de Fin de Carrera *Optimización de rutas para el reabastecimiento de cajeros automáticos mediante computación cuántica híbrida* (Ingeniería de Sistemas, UCSM, 2026).

Compara dos formulaciones QUBO del problema del vendedor viajero, **GPS** (González-Bermejo et al., 2022) y **QUBO tradicional** (one-hot), resueltas por recocido, contra una línea base exacta (Held-Karp). Tiene dos subsistemas desacoplados por un único archivo de intercambio `.json`:

```
pipeline/  (Python)                    schema/                     web/  (React + Leaflet)
CMP-01 preparacion_datos.py            contrato compartido         CMP-06 carga/        validación
CMP-02 formulacion_tsp.py (GPS/QUBO)   (JSON Schema 2020-12)       CMP-07 metricas/     métricas
CMP-03 cliente_dwave.py (sim./QPU)                                 CMP-08 visualizacion/ mapa y detalle
CMP-04 linea_base.py (Held-Karp)                                   CMP-09 reportes/     reporte PDF
       experimento.py → lote crudo .pkl                            persistencia/        IndexedDB (NoSQL)
CMP-05 conversor_resultados.py → .json ──── archivo .json ───────→ (se carga en el navegador)
```

> Estado: incremento de la Práctica 08. Los datos se guardan como documentos (NoSQL): lote crudo `.pkl`, archivo de intercambio `.json` e historial del visor en IndexedDB. Ver `docs/modelo-datos-nosql.md`.

## Requisitos

| Herramienta | Versión probada |
|---|---|
| Python | 3.12 y 3.13 |
| Node.js | 22 |
| Cuenta de D-Wave Leap | Solo para `RUTAS_SAMPLER=qpu` |

## Instalación y ejecución

### 1. Pipeline

```bash
cd pipeline
python -m venv .venv
source .venv/bin/activate          # en fish: source .venv/bin/activate.fish
pip install -r requirements-dev.txt
cp .env.example .env               # ajusta los valores si hace falta

PYTHONPATH=src python -m rutas_atm --cajeros 5 --corridas 3
```

Escribe el lote crudo `salidas/crudos/corridas_i1_n5_simulado_<fecha>.pkl` (después de cada corrida) y el archivo de intercambio `salidas/corridas_i1_n5_simulado_<fecha>.json`. El `.json` se valida contra el esquema antes de escribirse y nunca se sobrescribe uno existente.

```bash
PYTHONPATH=src python -m rutas_atm --convertir salidas/crudos/<lote>.pkl   # regenera el .json desde el .pkl
PYTHONPATH=src python -m rutas_atm --validar salidas/<archivo>.json        # valida un .json existente
```

### 2. Visor web

```bash
cd web
npm ci
npm run dev        # http://localhost:5173
```

Carga el `.json` generado, o el de ejemplo en `ejemplos/corridas_ejemplo.json`. El archivo se procesa en el navegador; para dibujar las rutas por las calles, solo las coordenadas de los cajeros (sintéticas) se envían al servicio de rutas OSRM. Con `VITE_OSRM_URL=off` se dibujan en línea recta y nada sale del navegador. Cada archivo válido queda en el historial del navegador (IndexedDB) para reabrirlo sin volver a subirlo; **Exportar reporte** descarga un PDF con las mismas cifras de la pantalla.

### 3. Pruebas

```bash
cd pipeline && pytest -q && ruff check src tests
cd web && npm test && npm run build
```

Las mismas comprobaciones corren en GitHub Actions en cada *push* a `main` y en cada *pull request* (`.github/workflows/ci.yml`).

## Configuración

| Variable | Propósito | Valor por defecto |
|---|---|---|
| `RUTAS_SAMPLER` | `simulado` (local, sin costo) o `qpu` (D-Wave Leap) | `simulado` |
| `RUTAS_NUM_READS` | Lecturas por corrida | `200` |
| `RUTAS_SEMILLA` | Semilla de la instancia y del recocido simulado | `42` |
| `RUTAS_ANNEALING_TIME` | Microsegundos de recocido por lectura en el QPU | `20` |
| `RUTAS_DISTANCIA` | `linea_recta` (haversine) o `vial` (por calles de OpenStreetMap, OSRM) | `linea_recta` |
| `RUTAS_OSRM_URL` | Servidor OSRM para `vial` | `https://router.project-osrm.org` |
| `RUTAS_DIR_SALIDA` | Carpeta de los `.json` generados | `salidas` |
| `RUTAS_NIVEL_LOG` | Nivel de registro | `INFO` |
| `DWAVE_API_TOKEN` | Token de Leap, solo con `qpu` (mejor: `dwave config create`) | — |

Las variables del entorno tienen prioridad sobre `.env`. **El token nunca va en el código ni en el repositorio**: usa `dwave config create` o una variable de entorno.

### Ejecutar en D-Wave Leap

```bash
pip install -r requirements-qpu.txt
dwave config create                                      # guarda el token fuera del repositorio
PYTHONPATH=src python -m rutas_atm --probar-leap          # verifica token y solver, sin usar el QPU
PYTHONPATH=src python -m rutas_atm --sampler qpu --cajeros 4 --corridas 1
```

También puede ejecutarse desde GitHub Actions (**Ejecucion en D-Wave Leap**, solo a mano), con el token guardado como secreto. Cada corrida consume tiempo de QPU del plan de Leap (RNF04): empieza con instancias pequeñas. Guía completa: `docs/ejecucion-dwave-leap.md`.

## Estructura

```
schema/        contrato del archivo de intercambio (JSON Schema 2020-12), compartido
pipeline/      src/rutas_atm (un módulo por componente CMP-01 a CMP-05), tests/, requirements*.txt
web/src/       carga/, metricas/, visualizacion/, reportes/ (CMP-06 a CMP-09), persistencia/ (IndexedDB), pantallas/
ejemplos/      archivo de intercambio de ejemplo (datos sintéticos)
docs/          decisiones, integración, incidencias, modelo de datos NoSQL y evidencias
```

## Datos

Todas las instancias son **sintéticas**: coordenadas ficticias alrededor de Arequipa generadas con semilla fija. El proyecto no usa datos personales ni operativos de ninguna entidad bancaria (RNF06).

## Créditos

La construcción de las matrices QUBO (tradicional y GPS) reutiliza el código de la tesis de la autora, [gps-vs-qubo-tsp](https://github.com/MariaJuliaPareja/gps-vs-qubo-tsp), donde se validó contra fuerza bruta.

- González-Bermejo, S., Alonso-Linaje, G., & Atchade-Adelomou, P. (2022). GPS: A new TSP formulation for its generalizations type QUBO. *Mathematics, 10*(3), 416. https://doi.org/10.3390/math10030416
- Lucas, A. (2014). Ising formulations of many NP problems. *Frontiers in Physics, 2*, 5. https://doi.org/10.3389/fphy.2014.00005
