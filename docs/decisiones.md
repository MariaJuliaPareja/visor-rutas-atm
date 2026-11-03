# Registro de decisiones de implementación

Cambios o precisiones respecto al diseño de las prácticas 05 (arquitectura), 06 (datos) y 07 (interfaces).

## DEC-01 · Recocido simulado por defecto, QPU por configuración

- **Diseño original:** DA-002 fija D-Wave Leap mediante Ocean SDK como motor de las corridas.
- **Cambio:** CMP-03 (`cliente_dwave.py`) admite dos samplers, elegidos con `RUTAS_SAMPLER`: `simulado` (por defecto) y `qpu`.
- **Motivo:** desarrollar y probar contra el QPU gastaría los minutos gratuitos (RNF04) en corridas de prueba. El simulador de `dwave-samplers` recibe el mismo `BinaryQuadraticModel`, así que el resto del pipeline no cambia.
- **Consecuencia:** DA-002 se mantiene para los resultados experimentales; el desarrollo y la integración continua usan el simulador.

## DEC-02 · Esquema 1.1: campo `sampler` y métricas del QPU anulables

- **Diseño original:** esquema 1.0 (Práctica 06), con `tiempo_anneal > 0` y `chain_break_fraction` obligatorios.
- **Cambio:** cada corrida declara `sampler`; `tiempo_anneal` y `chain_break_fraction` admiten `null`. Una regla entre entidades exige `tiempo_anneal` cuando `sampler = "qpu"`.
- **Motivo:** el recocido simulado no tiene tiempo de recocido físico ni embedding; registrar un tiempo de reloj como `tiempo_anneal` falsearía la métrica.
- **Migración:** `1.0 → 1.1` marca cada corrida con `sampler = "qpu"`. Implementada igual en Python y en JavaScript.

## DEC-03 · La factibilidad se evalúa sobre la ruta decodificada

- **Diseño original:** "`factible` coincide con el contenido de `secuencia`" (diccionario de datos).
- **Precisión:** una corrida es factible si su secuencia decodificada visita cada cajero exactamente una vez.
- **Consecuencia:** si el estado del QUBO viola una restricción pero la ruta decodificada es válida, se considera factible. Las rutas infactibles se registran tal como salieron, con repeticiones y omisiones; nunca se "reparan".

## DEC-04 · Persistencia NoSQL en IndexedDB

- **Diseño original:** la Práctica 06 eligió el archivo JSON sin persistencia en el navegador y dejó IndexedDB como mejora posible para conservar el historial sin contradecir RNF06.
- **Cambio:** el visor guarda cada archivo válido en IndexedDB, en las colecciones `instancias` y `corridas` (ver `modelo-datos-nosql.md`), y permite reabrir y eliminar lotes.
- **Motivo:** elimina el costo de volver a cargar el archivo en cada sesión (DA-004) sin enviar datos fuera del equipo.
- **Consecuencia:** reemplaza el control de privacidad "sin persistencia en el navegador" de la Práctica 06 por uno nuevo: solo datos sintéticos, almacenamiento local al sitio, y eliminación de un lote o de todo el historial con confirmación. Si el navegador no permite IndexedDB (por ejemplo, en navegación privada), el visor funciona sin historial.

## DEC-05 · Lote crudo `.pkl` como fuente del archivo de intercambio

- **Diseño original:** CMP-05 "transforma las corridas `.pkl` al formato del visor" (Práctica 05) y los `.pkl` son la fuente original para regenerar el `.json` (Práctica 06).
- **Implementación:** el experimento guarda el lote en `salidas/crudos/*.pkl` después de cada corrida, con escritura atómica, y el conversor genera el `.json` desde ese lote. `--convertir` regenera el `.json` desde un `.pkl` existente.
- **Seguridad:** `cargar_crudos()` solo acepta objetos `LoteCrudo` del propio pipeline; el visor nunca recibe `.pkl`.

## DEC-06 · Panel de detalle sobre el mapa, con reencuadre

- **Diseño original:** el panel de detalle se abre *sobre* el mapa (wireframe de la Práctica 07, Figura 18).
- **Implementación:** se respeta el wireframe. Para que el panel no tape cajeros, el mapa se reencuadra dejando libre el ancho del panel, y la cabecera y la leyenda se acomodan al área visible. Ver INC-03.

## DEC-07 · Rutas por las calles de OpenStreetMap (OSRM)

- **Problema:** el mapa unía los cajeros con líneas rectas que cruzaban manzanas, y las distancias eran en línea recta (haversine).
- **Decisión:** el visor pide a OSRM el trazado de cada ruta por la red vial de OpenStreetMap (`/route`, `overview=full`, `geometries=geojson`) y, si el servicio no responde, vuelve a la línea recta y lo avisa en la leyenda. El pipeline puede medir las distancias por calles con `RUTAS_DISTANCIA=vial` (`/table`), y el archivo lo indica en `matriz_distancias.metrica` (campo opcional, compatible con 1.1).
- **Simetría:** las calles de un solo sentido hacen que A→B ≠ B→A; como GPS y QUBO asumen una matriz simétrica, se usa el promedio de ambos sentidos.
- **Privacidad:** solo salen del navegador las coordenadas de los cajeros, que son sintéticas (RNF06). `VITE_OSRM_URL` permite usar un OSRM propio o desactivar el trazado (`off`).

## DEC-08 · QAOA en IBM Quantum como hardware cuántico real

- **Problema:** D-Wave Leap no da servicio desde Perú (INC-08), así que el modo `qpu` no puede ejecutarse desde aquí.
- **Decisión:** se agrega el sampler `ibm`, que resuelve los mismos modelos GPS y QUBO con QAOA en procesadores de compuerta de IBM Quantum (plan Open, accesible desde Perú). El esquema pasa a 1.2 con el valor `ibm`; la migración desde 1.1 no cambia datos.
- **Ahorro de QPU:** los ángulos se eligen en local (optimización exacta hasta 18 qubits, rampa lineal por encima) y cada corrida envía un solo job.
- **Consecuencia:** QAOA y el recocido no son el mismo algoritmo; el informe compara formulaciones dentro de cada sampler, no entre samplers.

