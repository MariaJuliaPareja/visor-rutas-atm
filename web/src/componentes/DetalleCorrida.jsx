import { formato } from "../lib/metricas.js";

// PAN-04: detalle de una corrida. La secuencia en texto es la alternativa accesible del mapa.
export default function DetalleCorrida({ corrida, onCerrar }) {
  const { metricas, ruta } = corrida;
  const repetido = new Set(corrida.repetidos);
  const vistos = new Set();
  return (
    <aside className="detalle" aria-label={`Detalle de la corrida ${corrida.id_corrida}`}>
      <header>
        <h2>Corrida {corrida.id_corrida} · {corrida.formulacion}</h2>
        <button className="icono" onClick={onCerrar} aria-label="Cerrar detalle">×</button>
      </header>
      {ruta.factible ? <span className="etiqueta ok">Factible</span> : <span className="etiqueta mal">Infactible</span>}
      {!ruta.factible && <p className="mensaje advertencia">⚠ Esta ruta no visita cada cajero exactamente una vez.</p>}

      <h3>Métricas</h3>
      <dl className="metricas">
        <div><dt>Distancia total</dt><dd>{formato(metricas.distancia_total)} km</dd></div>
        <div><dt>Gap respecto a la línea base</dt><dd>{corrida.gap === null ? "No comparable" : `${formato(corrida.gap)} %`}</dd></div>
        <div><dt>Tiempo de recocido</dt><dd>{metricas.tiempo_anneal === null ? "No aplica (simulado)" : `${formato(metricas.tiempo_anneal, 0)} µs`}</dd></div>
        <div><dt>Chain break fraction</dt><dd>{metricas.chain_break_fraction === null ? "No aplica (simulado)" : formato(metricas.chain_break_fraction, 3)}</dd></div>
      </dl>

      <h3>Secuencia de visita</h3>
      <p className="secuencia">
        {ruta.secuencia.map((c, k) => {
          const esRepeticion = repetido.has(c) && vistos.has(c);
          vistos.add(c);
          return (
            <span key={k}>
              {k > 0 && " → "}
              {esRepeticion ? <mark title="repetido">{c}</mark> : c}
            </span>
          );
        })}
        {" → "}{ruta.secuencia[0]}
      </p>
      {corrida.noVisitados.length > 0 && (
        <p className="mal-texto">No visitado: {corrida.noVisitados.map((c) => `cajero ${c}`).join(", ")}</p>
      )}
    </aside>
  );
}
