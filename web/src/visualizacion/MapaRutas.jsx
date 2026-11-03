import { useEffect, useMemo } from "react";
import { MapContainer, Marker, Polyline, TileLayer, Tooltip, useMap } from "react-leaflet";
import L from "leaflet";

const icono = (id, alerta) =>
  L.divIcon({
    className: "",
    html: `<div class="marcador${alerta ? " alerta" : ""}" aria-label="Cajero ${id}">${id}</div>`,
    iconSize: [30, 30],
    iconAnchor: [15, 15],
  });

// Cuando el panel de detalle cambia el ancho del mapa, Leaflet necesita recalcular su tamano
// y volver a encuadrar los cajeros; si no, el panel deja cajeros fuera de la vista.
function AjustarVista({ limites }) {
  const mapa = useMap();
  useEffect(() => {
    const contenedor = mapa.getContainer();
    const observador = new ResizeObserver(() => {
      mapa.invalidateSize();
      mapa.fitBounds(limites);
    });
    observador.observe(contenedor);
    return () => observador.disconnect();
  }, [mapa, limites]);
  return null;
}

const cerrar = (puntos) => (puntos.length > 1 ? [...puntos, puntos[0]] : puntos);

// CMP-08 Visualizacion geografica: ruta optima punteada y ruta seleccionada continua.
// Las teselas vienen de OpenStreetMap: solo revelan la zona visible, no los datos del archivo.
export default function MapaRutas({ instancia, corrida }) {
  const coord = instancia.cajeros.map((c) => [c.latitud, c.longitud]);
  const optima = cerrar(instancia.linea_base.ruta.map((i) => coord[i]));
  const seleccionada = corrida ? cerrar(corrida.ruta.secuencia.map((i) => coord[i])) : null;
  const sinVisitar = new Set(corrida?.noVisitados ?? []);
  const limites = useMemo(() => L.latLngBounds(instancia.cajeros.map((c) => [c.latitud, c.longitud])).pad(0.15), [instancia]);

  return (
    <div className="mapa">
      <div className="mapa-cabecera">
        <h2>Mapa de rutas</h2>
        <p>{instancia.cajeros.length} cajeros · depósito en el punto 0{corrida && ` · Corrida ${corrida.id_corrida} · ${corrida.formulacion}`}</p>
      </div>
      <MapContainer bounds={limites} scrollWheelZoom className="lienzo">
        <AjustarVista limites={limites} />
        <TileLayer attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
        <Polyline positions={optima} pathOptions={{ color: "#5f5e5a", weight: 3, dashArray: "8 8" }} />
        {seleccionada && <Polyline positions={seleccionada} pathOptions={{ color: "#14213d", weight: 5 }} />}
        {coord.map((p, i) => (
          <Marker key={i} position={p} icon={icono(i, sinVisitar.has(i))}>
            <Tooltip>Cajero {i}{sinVisitar.has(i) ? " · no visitado" : ""}</Tooltip>
          </Marker>
        ))}
      </MapContainer>
      <ul className="leyenda">
        <li><span className="linea punteada" /> Ruta óptima (Held-Karp)</li>
        <li><span className="linea continua" /> Ruta seleccionada</li>
        {sinVisitar.size > 0 && <li><span className="punto-alerta" /> No visitado</li>}
      </ul>
    </div>
  );
}
