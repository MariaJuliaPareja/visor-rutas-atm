import { useEffect, useMemo, useState } from "react";
import { abrir, disponible, guardarPreferencia, leerPreferencia } from "../persistencia/almacen.js";
import { FORMULACIONES, SUPUESTOS, calcularMetricas, formato, resumenGerencial } from "../metricas/metricas.js";
import PanelGerencia from "./PanelGerencia.jsx";
import MapaRutas from "../visualizacion/MapaRutas.jsx";
import DetalleCorrida from "../visualizacion/DetalleCorrida.jsx";

const CLAVE_SUPUESTOS = "supuestos_gerencia";

const NOTA_NO_COMPARABLE = "La ruta repite u omite cajeros; su gap no es comparable y se excluye del resumen.";

// Nota accesible: se muestra con el cursor, con el foco del teclado y al tocarla; Esc la cierra (WCAG 1.4.13).
function NoComparable() {
  const [abierta, setAbierta] = useState(false);
  return (
    <span className="nota-info" tabIndex={0} role="button" aria-label={`No comparable. ${NOTA_NO_COMPARABLE}`}
      onMouseEnter={() => setAbierta(true)} onMouseLeave={() => setAbierta(false)}
      onFocus={() => setAbierta(true)} onBlur={() => setAbierta(false)}
      onClick={() => setAbierta((v) => !v)}
      onKeyDown={(e) => { if (e.key === "Escape") setAbierta(false); }}>
      No comparable ⓘ
      {abierta && <span className="burbuja" role="tooltip">{NOTA_NO_COMPARABLE}</span>}
    </span>
  );
}

