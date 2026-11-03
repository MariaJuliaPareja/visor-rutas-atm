// CMP-08 Visualizacion geografica: trazado de una ruta por las calles de OpenStreetMap con OSRM.
// Solo se envian las coordenadas de los cajeros (sinteticas) al servicio de rutas; el resto del archivo
// sigue sin salir del navegador. VITE_OSRM_URL apunta a un OSRM propio, o "off" para no trazar por calles.

const URL_POR_DEFECTO = "https://router.project-osrm.org";
export const URL_OSRM = (import.meta.env?.VITE_OSRM_URL ?? URL_POR_DEFECTO).trim() || URL_POR_DEFECTO;
export const TRAZADO_ACTIVO = URL_OSRM.toLowerCase() !== "off";

const cache = new Map();

export const consultaRuta = (puntos, url = URL_OSRM) => {
  // OSRM espera longitud,latitud
  const coords = puntos.map(([lat, lon]) => `${lon.toFixed(6)},${lat.toFixed(6)}`).join(";");
  return `${url.replace(/\/$/, "")}/route/v1/driving/${coords}?overview=full&geometries=geojson`;
};

// puntos: [[lat, lon], ...] en el orden de la ruta (ya cerrada). Devuelve { trazo, km } o lanza un error.
export async function trazarPorCalles(puntos, { url = URL_OSRM, fetchFn = fetch, signal } = {}) {
  if (puntos.length < 2) return { trazo: puntos, km: 0 };
  const consulta = consultaRuta(puntos, url);
  if (cache.has(consulta)) return cache.get(consulta);
  const respuesta = await fetchFn(consulta, { signal });
  if (!respuesta.ok) throw new Error(`El servicio de rutas respondió ${respuesta.status}`);
  const datos = await respuesta.json();
  const ruta = datos?.routes?.[0];
  if (datos?.code !== "Ok" || !ruta?.geometry?.coordinates?.length) {
    throw new Error(`El servicio de rutas no encontró un camino (${datos?.code ?? "sin código"})`);
  }
  const resultado = { trazo: ruta.geometry.coordinates.map(([lon, lat]) => [lat, lon]), km: ruta.distance / 1000 };
  cache.set(consulta, resultado);
  return resultado;
}

export const limpiarCache = () => cache.clear();
