# Matriz de integración y contratos

| Origen | Destino | Mecanismo | Datos / contrato | Error previsto | Manejo |
|---|---|---|---|---|---|
| CMP-01 Preparación de datos | CMP-02, CMP-04 | Llamada en proceso (Python) | `Instancia` con matriz `n × n` en km | Menos de 3 o más de 100 cajeros (RNF05) | `ValueError` antes de construir nada |
| CMP-02 Formulación TSP | CMP-03 Cliente D-Wave | Llamada en proceso | `dimod.BinaryQuadraticModel` binario | Formulación desconocida | `ValueError` |
| CMP-03 Cliente D-Wave | D-Wave Leap | Ocean SDK sobre HTTPS (`RUTAS_SAMPLER=qpu`) | BQM + `num_reads`, `annealing_time` | Token ausente, red, cuota agotada | `ErrorDeMuestreo` con la causa, sin traza ni token en la salida |
| CMP-03 Cliente D-Wave | CMP-02 (decodificación) | Llamada en proceso | Muestra de menor energía | Ruta infactible | Se registra tal como salió (`factible: false`) |
| CMP-04 Línea base | Lote crudo | Llamada en proceso | `(distancia_optima, ruta)` | Más de 18 cajeros | `ValueError` |
| Experimento | Lote crudo `.pkl` | Escritura atómica tras cada corrida | `LoteCrudo` (instancia, línea base, corridas con bits y energía) | Caída del proceso | Solo se pierde la corrida en curso |
| Lote crudo `.pkl` | CMP-05 Conversor | Lectura en disco | `LoteCrudo` del propio pipeline | `.pkl` ajeno | `TypeError`: se rechaza |
| CMP-05 Conversor | Archivo `.json` | Escritura en disco | Esquema 1.1 + reglas entre entidades | Documento inválido; archivo existente | `ArchivoInvalido` o `FileExistsError`: no se escribe nada |
| Archivo `.json` | CMP-06 Carga | File API del navegador (carga manual) | El mismo esquema 1.1 y las mismas reglas | Formato, tamaño, lectura, versión, estructura, reglas | Rechazo todo o nada con el paso y el motivo (RNF11) |
| CMP-06 Carga | CMP-07 Métricas | Llamada en proceso (JavaScript) | Documento validado y migrado | Distancia inconsistente | Advertencia que no bloquea |
| CMP-06 Carga | IndexedDB | Transacción sobre `instancias` y `corridas` | Documentos del modelo NoSQL | IndexedDB no disponible | El visor funciona sin historial |
| IndexedDB | CMP-06 Carga | Lectura por índice `por_instancia` | Lote reconstruido | Documento alterado | Revalidación: se rechaza con el motivo |
| CMP-07 Métricas | CMP-08 Mapa y detalle | Props de React | Corridas con gap, no visitados y repetidos | Ruta infactible | Gap "No comparable", excluida del resumen |
| CMP-07 Métricas | CMP-09 Reportes | Carga diferida del módulo + jsPDF | Las mismas cifras de la pantalla | Falla al generar | Mensaje de error y **Reintentar**; no se descarga un archivo incompleto |
| CMP-08 Mapa | OpenStreetMap | Teselas sobre HTTPS | Coordenadas de la vista, no del archivo | Sin conexión | El mapa muestra cajeros y rutas sobre fondo gris |

## Contrato principal: archivo de intercambio

| Campo | Valor |
|---|---|
| Operación | Publicar los resultados de un lote de corridas para su análisis |
| Mecanismo | Archivo `.json` escrito por CMP-05 y leído por CMP-06 |
| Definición | `schema/esquema_archivo_intercambio.schema.json` (JSON Schema 2020-12), una sola copia usada por ambos lados |
| Versión | `version_esquema = "1.1"`; el visor migra la 1.0 |
| Autenticación | No aplica: no hay servidor (RNF06) |
| Respuesta exitosa | El visor muestra la vista principal |
| Errores previstos | Ver la fila *Archivo `.json` → CMP-06* |
| Responsable | CMP-05 al escribir; CMP-06 al leer |
