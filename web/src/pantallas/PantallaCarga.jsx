import { useRef, useState } from "react";
import { ErrorDeCarga, PASOS, leer, migrar, validarArchivo, validarEstructura, validarReglas } from "../carga/validacion.js";

const esperar = (ms) => new Promise((r) => setTimeout(r, ms));

// PAN-01 y PAN-02: zona de carga, validacion paso a paso y mensaje de rechazo.
export default function PantallaCarga({ onCargado, hayDatosPrevios, onCancelar, historial }) {
  const [arrastrando, setArrastrando] = useState(false);
  const [progreso, setProgreso] = useState(null); // { nombre, paso }
  const [rechazo, setRechazo] = useState(null);
  const entrada = useRef(null);

  async function procesar(archivo) {
    setRechazo(null);
    setProgreso({ nombre: archivo.name, paso: 0 });
    const avanzar = async (paso) => {
      setProgreso({ nombre: archivo.name, paso });
      await esperar(150); // deja ver cada paso; la validacion real es instantanea
    };
    try {
      validarArchivo(archivo.name, archivo.size);
      await avanzar(2);
      const crudo = leer(await archivo.text());
      await avanzar(3);
      const doc = migrar(crudo);
      await avanzar(4);
      validarEstructura(doc);
      await avanzar(5);
      const advertencias = validarReglas(doc);
      await avanzar(6);
      onCargado({ doc, advertencias, nombre: archivo.name });
    } catch (e) {
      const error = e instanceof ErrorDeCarga ? e : new ErrorDeCarga(2, "No se pudo leer el archivo.");
      if (!(e instanceof ErrorDeCarga)) console.error(e);
      setRechazo({ titulo: error.message, detalles: error.detalles });
      setProgreso(null);
    }
  }

  const alSoltar = (ev) => {
    ev.preventDefault();
    setArrastrando(false);
    const archivo = ev.dataTransfer.files?.[0];
    if (archivo) procesar(archivo);
  };

  return (
    <div className="app">
      <header className="barra">
        <h1>Visor de Rutas ATM</h1>
        {hayDatosPrevios && <button className="secundario" onClick={onCancelar}>Volver al archivo cargado</button>}
      </header>
      <main className="carga">
        {rechazo && (
          <section className="mensaje error" role="alert">
            <h2>No se pudo cargar el archivo</h2>
            <p>{rechazo.titulo}</p>
            {rechazo.detalles.length > 0 && (
              <ul className="detalle-tecnico">
                {rechazo.detalles.map((d) => <li key={d}><code>{d}</code></li>)}
              </ul>
            )}
            <div className="pie-mensaje">
              <p>No se cargaron datos. Corrige el archivo y vuelve a intentarlo.</p>
              <button className="secundario" onClick={() => entrada.current.click()}>Cargar otro archivo</button>
            </div>
          </section>
        )}

        {progreso ? (
          <section className="validando" aria-live="polite">
            <p className="etiqueta">Archivo seleccionado</p>
            <h2>{progreso.nombre}</h2>
            <ol>
              {PASOS.map((p, i) => (
                <li key={p} className={i < progreso.paso ? "hecho" : i === progreso.paso ? "en-curso" : ""}>
                  <span>{i < progreso.paso ? "OK" : i === progreso.paso ? "··" : "--"}</span> {p}
                  <em>{i < progreso.paso ? "Completado" : i === progreso.paso ? "En curso" : "Pendiente"}</em>
                </li>
              ))}
            </ol>
            <p>Validando el archivo…</p>
          </section>
        ) : (
          <section
            className={`zona ${arrastrando ? "activa" : ""}`}
            onDragOver={(e) => { e.preventDefault(); setArrastrando(true); }}
            onDragLeave={() => setArrastrando(false)}
            onDrop={alSoltar}
          >
            <h2>{arrastrando ? "Suelta el archivo para cargarlo" : "Arrastra aquí el archivo de corridas (.json)"}</h2>
            {rechazo ? (
              <p>o usa “Cargar otro archivo” para seleccionarlo</p>
            ) : (
              <>
                <p>o</p>
                <button className="principal" onClick={() => entrada.current.click()}>Cargar archivo</button>
              </>
            )}
            <input ref={entrada} type="file" accept=".json,application/json" hidden
              onChange={(e) => { if (e.target.files[0]) procesar(e.target.files[0]); e.target.value = ""; }} />
          </section>
        )}
        <p className="nota">Solo archivos .json generados por el pipeline de experimentación. El archivo se procesa en tu navegador y no se envía a ningún servidor.</p>
        {historial && !progreso && <Historial {...historial} onError={(m) => setRechazo({ titulo: m, detalles: [] })} />}
      </main>
    </div>
  );
}

const fecha = (iso) => new Date(iso).toLocaleString("es-ES", { dateStyle: "short", timeStyle: "short" });

// Lotes guardados en IndexedDB: se reabren sin volver a subir el archivo. Eliminar pide confirmacion.
function Historial({ estado, lotes, abrir, eliminar, borrarTodo, onError }) {
  const [confirmando, setConfirmando] = useState(null); // clave | "todo" | null

  if (estado === "no-disponible")
    return <p className="nota">Este navegador no permite guardar el historial (por ejemplo, en navegación privada). El visor funciona igual, sin historial.</p>;
  if (estado !== "lista" || lotes.length === 0) return null;

  const intentar = (accion) => accion().catch((e) => onError(e.message || "No se pudo abrir el lote guardado."));
  return (
    <section className="historial" aria-labelledby="titulo-historial">
      <header>
        <h2 id="titulo-historial">Lotes guardados en este navegador</h2>
        {confirmando === "todo" ? (
          <span className="confirmar">
            ¿Borrar todo el historial?
            <button className="peligro" onClick={() => intentar(async () => { await borrarTodo(); setConfirmando(null); })}>Sí, borrar</button>
            <button className="secundario" onClick={() => setConfirmando(null)}>Cancelar</button>
          </span>
        ) : (
          <button className="secundario" onClick={() => setConfirmando("todo")}>Borrar historial</button>
        )}
      </header>
      <ul>
        {lotes.map((l) => (
          <li key={l.clave}>
            <div>
              <b>Instancia {l.id_instancia}</b> · {l.tipo_instancia} · {l.num_cajeros} cajeros · {l.num_corridas} corridas
              <p className="nota">{l.nombre_archivo} · generado el {fecha(l.fecha_generacion)}</p>
            </div>
            {confirmando === l.clave ? (
              <span className="confirmar">
                <button className="peligro" onClick={() => intentar(async () => { await eliminar(l.clave); setConfirmando(null); })}>Confirmar</button>
                <button className="secundario" onClick={() => setConfirmando(null)}>Cancelar</button>
              </span>
            ) : (
              <span className="confirmar">
                <button className="principal" onClick={() => intentar(() => abrir(l.clave))}>Abrir</button>
                <button className="secundario" onClick={() => setConfirmando(l.clave)} aria-label={`Eliminar el lote de la instancia ${l.id_instancia}`}>Eliminar</button>
              </span>
            )}
          </li>
        ))}
      </ul>
      <p className="nota">Se guardan solo en este equipo y nunca se envían a un servidor. Al abrir un lote se vuelve a validar.</p>
    </section>
  );
}
