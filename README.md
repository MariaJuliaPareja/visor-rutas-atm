# Visor de Rutas ATM

Prototipo del Proyecto de Fin de Carrera *Optimización de rutas para el reabastecimiento de cajeros automáticos mediante computación cuántica híbrida* (Ingeniería de Sistemas, UCSM, 2026).

Compara dos formulaciones QUBO del problema del vendedor viajero, **GPS** (González-Bermejo et al., 2022) y **QUBO tradicional** (one-hot), resueltas por recocido, contra una línea base exacta (Held-Karp). Tiene dos subsistemas desacoplados por un único archivo de intercambio `.json`:

```
pipeline/  (Python)             schema/                      web/  (React + Leaflet)
CMP-01 instancia                esquema_archivo_             CMP-06 carga y validación
CMP-02 formulaciones GPS/QUBO   intercambio.schema.json      CMP-07 métricas
CMP-03 recocido (simulado/QPU)  ← contrato compartido →      CMP-08 mapa y detalle
CMP-04 Held-Karp
CMP-05 conversor → .json  ─────────── archivo .json ──────→  (se carga en el navegador)
```

> Estado: incremento de la Práctica 08. La exportación del reporte (RF05, CMP-09) queda para el siguiente incremento.

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

Escribe `salidas/corridas_i1_n5_simulado_<fecha>.json`. El archivo se valida contra el esquema antes de escribirse y nunca se sobrescribe uno existente.

Para validar un archivo ya generado:

```bash
PYTHONPATH=src python -m rutas_atm --validar salidas/<archivo>.json
```

### 2. Visor web

```bash
cd web
npm ci
npm run dev        # http://localhost:5173
```

Carga el `.json` generado, o el de ejemplo en `ejemplos/corridas_ejemplo.json`. El archivo se procesa en el navegador y no se envía a ningún servidor.

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
| `RUTAS_DIR_SALIDA` | Carpeta de los `.json` generados | `salidas` |
| `RUTAS_NIVEL_LOG` | Nivel de registro | `INFO` |
| `DWAVE_API_TOKEN` | Token de Leap, solo con `qpu` | — |

Las variables del entorno tienen prioridad sobre `.env`. **El token nunca va en el código ni en el repositorio**: usa `dwave config create` o una variable de entorno.

### Ejecutar en el QPU real

```bash
pip install -r requirements-qpu.txt
dwave config create                # guarda el token fuera del repositorio
RUTAS_SAMPLER=qpu RUTAS_NUM_READS=100 PYTHONPATH=src python -m rutas_atm --cajeros 4 --corridas 1
```

Cada corrida consume minutos del plan gratuito de Leap (RNF04): empieza con instancias pequeñas.

## Estructura

```
schema/        contrato del archivo de intercambio (JSON Schema 2020-12), compartido
pipeline/      src/rutas_atm (CMP-01 a CMP-05), tests/, requirements*.txt
web/           src/lib (validación y métricas), src/componentes (pantallas), pruebas con Vitest
ejemplos/      archivo de intercambio de ejemplo (datos sintéticos)
docs/          decisiones, integración, incidencias y evidencias
```

## Datos

Todas las instancias son **sintéticas**: coordenadas ficticias alrededor de Arequipa generadas con semilla fija. El proyecto no usa datos personales ni operativos de ninguna entidad bancaria (RNF06).

## Créditos

La construcción de las matrices QUBO (tradicional y GPS) reutiliza el código de la tesis de la autora, [gps-vs-qubo-tsp](https://github.com/MariaJuliaPareja/gps-vs-qubo-tsp), donde se validó contra fuerza bruta.

- González-Bermejo, S., Alonso-Linaje, G., & Atchade-Adelomou, P. (2022). GPS: A new TSP formulation for its generalizations type QUBO. *Mathematics, 10*(3), 416. https://doi.org/10.3390/math10030416
- Lucas, A. (2014). Ising formulations of many NP problems. *Frontiers in Physics, 2*, 5. https://doi.org/10.3389/fphy.2014.00005