// PAN-03: barra superior, comparacion (tarjetas + tabla) y mapa, visibles a la vez.
export default function VistaPrincipal({ doc, advertencias, onCargarOtro }) {
  const metricas = useMemo(() => calcularMetricas(doc), [doc]);
  const { corridas, resumen } = metricas;
  const [supuestos, setSupuestos] = useState(SUPUESTOS);
  const gerencia = useMemo(() => resumenGerencial(doc, metricas, supuestos), [doc, metricas, supuestos]);

  // Los supuestos se guardan en IndexedDB (coleccion preferencias) y se recuerdan entre sesiones.
  useEffect(() => {
    if (!disponible()) return;
    abrir().then((bd) => leerPreferencia(bd, CLAVE_SUPUESTOS))
      .then((guardados) => { if (guardados) setSupuestos({ ...SUPUESTOS, ...guardados }); })
      .catch((e) => console.warn("No se pudieron leer los supuestos guardados", e));
  }, []);
  const persistir = (nuevos) => {
    if (!disponible()) return;
    abrir().then((bd) => guardarPreferencia(bd, CLAVE_SUPUESTOS, nuevos))
      .catch((e) => console.warn("No se pudieron guardar los supuestos", e));
  };
  const cambiarSupuesto = (clave, valor) => {
    const x = Number(valor);
    if (!Number.isFinite(x) || x <= 0) return;
    setSupuestos((s) => { const nuevos = { ...s, [clave]: x }; persistir(nuevos); return nuevos; });
  };
  const restablecerSupuestos = () => { setSupuestos(SUPUESTOS); persistir(SUPUESTOS); };
  const [seleccion, setSeleccion] = useState(null);
  const [exportacion, setExportacion] = useState(null); // null | "generando" | { ok, texto }
  const corrida = corridas.find((c) => c.id_corrida === seleccion) ?? null;
  const inst = doc.instancia;
  const conAdvertencia = new Set(advertencias.map((a) => a.id_corrida));

  async function exportar() {
    setExportacion("generando");
    try {
      // CMP-09 se carga solo al exportar: jsPDF no pesa en la carga inicial del visor (RNF01).
      const { contenidoReporte, generarPdf, nombreReporte } = await import("../reportes/reporte.js");
      const contenido = contenidoReporte(doc, metricas, advertencias, gerencia);
      generarPdf(contenido).save(nombreReporte(doc));
      const n = contenido.infactibles;
      const extra = n ? ` · Incluye ${n} ${n === 1 ? "ruta infactible marcada" : "rutas infactibles marcadas"} con su nota explicativa` : "";
      setExportacion({ ok: true, texto: `Reporte descargado: ${nombreReporte(doc)}${extra}` });
    } catch (e) {
      console.error(e);
      setExportacion({ ok: false, texto: "No se pudo generar el reporte. No se descargó ningún archivo." });
    }
  }

  return (
    <div className="app">
      <header className="barra">
        <h1>Visor de Rutas ATM</h1>
        <p className="contexto">
          Instancia {inst.id_instancia} · {inst.fuente?.tipo === "osm" ? `cajeros reales ${inst.fuente.entidad ?? ""} (OpenStreetMap)` : "datos sintéticos"} · {inst.cajeros.length} puntos · esquema {doc.version_esquema}
        </p>
        <button className="secundario" onClick={onCargarOtro}>Cargar otro archivo</button>
        <button className="principal" onClick={exportar} disabled={exportacion === "generando"}>
          {exportacion === "generando" ? "Generando reporte…" : "Exportar reporte"}
        </button>
      </header>

      <main className="principal-grid">
        <section className="comparacion">
          <PanelGerencia resumen={gerencia} onCambiarSupuesto={cambiarSupuesto} onRestablecer={restablecerSupuestos} />
          <h2 className="subtitulo">Comparación técnica de formulaciones</h2>
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
                      <div><dt>Rutas factibles</dt><dd>{r.factibles} / {r.total}</dd></div>
                      <div><dt>% de ahorro respecto a GPS</dt><dd>{f === "GPS" ? "Referencia" : r.ahorroVsGps === null ? "No calculable" : `${formato(r.ahorroVsGps)} %`}</dd></div>
                    </dl>
                  )}
                  {r.motivoAhorro && <p className="nota">{r.motivoAhorro}</p>}
                </article>
              );
            })}
          </div>

          <section className="corridas">
            <header className="corridas-cabecera">
              <h2>Corridas</h2>
              <p>Selecciona una fila para ver su ruta</p>
            </header>
            {advertencias.length > 0 && (
              <div className="mensaje advertencia" role="status">
                {advertencias.map((a) => <p key={a.id_corrida}><span aria-hidden="true">⚠</span> <b>Advertencia:</b> {a.mensaje}</p>)}
              </div>
            )}
            <table>
              <thead>
                <tr>
                  <th scope="col">Corrida</th><th scope="col">Formulación</th>
                  <th scope="col" className="num">Distancia (km)</th><th scope="col" className="num">Gap (%)</th>
                  <th scope="col" className="num">Chain break fraction</th><th scope="col">Factible</th>
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
                    <td className="num">{formato(c.metricas.distancia_total)}{conAdvertencia.has(c.id_corrida) && <span className="icono-adv" title="Distancia inconsistente"> ⚠</span>}</td>
                    <td className="num">{c.gap === null ? <NoComparable /> : formato(c.gap)}</td>
                    <td className="num">{c.metricas.chain_break_fraction === null ? "No aplica" : formato(c.metricas.chain_break_fraction, 3)}</td>
                    <td>{c.ruta.factible ? <span className="etiqueta ok">Sí</span> : <span className="etiqueta mal">Infactible</span>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="nota">El resumen solo considera rutas factibles. Línea base (Held-Karp): {formato(inst.linea_base.dist_optima)} km.</p>
          </section>
        </section>

        <section className="lado-mapa">
          <MapaRutas instancia={inst} corrida={corrida} panelAbierto={Boolean(corrida)} />
          {corrida && <DetalleCorrida corrida={corrida} onCerrar={() => setSeleccion(null)} />}
        </section>
      </main>

      {exportacion && exportacion !== "generando" && (
        <div className={`aviso ${exportacion.ok ? "ok" : "error"}`} role={exportacion.ok ? "status" : "alert"}>
          <span aria-hidden="true">{exportacion.ok ? "✓" : "⚠"}</span>
          <p>{exportacion.texto}</p>
          {!exportacion.ok && <button className="secundario" onClick={exportar}>Reintentar</button>}
          <button className="icono" onClick={() => setExportacion(null)} aria-label="Cerrar mensaje">×</button>
        </div>
      )}
    </div>
  );
}
