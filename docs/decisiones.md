# Registro de decisiones de implementación

Cambios o precisiones respecto al diseño de las prácticas 05 (arquitectura), 06 (datos) y 07 (interfaces).

## DEC-01 · Recocido simulado por defecto, QPU por configuración

- **Diseño original:** DA-002 fija D-Wave Leap mediante Ocean SDK como motor de las corridas.
- **Cambio:** CMP-03 admite dos samplers, elegidos con `RUTAS_SAMPLER`: `simulado` (por defecto) y `qpu`.
- **Motivo:** desarrollar y probar contra el QPU gastaría los minutos gratuitos (RNF04) en corridas de prueba. El simulador de `dwave-samplers` recibe el mismo modelo (`BinaryQuadraticModel`), así que el resto del pipeline no cambia.
- **Consecuencia:** DA-002 se mantiene para los resultados experimentales; el ambiente de desarrollo y la integración continua usan el simulador.

## DEC-02 · Esquema 1.1: campo `sampler` y métricas del QPU anulables

- **Diseño original:** esquema 1.0 (Práctica 06), con `tiempo_anneal > 0` y `chain_break_fraction` obligatorios.
- **Cambio:** cada corrida declara `sampler`; `tiempo_anneal` y `chain_break_fraction` admiten `null`. Una regla entre entidades exige `tiempo_anneal` cuando `sampler = "qpu"`.
- **Motivo:** el recocido simulado no tiene tiempo de recocido físico ni embedding; registrar un tiempo de reloj como si fuera `tiempo_anneal` falsearía la métrica.
- **Migración:** `1.0 → 1.1` marca cada corrida con `sampler = "qpu"`, porque la versión 1.0 asumía el QPU. Implementada igual en Python (`validacion.py`) y en JavaScript (`validacion.js`).

## DEC-03 · La factibilidad se evalúa sobre la ruta decodificada

- **Diseño original:** "`factible` coincide con el contenido de `secuencia`" (diccionario de datos).
- **Precisión:** una corrida es factible si su secuencia decodificada visita cada cajero exactamente una vez.
- **Consecuencia:** si el estado del QUBO viola una restricción pero la ruta decodificada es válida (por ejemplo, dos cajeros en la misma posición y una posición vacía), se considera factible. En GPS se siguen las aristas `r = 1` desde el depósito y se ignoran aristas sobrantes. Las rutas infactibles se registran tal como salieron, con repeticiones y omisiones, y nunca se "reparan".

## DEC-04 · Exportación del reporte fuera del incremento

- **Diseño original:** el flujo 3 (TC-06, RF05) forma parte del prototipo navegable.
- **Cambio:** el botón **Exportar reporte** aparece deshabilitado, con una nota, en este incremento.
- **Motivo:** se priorizó el flujo de extremo a extremo que sostiene la comparación (pipeline → archivo → visor). El formato del reporte (RF05) sigue sin definirse.

## DEC-05 · El mapa se reencuadra cuando se abre el detalle

- **Diseño original:** el panel de detalle se abre *sobre* el mapa (wireframe de la Figura 18).
- **Cambio:** el panel se ubica *al lado* del mapa y el mapa se reencuadra al cambiar de tamaño.
- **Motivo:** en la primera versión el panel tapaba la mitad de los cajeros, incluidos los no visitados que el usuario necesita ver en las rutas infactibles (TC-04, TC-05). Ver INC-03.
