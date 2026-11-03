import { useCallback, useEffect, useState } from "react";
import PantallaCarga from "./pantallas/PantallaCarga.jsx";
import VistaPrincipal from "./pantallas/VistaPrincipal.jsx";
import { abrir, borrarTodo, cargarLote, disponible, eliminarLote, guardarLote, listarLotes } from "./persistencia/almacen.js";

// Dos pantallas (mapa de navegacion): carga y vista principal.
// Un archivo rechazado no altera lo que ya estaba cargado (RNF11).
// Cada archivo valido se guarda en IndexedDB para reabrirlo sin volver a subirlo.
export default function App() {
  const [cargado, setCargado] = useState(null); // { doc, advertencias, nombre }
  const [cargando, setCargando] = useState(true);
  const [bd, setBd] = useState(null);
  const [lotes, setLotes] = useState([]);
  const [estadoBd, setEstadoBd] = useState(disponible() ? "abriendo" : "no-disponible");

  const refrescar = useCallback(async (base) => setLotes(await listarLotes(base)), []);

  useEffect(() => {
    if (!disponible()) return;
    abrir()
      .then(async (base) => {
        setBd(base);
        setEstadoBd("lista");
        await refrescar(base);
      })
      .catch((e) => {
        console.error(e);
        setEstadoBd("no-disponible"); // p. ej., navegacion privada: el visor funciona sin historial
      });
  }, [refrescar]);

  const mostrar = (resultado) => {
    setCargado(resultado);
    setCargando(false);
  };

  async function alCargar(resultado) {
    mostrar(resultado);
    if (!bd) return;
    try {
      await guardarLote(bd, resultado.doc, resultado.nombre);
      await refrescar(bd);
    } catch (e) {
      console.error("No se pudo guardar el lote en el historial", e);
    }
  }

  if (cargando || !cargado)
    return (
      <PantallaCarga
        hayDatosPrevios={Boolean(cargado)}
        onCancelar={() => setCargando(false)}
        onCargado={alCargar}
        historial={{
          estado: estadoBd,
          lotes,
          abrir: (clave) => cargarLote(bd, clave).then(mostrar),
          eliminar: async (clave) => { await eliminarLote(bd, clave); await refrescar(bd); },
          borrarTodo: async () => { await borrarTodo(bd); await refrescar(bd); },
        }}
      />
    );
  return <VistaPrincipal {...cargado} onCargarOtro={() => setCargando(true)} />;
}
