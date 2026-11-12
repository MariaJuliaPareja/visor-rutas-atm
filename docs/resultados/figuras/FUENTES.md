# Fuentes de las figuras del póster

Generado: 2026-11-12 01:15 Hora est. Pacífico, Sudamérica.

Cada cifra sale de estos archivos. Donde no hay medición, la tabla y las figuras dicen pendiente.

## Archivos

- `corridas_i31_n3_aleatorio_20261111-223814-073.json`
- `corridas_i31_n3_aleatorio_20261111-223814-073.pkl`
- `corridas_i3_n3_ibm_20261111-211121-481.pkl`
- `corridas_i3_n3_ibm_20261111-211121-481_estricto.json`
- `corridas_i41_n4_aleatorio_20261111-223808-052.json`
- `corridas_i41_n4_aleatorio_20261111-223808-052.pkl`
- `corridas_i42_n4_ibm_20261111-230125-642.json`
- `corridas_i42_n4_ibm_20261111-230125-642.pkl`
- `corridas_i4_n4_ibm_20261111-201713-615.pkl`
- `corridas_i4_n4_ibm_20261111-201713-615_estricto.json`
- `corridas_i4_n4_ibm_20261111-232903-006.json`
- `corridas_i4_n4_ibm_20261111-232903-006.pkl`
- `qaoa_ideal_verificacion_1000.json` (simulación ideal sin ruido; columna menor energía óptima)
- `corridas_i59_n5_ibm_20261111-213211-695.json` (sondeo n=5, una réplica; solo la figura de recursos)

## N por celda

| n | formulación | condición | N | backend | archivos |
|---|---|---|---|---|---|
| 3 | QUBO | azar | 20 | — | corridas_i31_n3_aleatorio_20261111-223814-073.json |
| 3 | QUBO | rampa fija | pendiente |  |  |
| 3 | QUBO | ángulos optimizados | 10 | ibm_fez | corridas_i3_n3_ibm_20261111-211121-481_estricto.json |
| 3 | GPS | azar | 20 | — | corridas_i31_n3_aleatorio_20261111-223814-073.json |
| 3 | GPS | rampa fija | 10 | ibm_fez | corridas_i3_n3_ibm_20261111-211121-481_estricto.json |
| 3 | GPS | ángulos optimizados | pendiente |  |  |
| 4 | QUBO | azar | 20 | — | corridas_i41_n4_aleatorio_20261111-223808-052.json |
| 4 | QUBO | rampa fija | 20 | ibm_kingston | corridas_i42_n4_ibm_20261111-230125-642.json |
| 4 | QUBO | ángulos optimizados | 20 | ibm_kingston | corridas_i4_n4_ibm_20261111-201713-615_estricto.json, corridas_i4_n4_ibm_20261111-232903-006.json |
| 4 | GPS | azar | 20 | — | corridas_i41_n4_aleatorio_20261111-223808-052.json |
| 4 | GPS | rampa fija | 10 | ibm_kingston | corridas_i4_n4_ibm_20261111-201713-615_estricto.json |
| 4 | GPS | ángulos optimizados | pendiente |  |  |

## Conteos y mediana exacta de la brecha

- n=3 QUBO azar: factibles 17/20, óptimas 17/20, mediana 0.0
- n=3 QUBO ángulos optimizados: factibles 10/10, óptimas 10/10, mediana 0.0
- n=3 GPS azar: factibles 0/20, óptimas 0/20, mediana 0.3353307609354033
- n=3 GPS rampa fija: factibles 0/10, óptimas 0/10, mediana 0.48353868427172575
- n=4 QUBO azar: factibles 0/20, óptimas 0/20, mediana 0.2539755132306014
- n=4 QUBO rampa fija: factibles 0/20, óptimas 0/20, mediana 0.25397551323060125
- n=4 QUBO ángulos optimizados: factibles 12/20, óptimas 8/20, mediana 0.0023771850982361718
- n=4 GPS azar: factibles 0/20, óptimas 0/20, mediana 0.4618409833438756
- n=4 GPS rampa fija: factibles 0/10, óptimas 0/10, mediana 0.590425082368304

## Mann-Whitney, brecha, hardware contra su azar

- n=4 GPS rampa fija: U = 191.0, p = 6.849060512600007e-05
- n=4 QUBO ángulos optimizados: U = 36.0, p = 8.78695926312649e-06
- n=4 QUBO rampa fija: U = 194.0, p = 0.8816094616689779

## Simulación ideal, QUBO n=4 ángulos optimizados

- QUBO n=4 COBYLA [2.6821, 0.4424]: 823/1000 = 0.823
- QUBO n=4 COBYLA [-0.4595, 0.4424]: 822/1000 = 0.822
- QUBO n=4 COBYLA [-0.4595, 0.4423]: 816/1000 = 0.816
- QUBO n=4 COBYLA [3.6011, -0.4423]: 818/1000 = 0.818
- QUBO n=4 COBYLA [2.6821, 0.4423]: 817/1000 = 0.817
- Azar analítico: 0.02411990415843801 = 1-(1-k/2^q)^200, con k igual al número de cadenas en E* del QUBO n=4.

## Sondeo n=5, figura de recursos

- GPS: N=1, backend ibm_fez, qubits 84, puertas de 2 qubits 1837
- QUBO: N=1, backend ibm_fez, qubits 25, puertas de 2 qubits 1178
- Promedio GPS/QUBO: 3.3561111111111113 (n=3: 3.333333, n=4: 3.375000, n=5: 3.360000)

## Qué no entra

Lotes de 1000 shots, recocido simulado y la prueba de humo de ibm_marrakesh no entran en la tabla.
El sondeo n=5 es una réplica en ibm_fez. Marcador hueco. No se suma a las celdas de n=3 ni n=4.
No hay curva ajustada. La nota de qubits es el promedio de GPS/QUBO en n=3, n=4 y n=5.
La brecha mediana usa todas las réplicas de la celda, factibles o no.
Una ruta óptima cuenta si es factible estricta y su distancia está a lo sumo a 0,001 km del Held-Karp.
