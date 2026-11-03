import { describe, expect, it } from "vitest";
import { SUPUESTOS, evaluarRuta, resumenGerencial } from "./metricas.js";

// 4 nodos: la ruta habitual 0-1-2-3 mide 4+5+4+5 = 18; la propuesta 0-2-1-3 mide 3+5+3+5 = 16.
const D = [[0, 4, 3, 5], [4, 0, 5, 3], [3, 5, 0, 4], [5, 3, 4, 0]];
const doc = (corridas, tiempos) => ({
  instancia: {
    cajeros: [0, 1, 2, 3].map((i) => ({ id_cajero: i, latitud: 0, longitud: 0 })),
    matriz_distancias: { unidad: "km", distancias: D },
    ...(tiempos ? { matriz_tiempos: { unidad: "min", tiempos } } : {}),
    linea_base: { dist_optima: 14, ruta: [0, 1, 3, 2] },
  },
  corridas,
});
const corrida = (id, secuencia, factible = true) =>
  ({ id_corrida: id, formulacion: "QUBO", sampler: "ibm", ruta: { secuencia, factible } });

describe("CMP-07 resumen para gerencia", () => {
  it("evalua rutas cerradas", () => {
    expect(evaluarRuta([0, 1, 2, 3], D)).toBe(18);
  });

  it("compara la mejor corrida factible con la ruta habitual y la traduce a soles y CO2", () => {
    const r = resumenGerencial(doc([corrida(1, [0, 2, 1, 3]), corrida(2, [0, 0, 1, 2], false)]), {
      corridas: [corrida(1, [0, 2, 1, 3]), corrida(2, [0, 0, 1, 2], false)],
    });
    expect(r.porRecorrido.km).toBeCloseTo(2);
    expect(r.porRecorrido.soles).toBeCloseTo((2 / SUPUESTOS.rendimiento_km_l) * SUPUESTOS.precio_soles_l);
    expect(r.porAnio.km).toBeCloseTo(2 * SUPUESTOS.recorridos_anio);
    expect(r.propuesta.origen).toContain("IBM Quantum");
    expect(r.alcanzaOptimo).toBe(false);
    expect(r.tiempoEstimado).toBe(true);
  });

  it("usa los tiempos por calles cuando el archivo los trae", () => {
    const T = D.map((fila) => fila.map((x) => x * 2));
    const c = [corrida(1, [0, 2, 1, 3])];
    expect(resumenGerencial(doc(c, T), { corridas: c }).porRecorrido.min).toBeCloseTo(4);
  });

  it("sin rutas factibles usa el optimo clasico y lo dice", () => {
    const c = [corrida(1, [0, 0, 1, 2], false)];
    const r = resumenGerencial(doc(c), { corridas: c });
    expect(r.propuesta.origen).toContain("Held-Karp");
    expect(r.alcanzaOptimo).toBe(true);
  });
});
