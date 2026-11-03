# Ejecución en IBM Quantum (QAOA)

D-Wave Leap no da servicio desde Perú (INC-08). IBM Quantum sí: su plan **Open** es gratuito y da **10 minutos de QPU al mes** en procesadores reales de 127 a 156 qubits. El pipeline resuelve los mismos modelos GPS y QUBO con QAOA (DEC-08).

## 1. Crear la cuenta y la API key

1. Entra a https://quantum.cloud.ibm.com y crea una cuenta (plan Open).
2. En el panel principal, copia la **API key**. Si te pide crear una instancia, créala con el plan Open y copia su **CRN**.
3. La API key **nunca** se escribe en el código, en `.env.example` ni en un commit.

## 2. Instalar y guardar la cuenta (Windows, PowerShell)

```powershell
cd pipeline
.\.venv\Scripts\Activate.ps1
pip install -r requirements-ibm.txt
python -c "from qiskit_ibm_runtime import QiskitRuntimeService as S; S.save_account(channel='ibm_quantum_platform', token='TU_API_KEY', instance='TU_CRN', set_as_default=True, overwrite=True)"
```

La cuenta queda guardada en tu usuario (`~/.qiskit`), fuera del repositorio. Si no tienes CRN, quita `instance='TU_CRN', `.

## 3. Verificar sin gastar QPU

```powershell
$env:PYTHONPATH="src"
python -m rutas_atm --probar-ibm
# Conexion con IBM Quantum correcta. Backends: ibm_brisbane (127 qubits), ...
```

## 4. Ejecutar

```powershell
python -m rutas_atm --sampler ibm --cajeros 3 --corridas 1
```

Cada corrida es **un solo job** en el QPU. Con 3 cajeros, QUBO usa 9 qubits y GPS 30; con 4 cajeros, 16 y 54. Los trabajos pueden esperar en cola varios minutos.

| Variable | Uso | Por defecto |
|---|---|---|
| `RUTAS_NUM_READS` | Disparos (*shots*) por corrida | `200` (se recomienda 1000) |
| `RUTAS_QAOA_REPS` | Capas de QAOA | `1` |
| `RUTAS_IBM_BACKEND` | Fija un backend (`ibm_brisbane`, ...) | el menos ocupado |
| `QISKIT_IBM_TOKEN`, `QISKIT_IBM_INSTANCE` | Alternativa a `save_account` | — |

## Cómo se ejecuta cada corrida

1. El modelo BQM se convierte a un Hamiltoniano de Ising (un qubit por variable binaria), con coeficientes normalizados.
2. Se arma el circuito QAOA (`QAOAAnsatz`).
3. Los ángulos se eligen **en local, sin gastar QPU**: hasta 18 qubits se optimizan con COBYLA sobre una simulación exacta en NumPy; con más qubits se usa una rampa lineal fija.
4. El circuito se transpila al backend (nivel de optimización 3) y se envía una sola vez con `SamplerV2`.
5. De todas las cadenas medidas se toma la de menor energía del BQM, igual que la muestra de menor energía en D-Wave.

## Qué registra cada corrida

| Campo en `parametros` | Uso |
|---|---|
| `backend`, `job_id` | Trazabilidad del hardware y auditoría en el panel de IBM |
| `qubits_logicos`, `qubits_fisicos` | Costo en qubits de cada formulación |
| `profundidad`, `puertas_2q` | Tamaño del circuito tras transpilar: principal fuente de ruido |
| `angulos`, `metodo_angulos`, `reps` | Reproducibilidad de QAOA |
| `qpu_segundos` | Consumo de la cuota mensual |

`tiempo_anneal` y `chain_break_fraction` quedan en `null`: son métricas propias del recocido.

## Qué esperar

QAOA de una capa en hardware ruidoso rara vez encuentra la ruta óptima, y GPS (más qubits y más profundidad) suele dar rutas infactibles. No es un error del pipeline: es el resultado que el visor marca como «No comparable» y que la tesis compara entre formulaciones.

## Pruebas sin gastar QPU

`tests/test_cliente_ibm.py` ejecuta la ruta completa con `FakeGuadalupeV2` (modelo de ruido de un procesador real de IBM) y con el simulador de Aer, y verifica que la simulación NumPy de QAOA coincida con Qiskit.
