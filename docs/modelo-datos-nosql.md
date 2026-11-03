# Modelo de datos NoSQL (documental)

Implementa el modelo lógico de la Práctica 06 como colecciones de documentos. La regla es la misma que la Práctica 06 usó para el archivo de intercambio: **las entidades débiles con relación 1:1 se embeben en su documento dueño**, y las relaciones 1:N se resuelven con una referencia y un índice.

## Dónde vive cada dato

| Almacén | Tecnología | Contenido | Rol |
|---|---|---|---|
| Lote crudo | `.pkl` (pipeline) | Instancia, línea base y corridas con los bits y la energía de cada muestra | Fuente original; nunca se modifica (Práctica 06, recuperación) |
| Archivo de intercambio | `.json` (esquema 1.1) | El documento que comparten pipeline y visor | Contrato entre subsistemas (DA-005) |
| Historial del visor | IndexedDB, base `rutas_atm` | Colecciones `instancias` y `corridas` | Reabrir lotes sin volver a subir el archivo |

## Correspondencia con el modelo lógico de la Práctica 06

| Tabla lógica (Práctica 06) | Colección IndexedDB | Representación |
|---|---|---|
| INSTANCIA | `instancias` | Documento raíz; clave `"<id_instancia>@<fecha_generacion>"` |
| CAJERO | `instancias` | Arreglo `cajeros` embebido |
| MATRIZ_DISTANCIAS, DISTANCIA_CAJERO | `instancias` | Objeto `matriz_distancias` con el arreglo `n × n` embebido |
| LINEA_BASE, LINEA_BASE_CAJERO | `instancias` | Objeto `linea_base` con la ruta ordenada embebida |
| CORRIDA | `corridas` | Documento propio; clave compuesta `[clave_instancia, id_corrida]` |
| RUTA, RUTA_CAJERO | `corridas` | Objeto `ruta` con la `secuencia` ordenada embebida |
| METRICAS_CUANTICAS | `corridas` | Objeto `metricas` embebido |

## Índices

| Colección | Índice | Uso |
|---|---|---|
| `corridas` | `por_instancia` (`clave_instancia`) | Reconstruir un lote completo y eliminarlo con todas sus corridas |
| `corridas` | `por_formulacion` (`[clave_instancia, formulacion]`) | Contar o filtrar corridas GPS y QUBO de un lote (índice "corridas por formulación" de la Práctica 06) |

## Integridad sin motor relacional

- **Atomicidad:** guardar y eliminar un lote ocurre en una sola transacción sobre ambas colecciones; no quedan corridas huérfanas.
- **Idempotencia:** volver a cargar el mismo archivo reemplaza el lote; no duplica corridas.
- **Revalidación:** al reabrir un lote, el documento se reconstruye y pasa otra vez por el esquema y las reglas entre entidades. Lo guardado en el navegador no se da por confiable.
- **Privacidad (RNF06):** IndexedDB es local al navegador y al sitio; nada se envía a un servidor. Solo se guardan datos sintéticos, y el usuario puede eliminar un lote o todo el historial.
