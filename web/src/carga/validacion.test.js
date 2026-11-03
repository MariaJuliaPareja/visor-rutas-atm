import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { ErrorDeCarga, VERSION_ESQUEMA, procesarTexto, validarArchivo } from "./validacion.js";
import { calcularMetricas } from "../metricas/metricas.js";

const ejemplo = readFileSync(new URL("../../../ejemplos/corridas_ejemplo.json", import.meta.url), "utf8");
const doc = () => JSON.parse(ejemplo);
const rechazoEn = (texto) => {
  try {
    procesarTexto(texto);
  } catch (e) {
    expect(e).toBeInstanceOf(ErrorDeCarga);
    return e;
  }
  throw new Error("se esperaba un rechazo");
};

describe("CMP-06 validacion compartida con el pipeline", () => {
  it("acepta el archivo generado por el pipeline", () => {
    const { advertencias } = procesarTexto(ejemplo);
    expect(advertencias).toEqual([]);
  });

  it("rechaza archivos que no son .json o son demasiado grandes", () => {
    expect(() => validarArchivo("corridas.pkl", 10)).toThrow(/Solo se aceptan/);
    expect(() => validarArchivo("corridas.json", 5 * 1024 * 1024)).toThrow(/tamaño máximo/);
  });

  it("rechaza JSON dañado en el paso de lectura", () => {
    expect(rechazoEn("{no es json").paso).toBe(2);
  });

  it("rechaza una version sin migracion", () => {
    expect(rechazoEn(JSON.stringify({ ...doc(), version_esquema: "0.9" })).paso).toBe(3);
  });

  it("migra la version 1.0 hasta la actual", () => {
    const viejo = doc();
    viejo.version_esquema = "1.0";
    viejo.corridas.forEach((c) => { delete c.sampler; c.metricas.tiempo_anneal = 20; });
    const { doc: migrado } = procesarTexto(JSON.stringify(viejo));
    expect(migrado.version_esquema).toBe(VERSION_ESQUEMA);
    expect(migrado.corridas.every((c) => c.sampler === "qpu")).toBe(true);
  });

  it("indica el campo exacto cuando falla la estructura", () => {
    const d = doc();
    d.corridas[0].formulacion = "GPU";
    const e = rechazoEn(JSON.stringify(d));
    expect(e.paso).toBe(4);
    expect(e.detalles.join()).toMatch(/corridas\/0\/formulacion/);
  });

  it("rechaza referencias a cajeros inexistentes y factibilidad incoherente", () => {
    const d = doc();
    d.corridas[0].ruta.secuencia = [0, 1, 7];
    d.corridas[1].ruta.factible = !d.corridas[1].ruta.factible;
    const e = rechazoEn(JSON.stringify(d));
    expect(e.paso).toBe(5);
    expect(e.detalles).toHaveLength(2);
  });

  it("advierte, sin bloquear, si la distancia almacenada no coincide", () => {
    const d = doc();
    d.corridas[1].metricas.distancia_total += 3;
    expect(procesarTexto(JSON.stringify(d)).advertencias).toHaveLength(1);
  });
});

describe("CMP-07 metricas", () => {
  it("excluye las rutas infactibles del resumen y no les asigna gap", () => {
    const { corridas, resumen } = calcularMetricas(doc());
    const infactibles = corridas.filter((c) => !c.ruta.factible);
    expect(infactibles.length).toBeGreaterThan(0);
    expect(infactibles.every((c) => c.gap === null)).toBe(true);
    const gps = corridas.filter((c) => c.formulacion === "GPS");
    expect(resumen.GPS.factibles).toBe(gps.filter((c) => c.ruta.factible).length);
    expect(resumen.GPS.ahorroVsGps).toBe(0);
  });

  it("marca como no calculable el ahorro si falta una formulacion", () => {
    const d = doc();
    d.corridas = d.corridas.filter((c) => c.formulacion === "GPS");
    const { resumen } = calcularMetricas(d);
    expect(resumen.QUBO.total).toBe(0);
    expect(resumen.QUBO.ahorroVsGps).toBeNull();
    expect(resumen.GPS.motivoAhorro).toMatch(/ambas formulaciones/);
  });
});
