import { useMemo, useState } from "react";
import { FORMULACIONES, calcularMetricas, formato } from "../metricas/metricas.js";
import MapaRutas from "../visualizacion/MapaRutas.jsx";
import DetalleCorrida from "../visualizacion/DetalleCorrida.jsx";

// PAN-03: barra superior, comparacion (tarjetas + tabla) y mapa, visibles a la vez.
export default function VistaPrincipal({ doc, advertencias, nombre, onCargarOtro }) {
  const { corridas, resumen } = useMemo(() => calcularMetricas(doc), [doc]);
  const [seleccion, setSeleccion] = useState(null);
  const corrida = corridas.find((c) => c.id_corrida === seleccion) ?? null;
  const inst = doc.instancia;
  const conAdvertencia = new Set(advertencias.map((a) => a.id_corrida));

  return (
    <div className="app">
      <header className="barra">
        <h1>Visor de Rutas ATM</h1>
        <p className="contexto">
          Instancia {inst.id_instancia} · {inst.tipo_instancia} · {inst.cajeros.length} cajeros · esquema {doc.version_esquema} · <span title={nombre}>{nombre}</span>
        </p>
        <button className="secundario" onClick={onCargarOtro}>Cargar otro archivo</button>
        <button className="principal" disabled title="Exportar reporte (RF05) queda para el siguiente incremento">Exportar reporte</button>
      </header>

      <main className="principal-grid">
        <section className="comparacion">
          <div className="tarjetas">
            {FORMULACIONES.map((f) => {
              const r = resumen[f];
              return (
                <article key={f} className="tarjeta">
                  <h2>{f}</h2>
                  {r.total === 0 ? (
                    <p className="vacio">Sin corridas en este archivo</p>
                  ) : (
                    <dl>
                      <div><dt>Mejor gap</dt><dd>{r.mejorGap === null ? "Sin rutas factibles" : `${formato(r.mejorGap)} %`}</dd></div>
                      <div><dt>Rutas factibles</dt><dd>{r.factibles} de {r.total}</dd></div>
                      <div><dt>% de ahorro respecto a GPS</dt><dd>{r.ahorroVsGps === null ? "No calculable" : `${formato(r.ahorroVsGps)} %`}</dd></div>
                    </dl>
                  )}
                  {r.motivoAhorro && <p className="nota">{r.motivoAhorro}</p>}
                </article>
              );
            })}
          </div>
          <p className="nota">El resumen solo considera rutas factibles. Línea base (Held-Karp): {formato(inst.linea_base.dist_optima)} km.</p>

          {advertencias.length > 0 && (
            <div className="mensaje advertencia" role="status">
              {advertencias.map((a) => <p key={a.id_corrida}>⚠ <b>Advertencia:</b> {a.mensaje}</p>)}
            </div>
          )}

          <table>
            <caption>Corridas · selecciona una fila para ver su ruta</caption>
            <thead>
              <tr>
                <th scope="col">Corrida</th><th scope="col">Formulación</th><th scope="col">Sampler</th>
                <th scope="col">Distancia (km)</th><th scope="col">Gap (%)</th>
                <th scope="col">Chain break fraction</th><th scope="col">Factible</th>
              </tr>
            </thead>
            <tbody>
              {corridas.map((c) => (
                <tr key={c.id_corrida} className={c.id_corrida === seleccion ? "seleccionada" : ""}
                  tabIndex={0} aria-selected={c.id_corrida === seleccion}
                  onClick={() => setSeleccion(c.id_corrida)}
                  onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); setSeleccion(c.id_corrida); } }}>
                  <td>{c.id_corrida}</td>
                  <td>{c.formulacion}</td>
                  <td>{c.sampler}</td>
                  <td className="num">{formato(c.metricas.distancia_total)}{conAdvertencia.has(c.id_corrida) && <span className="icono-adv" title="Distancia inconsistente"> ⚠</span>}</td>
                  <td className="num">{c.gap === null
                    ? <span title="La ruta repite u omite cajeros; su gap no es comparable y se excluye del resumen.">No comparable ⓘ</span>
                    : formato(c.gap)}</td>
                  <td className="num">{c.metricas.chain_break_fraction === null ? "No aplica" : formato(c.metricas.chain_break_fraction, 3)}</td>
                  <td>{c.ruta.factible ? <span className="etiqueta ok">Sí</span> : <span className="etiqueta mal">Infactible</span>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>

        <section className="lado-mapa">
          <MapaRutas instancia={inst} corrida={corrida} />
          {corrida && <DetalleCorrida corrida={corrida} onCerrar={() => setSeleccion(null)} />}
        </section>
      </main>
    </div>
  );
}
