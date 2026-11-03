import { useEffect, useMemo, useState } from "react";
import { MapContainer, Marker, Polyline, TileLayer, Tooltip, useMap } from "react-leaflet";
import L from "leaflet";
import { formato } from "../metricas/metricas.js";
import { TRAZADO_ACTIVO, trazarPorCalles } from "./trazadoVial.js";

const icono = (id, alerta) =>
  L.divIcon({
    className: "",
    html: `<div class="marcador${alerta ? " alerta" : ""}" aria-label="Cajero ${id}">${id}</div>`,
    iconSize: [30, 30],
    iconAnchor: [15, 15],
  });

export const ANCHO_PANEL = 380;

// El panel de detalle se abre SOBRE el mapa (wireframe de la practica 07). Para que no tape cajeros,
// el mapa se reencuadra dejando libre el ancho del panel; tambien al cambiar el tamano de la ventana.
function AjustarVista({ limites, panelAbierto }) {
  const mapa = useMap();
  useEffect(() => {
    const encuadrar = () => {
      mapa.invalidateSize();
      const escritorio = window.matchMedia("(min-width: 1280px)").matches;
      const derecha = panelAbierto && escritorio ? ANCHO_PANEL + 24 : 24;
      mapa.fitBounds(limites, { paddingTopLeft: [24, 24], paddingBottomRight: [derecha, 24] });
    };
    encuadrar();
    const observador = new ResizeObserver(encuadrar);
    observador.observe(mapa.getContainer());
    return () => observador.disconnect();
  }, [mapa, limites, panelAbierto]);
  return null;
}

// Pide a OSRM el trazado por calles; mientras llega, o si falla, se dibuja la linea recta entre cajeros.
function useTrazadoVial(puntos) {
  const clave = JSON.stringify(puntos);
  const [estado, setEstado] = useState({ clave: null, trazo: null, fallo: false });
  useEffect(() => {
    if (!TRAZADO_ACTIVO || !puntos || puntos.length < 2) return undefined;
    const control = new AbortController();
    trazarPorCalles(puntos, { signal: control.signal })
      .then(({ trazo }) => setEstado({ clave, trazo, fallo: false }))
      .catch((e) => { if (e.name !== "AbortError") setEstado({ clave, trazo: null, fallo: true }); });
    return () => control.abort();
  }, [clave]); // eslint-disable-line react-hooks/exhaustive-deps
  const vigente = estado.clave === clave;
  return { trazo: vigente && estado.trazo ? estado.trazo : puntos, porCalles: vigente && !!estado.trazo, fallo: vigente && estado.fallo };
}

const cerrar = (puntos) => (puntos.length > 1 ? [...puntos, puntos[0]] : puntos);

// CMP-08 Visualizacion geografica: ruta optima punteada y ruta seleccionada continua.
// Las teselas vienen de OpenStreetMap: solo revelan la zona visible, no los datos del archivo.
export default function MapaRutas({ instancia, corrida, panelAbierto = false }) {
  const coord = instancia.cajeros.map((c) => [c.latitud, c.longitud]);
  const optima = cerrar(instancia.linea_base.ruta.map((i) => coord[i]));
  const seleccionada = corrida ? cerrar(corrida.ruta.secuencia.map((i) => coord[i])) : null;
  const trazoOptima = useTrazadoVial(optima);
  const trazoSeleccionada = useTrazadoVial(seleccionada);
  const porCalles = trazoOptima.porCalles && (!seleccionada || trazoSeleccionada.porCalles);
  const fallo = trazoOptima.fallo || trazoSeleccionada.fallo;
  const metrica = instancia.matriz_distancias.metrica ?? "linea_recta";
  const sinVisitar = new Set(corrida?.noVisitados ?? []);
  const limites = useMemo(() => L.latLngBounds(instancia.cajeros.map((c) => [c.latitud, c.longitud])).pad(0.15), [instancia]);

  return (
    <div className={`mapa${panelAbierto ? " con-panel" : ""}`}>
      <div className="mapa-cabecera">
        <div>
          <h2>Mapa de rutas</h2>
          <p>{instancia.cajeros.length} cajeros · depósito en el punto 0 · distancias {metrica === "vial" ? "por calles" : "en línea recta"}</p>
        </div>
        {corrida && <p className="chip">Corrida {corrida.id_corrida} · <b>{corrida.formulacion}</b> · {formato(corrida.metricas.distancia_total)} km</p>}
      </div>
      <MapContainer bounds={limites} scrollWheelZoom className="lienzo">
        <AjustarVista limites={limites} panelAbierto={panelAbierto} />
        <TileLayer attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
        <Polyline positions={trazoOptima.trazo} pathOptions={{ color: "#5f5e5a", weight: 3, dashArray: "8 8" }} />
        {seleccionada && <Polyline positions={trazoSeleccionada.trazo} pathOptions={{ color: "#14213d", weight: 5 }} />}
        {coord.map((p, i) => (
          <Marker key={i} position={p} icon={icono(i, sinVisitar.has(i))}>
            <Tooltip>Cajero {i}{sinVisitar.has(i) ? " · no visitado" : ""}</Tooltip>
          </Marker>
        ))}
      </MapContainer>
      <ul className="leyenda">
        <li><span className="linea punteada" /> Ruta óptima (Held-Karp)</li>
        <li><span className="linea continua" /> Ruta seleccionada</li>
        {TRAZADO_ACTIVO && <li className="nota-trazado">{porCalles ? "Trazado por calles (OpenStreetMap · OSRM)"
          : fallo ? "Servicio de rutas no disponible: trazado en línea recta" : "Trazando por calles…"}</li>}
        {sinVisitar.size > 0 && <li><span className="punto-alerta" /> No visitado</li>}
      </ul>
    </div>
  );
}
