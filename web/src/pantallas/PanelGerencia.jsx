import { formato } from "../metricas/metricas.js";

const CAMPOS = [
  ["rendimiento_km_l", "Rendimiento del vehículo", "km/l"],
  ["precio_soles_l", "Precio del diésel", "S/ por litro"],
  ["co2_kg_l", "Emisión del diésel", "kg CO₂ por litro"],
  ["recorridos_anio", "Recorridos de esta ruta al año", "recorridos"],
  ["velocidad_kmh", "Velocidad media (si no hay tiempos por calles)", "km/h"],
];

const entero = (x) => formato(x, 0);

// Resumen para gerencia (DEC-09): lo que un gerente necesita saber, en km, minutos, soles y CO2.
export default function PanelGerencia({ resumen, onCambiarSupuesto, onRestablecer }) {
  const { habitual, propuesta, porRecorrido: r, porAnio: a, supuestos } = resumen;
  return (
    <section className="gerencia" aria-labelledby="titulo-gerencia">
      <header>
        <h2 id="titulo-gerencia">Resumen para gerencia</h2>
        <p>Ruta propuesta frente a la ruta habitual (visitar los cajeros en el orden de la planilla).</p>
      </header>

      {resumen.sinAhorro ? (
        <p className="mensaje advertencia">
          En esta instancia el orden de la planilla ya es la mejor ruta: no hay ahorro que reportar. Con más
          cajeros por recorrido es menos probable que el orden de la planilla sea el óptimo.
        </p>
      ) : (
        <dl className="cifras">
          <div><dt>Ahorro al año</dt><dd>S/ {formato(a.soles)}</dd><span>S/ {formato(r.soles)} por recorrido</span></div>
          <div><dt>Diésel ahorrado al año</dt><dd>{entero(a.litros)} L</dd><span>{formato(r.litros)} L por recorrido</span></div>
          <div><dt>Distancia ahorrada</dt><dd>{formato(r.pct, 1)} %</dd><span>{formato(r.km)} km por recorrido · {entero(a.km)} km al año</span></div>
          <div><dt>Tiempo ahorrado</dt><dd>{entero(r.min)} min</dd><span>por recorrido · {formato(a.horas, 1)} h al año{resumen.tiempoEstimado ? " (estimado)" : ""}</span></div>
          <div><dt>CO₂ evitado al año</dt><dd>{entero(a.co2)} kg</dd><span>{formato(r.co2)} kg por recorrido</span></div>
        </dl>
      )}

      <table className="comparativa">
        <thead>
          <tr><th scope="col">Ruta</th><th scope="col" className="num">km</th><th scope="col" className="num">min</th><th scope="col" className="num">Diésel (L)</th><th scope="col" className="num">Costo (S/)</th><th scope="col">Orden de visita</th></tr>
        </thead>
        <tbody>
          <tr><td>Habitual (planilla)</td><td className="num">{formato(habitual.km)}</td><td className="num">{entero(habitual.min)}</td><td className="num">{formato(resumen.consumo.habitual.litros)}</td><td className="num">{formato(resumen.consumo.habitual.soles)}</td><td>{habitual.secuencia.join(" → ")} → 0</td></tr>
          <tr><td>Propuesta</td><td className="num">{formato(propuesta.km)}</td><td className="num">{entero(propuesta.min)}</td><td className="num">{formato(resumen.consumo.propuesta.litros)}</td><td className="num">{formato(resumen.consumo.propuesta.soles)}</td><td>{propuesta.secuencia.join(" → ")} → {propuesta.secuencia[0]}</td></tr>
        </tbody>
      </table>
      <p className="nota">
        Propuesta: {propuesta.origen}.{" "}
        {resumen.alcanzaOptimo ? "Coincide con la mejor ruta posible (Held-Karp)." : `La mejor ruta posible mide ${formato(resumen.optimoKm)} km (Held-Karp).`}
      </p>

      <details className="supuestos">
        <summary>Supuestos del cálculo (editables)</summary>
        <div className="campos">
          {CAMPOS.map(([clave, etiqueta, unidad]) => (
            <label key={clave}>
              <span>{etiqueta}</span>
              <input type="number" min="0.01" step="any" value={supuestos[clave]}
                onChange={(e) => onCambiarSupuesto(clave, e.target.value)} />
              <em>{unidad}</em>
            </label>
          ))}
        </div>
        <p className="nota">
          Ajusta el precio del diésel al vigente y el rendimiento al de tu flota. Se guardan en este navegador
          y el reporte PDF usa estos mismos valores.{" "}
          <button type="button" className="enlace" onClick={onRestablecer}>Restablecer valores por defecto</button>
        </p>
      </details>
    </section>
  );
}
