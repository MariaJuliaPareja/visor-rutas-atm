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
  x === null || x === undefined ? "—" : x.toLocaleString("es-PE", { minimumFractionDigits: decimales, maximumFractionDigits: decimales });
