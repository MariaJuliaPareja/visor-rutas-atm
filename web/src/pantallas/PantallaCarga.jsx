import { useRef, useState } from "react";
import { ErrorDeCarga, PASOS, leer, migrar, validarArchivo, validarEstructura, validarReglas } from "../carga/validacion.js";

const esperar = (ms) => new Promise((r) => setTimeout(r, ms));

// PAN-01 y PAN-02: zona de carga, validacion paso a paso y mensaje de rechazo.
export default function PantallaCarga({ onCargado, hayDatosPrevios, onCancelar }) {
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
            <h2>⚠ No se pudo cargar el archivo</h2>
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
                  <span>{i < progreso.paso ? "✓" : i === progreso.paso ? "…" : "○"}</span> {p}
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
      </main>
    </div>
  );
}
