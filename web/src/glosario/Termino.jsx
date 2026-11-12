import { useEffect, useId, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { exigirEntrada } from "./indice.js";

const INICIAL = { sobre: false, foco: false, anclado: false, cerrado: false };
const MARGEN = 8;

export function reducir(estado, evento) {
  switch (evento) {
    case "entrar":
      return { ...estado, sobre: true, cerrado: false };
    case "salir":
      return { ...estado, sobre: false, cerrado: false };
    case "foco":
      return { ...estado, foco: true, cerrado: false };
    case "blur":
      return { ...estado, foco: false, cerrado: false };
    case "toque":
      return { ...estado, anclado: !estado.anclado, cerrado: false };
    case "escape":
      return { ...estado, anclado: false, sobre: false, cerrado: true };
    default:
      return estado;
  }
}

export function estaVisible(estado) {
  return !estado.cerrado && (estado.sobre || estado.foco || estado.anclado);
}

function colocar(ancla, tip) {
  let left = ancla.left;
  let top = ancla.bottom + 6;
  const ancho = window.innerWidth;
  const alto = window.innerHeight;
  if (left + tip.width > ancho - MARGEN) left = ancho - MARGEN - tip.width;
  if (left < MARGEN) left = MARGEN;
  if (top + tip.height > alto - MARGEN) {
    const arriba = ancla.top - 6 - tip.height;
    top = arriba >= MARGEN ? arriba : Math.max(MARGEN, alto - MARGEN - tip.height);
  }
  return { left, top };
}

export default function Termino({ id, children }) {
  const entrada = exigirEntrada(id);
  const [estado, setEstado] = useState(INICIAL);
  const [caja, setCaja] = useState(null);
  const boton = useRef(null);
  const burbuja = useRef(null);
  const tipId = useId();
  const visible = Boolean(entrada) && estaVisible(estado);

  useEffect(() => {
    if (!visible || !boton.current || !burbuja.current) return;
    setCaja(colocar(boton.current.getBoundingClientRect(), burbuja.current.getBoundingClientRect()));
  }, [visible, entrada]);

  if (!entrada) return children;

  const despachar = (evento) => setEstado((actual) => reducir(actual, evento));
  const tooltip = (
    <span
      ref={burbuja}
      id={tipId}
      role="tooltip"
      className="termino-burbuja"
      hidden={!visible}
      style={caja ?? { left: -9999, top: 0 }}
    >
      <strong>{entrada.termino}. </strong>
      {entrada.definicion}
      {entrada.detalle && <span className="termino-detalle">{entrada.detalle}</span>}
    </span>
  );

  return (
    <>
      <button
        type="button"
        className="termino"
        ref={boton}
        aria-describedby={tipId}
        onPointerEnter={(e) => { if (e.pointerType === "mouse") despachar("entrar"); }}
        onPointerLeave={(e) => { if (e.pointerType === "mouse") despachar("salir"); }}
        onFocus={() => despachar("foco")}
        onBlur={() => despachar("blur")}
        onClick={(e) => { e.stopPropagation(); despachar("toque"); }}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") e.stopPropagation();
          if (e.key !== "Escape") return;
          e.preventDefault();
          e.stopPropagation();
          despachar("escape");
        }}
      >
        {children}
      </button>
      {typeof document === "undefined" ? tooltip : createPortal(tooltip, document.body)}
    </>
  );
}
