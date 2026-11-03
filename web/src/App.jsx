import { useState } from "react";
import PantallaCarga from "./pantallas/PantallaCarga.jsx";
import VistaPrincipal from "./pantallas/VistaPrincipal.jsx";

// Dos pantallas (mapa de navegacion): carga y vista principal.
// Un archivo rechazado no altera lo que ya estaba cargado (RNF11).
export default function App() {
  const [cargado, setCargado] = useState(null); // { doc, advertencias, nombre }
  const [cargando, setCargando] = useState(!cargado);

  if (cargando || !cargado)
    return (
      <PantallaCarga
        hayDatosPrevios={Boolean(cargado)}
        onCancelar={() => setCargando(false)}
        onCargado={(resultado) => {
          setCargado(resultado);
          setCargando(false);
        }}
      />
    );
  return <VistaPrincipal {...cargado} onCargarOtro={() => setCargando(true)} />;
}
