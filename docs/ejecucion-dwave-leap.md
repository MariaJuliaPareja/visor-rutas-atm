# Ejecución en D-Wave Leap

El pipeline envía los modelos GPS y QUBO al QPU de D-Wave mediante el Ocean SDK (DA-002). Cada lote consume tiempo de QPU del plan de Leap (RNF04), así que conviene empezar con instancias de 3 o 4 cajeros.

## 1. Obtener el token

1. Inicia sesión en Leap: https://cloud.dwavesys.com/leap/
2. Copia el **API Token** del panel principal.
3. El token **nunca** se escribe en el código, en `.env.example` ni en un commit.

## 2. Opción A: ejecutar en tu computadora

```bash
cd pipeline
source .venv/bin/activate            # en fish: source .venv/bin/activate.fish
pip install -r requirements-qpu.txt
dwave config create                  # pega el token cuando lo pida; queda fuera del repositorio

PYTHONPATH=src python -m rutas_atm --probar-leap
# Conexion con D-Wave Leap correcta. Solver: Advantage... No se uso tiempo de QPU.

PYTHONPATH=src python -m rutas_atm --sampler qpu --cajeros 4 --corridas 1
```

En lugar de `dwave config create` puedes exportar `DWAVE_API_TOKEN` en la terminal de esa sesión.

## 3. Opción B: ejecutar desde GitHub Actions

1. En el repositorio: **Settings → Environments → New environment**, con el nombre `dwave-leap`.
2. Dentro de ese ambiente, agrega el secreto **`DWAVE_API_TOKEN`** con tu token.
3. **Actions → Ejecucion en D-Wave Leap → Run workflow**, con los cajeros, las corridas y las lecturas.
4. Al terminar, descarga el artefacto **resultados-dwave-leap**: el `.json` se carga directamente en el visor.

El flujo verifica la conexión, ejecuta el lote, valida el archivo y guarda el `.json` y el `.pkl` como artefacto. Solo se ejecuta a mano, nunca en cada *push*.

## Qué registra cada corrida en el QPU

| Campo | Origen | Uso |
|---|---|---|
| `metricas.tiempo_anneal` | `qpu_anneal_time_per_sample` (µs) | Métrica del diccionario de datos |
| `metricas.chain_break_fraction` | Muestra de menor energía | Métrica del diccionario de datos |
| `parametros.solver` | Solver asignado por Leap | Trazabilidad del hardware usado |
| `parametros.problem_id` | Identificador del problema en Leap | Auditoría en el panel de Leap |
| `parametros.qubits_fisicos`, `cadena_max` | Embedding de `EmbeddingComposite` | Costo real en qubits de cada formulación |
| `parametros.qpu_access_time_us` | Tiempo de acceso al QPU | Control del consumo de la cuota |

## Errores previstos

| Situación | Mensaje |
|---|---|
| Sin token o token inválido | `No se pudo conectar con D-Wave Leap. Revisa el token…` |
| Sin internet o red bloqueada | El mismo mensaje, con la causa de red |
| El problema no cabe en el QPU (embedding) | `El QPU rechazo o no completo la ejecucion…` |
| Falta `dwave-system` | `La ejecucion en D-Wave Leap requiere dwave-system…` |

## Pruebas sin gastar QPU

`tests/test_cliente_dwave.py` ejecuta la ruta completa del QPU con `MockDWaveSampler` del Ocean SDK, que reproduce la topología, el embedding, las cadenas y los tiempos sin conectarse a Leap. Corre en la integración continua en cada cambio.
