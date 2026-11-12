import { useEffect, useId, useRef, useState } from "react";
import { entradas } from "./indice.js";

function coincide(entrada, consulta) {
  if (!consulta) return true;
  const texto = [entrada.termino, entrada.definicion, entrada.detalle, entrada.fuente]
    .filter(Boolean)
    .join(" ")
    .toLocaleLowerCase("es");
  return texto.includes(consulta);
}

export default function PanelGlosario() {
  const [abierto, setAbierto] = useState(false);
  const [consulta, setConsulta] = useState("");
  const boton = useRef(null);
  const campo = useRef(null);
  const tituloId = useId();
  const q = consulta.trim().toLocaleLowerCase("es");
  const visibles = entradas.filter((entrada) => coincide(entrada, q));

  useEffect(() => {
    if (!abierto) return undefined;
    const previo = document.activeElement;
    campo.current?.focus();
    const alTeclado = (e) => {
      if (e.key !== "Escape") return;
      e.preventDefault();
      e.stopPropagation();
      setAbierto(false);
    };
    window.addEventListener("keydown", alTeclado);
    return () => {
      window.removeEventListener("keydown", alTeclado);
      if (previo instanceof HTMLElement) previo.focus();
    };
  }, [abierto]);

  return (
    <>
      <button type="button" className="secundario" ref={boton} aria-expanded={abierto} onClick={() => setAbierto(true)}>
        Glosario
      </button>
      {abierto && (
        <div className="glosario-fondo" onClick={() => setAbierto(false)}>
          <div
            className="glosario-panel"
            role="dialog"
            aria-modal="true"
            aria-labelledby={tituloId}
            onClick={(e) => e.stopPropagation()}
          >
            <header>
              <h2 id={tituloId}>Glosario</h2>
              <button type="button" className="icono" onClick={() => setAbierto(false)} aria-label="Cerrar glosario">×</button>
            </header>
            <input
              ref={campo}
              type="search"
              value={consulta}
              onChange={(e) => setConsulta(e.target.value)}
              placeholder="Buscar un término"
              aria-label="Buscar en el glosario"
            />
            {visibles.length === 0 ? (
              <p>Ningún término coincide con la búsqueda.</p>
            ) : (
              <ul>
                {visibles.map((entrada) => (
                  <li key={entrada.id}>
                    <h3>{entrada.termino}</h3>
                    <p>{entrada.definicion}</p>
                    {entrada.detalle && <p className="nota">{entrada.detalle}</p>}
                    {entrada.fuente && <p className="nota">{entrada.fuente}</p>}
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      )}
    </>
  );
}
