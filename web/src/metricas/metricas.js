// CMP-07 Calculo de metricas. Se calculan una sola vez y alimentan tarjetas, tabla y mapa.
// Regla de diseno (TC-04): el gap de una ruta infactible no es comparable y no entra en el resumen.

export const FORMULACIONES = ["GPS", "QUBO"];

export function noVisitados(secuencia, n) {
  const vistos = new Set(secuencia);
  return [...Array(n).keys()].filter((i) => !vistos.has(i));
}

export function repetidos(secuencia) {
  return secuencia.filter((v, i) => secuencia.indexOf(v) !== i);
}

export function calcularMetricas(doc) {
  const opt = doc.instancia.linea_base.dist_optima;
  const n = doc.instancia.cajeros.length;

  const corridas = doc.corridas.map((c) => ({
    ...c,
    gap: c.ruta.factible ? ((c.metricas.distancia_total - opt) / opt) * 100 : null,
    noVisitados: noVisitados(c.ruta.secuencia, n),
    repetidos: repetidos(c.ruta.secuencia),
  }));

  const resumen = {};
  for (const f of FORMULACIONES) {
    const propias = corridas.filter((c) => c.formulacion === f);
    const factibles = propias.filter((c) => c.ruta.factible);
    const mejor = factibles.length ? Math.min(...factibles.map((c) => c.metricas.distancia_total)) : null;
    resumen[f] = {
      total: propias.length,
      factibles: factibles.length,
      mejorDistancia: mejor,
      mejorGap: mejor === null ? null : ((mejor - opt) / opt) * 100,
    };
  }

  const gps = resumen.GPS.mejorDistancia;
  for (const f of FORMULACIONES) {
    const r = resumen[f];
    r.ahorroVsGps = gps === null || r.mejorDistancia === null ? null : ((gps - r.mejorDistancia) / gps) * 100;
    r.motivoAhorro = resumen.GPS.total === 0 || resumen.QUBO.total === 0
      ? "Se necesitan corridas de ambas formulaciones."
      : gps === null || r.mejorDistancia === null ? "Se necesitan rutas factibles de ambas formulaciones." : null;
  }
  return { corridas, resumen, optima: opt };
}

export const formato = (x, decimales = 2) =>
  x === null || x === undefined ? "—" : x.toLocaleString("es-ES", { minimumFractionDigits: decimales, maximumFractionDigits: decimales });

// ---------------------------------------------------------------------------------------------
// Resumen para gerencia (DEC-09): traduce la mejor ruta obtenida a km, minutos, soles y CO2,
// frente a la "ruta habitual" (visitar los cajeros en el orden de la planilla: 0, 1, 2, ...).
// Los supuestos economicos son editables en pantalla y salen tal cual en el reporte.
export const SUPUESTOS = {
  rendimiento_km_l: 8, // km por litro del vehiculo blindado
  precio_soles_l: 4.3, // S/ por litro de diesel
  co2_kg_l: 2.68, // kg de CO2 por litro de diesel quemado
  velocidad_kmh: 20, // solo si el archivo no trae tiempos de manejo por calles
  recorridos_anio: 300, // recorridos de esta ruta al anio
};

export const NOMBRE_SAMPLER = { simulado: "recocido simulado", qpu: "D-Wave Leap", ibm: "IBM Quantum" };

export function evaluarRuta(secuencia, matriz) {
  if (secuencia.length < 2) return 0;
  return secuencia.reduce((s, v, k) => s + matriz[v][secuencia[(k + 1) % secuencia.length]], 0);
}

export function resumenGerencial(doc, { corridas }, supuestos = SUPUESTOS) {
  const inst = doc.instancia;
  const n = inst.cajeros.length;
  const D = inst.matriz_distancias.distancias;
  const T = inst.matriz_tiempos?.tiempos ?? null;
  const minutos = (sec, km) => (T ? evaluarRuta(sec, T) : (km / supuestos.velocidad_kmh) * 60);

  const habitualSec = [...Array(n).keys()];
  const habitualKm = evaluarRuta(habitualSec, D);
  const factibles = corridas.filter((c) => c.ruta.factible);
  const mejor = factibles.length
    ? factibles.reduce((a, b) => (evaluarRuta(b.ruta.secuencia, D) < evaluarRuta(a.ruta.secuencia, D) ? b : a))
    : null;
  const propuestaSec = mejor ? mejor.ruta.secuencia : inst.linea_base.ruta;
  const propuestaKm = evaluarRuta(propuestaSec, D);
  const origen = mejor
    ? `corrida ${mejor.id_corrida} · ${mejor.formulacion} · ${NOMBRE_SAMPLER[mejor.sampler] ?? mejor.sampler}`
    : "óptimo clásico (Held-Karp): ninguna corrida dio una ruta factible";

  const km = habitualKm - propuestaKm;
  const min = minutos(habitualSec, habitualKm) - minutos(propuestaSec, propuestaKm);
  const litros = km / supuestos.rendimiento_km_l;
  const soles = litros * supuestos.precio_soles_l;
  const co2 = litros * supuestos.co2_kg_l;
  const anio = supuestos.recorridos_anio;
  const optimoKm = inst.linea_base.dist_optima;

  return {
    habitual: { secuencia: habitualSec, km: habitualKm, min: minutos(habitualSec, habitualKm) },
    propuesta: { secuencia: propuestaSec, km: propuestaKm, min: minutos(propuestaSec, propuestaKm), origen },
    porRecorrido: { km, min, soles, co2, pct: habitualKm > 0 ? (km / habitualKm) * 100 : 0 },
    porAnio: { km: km * anio, horas: (min * anio) / 60, soles: soles * anio, co2: co2 * anio },
    alcanzaOptimo: Math.abs(propuestaKm - optimoKm) < 0.01,
    optimoKm,
    tiempoEstimado: !T,
    sinAhorro: km <= 0.005,
    supuestos,
  };
}
