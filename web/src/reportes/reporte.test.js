import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { procesarTexto } from "../carga/validacion.js";
import { calcularMetricas } from "../metricas/metricas.js";
import { NOTA_INFACTIBLE, contenidoReporte, generarPdf, nombreReporte } from "./reporte.js";

const texto = readFileSync(new URL("../../../ejemplos/corridas_ejemplo.json", import.meta.url), "utf8");

describe("CMP-09 reporte consolidado", () => {
  const { doc, advertencias } = procesarTexto(texto);
  const metricas = calcularMetricas(doc);
  const contenido = contenidoReporte(doc, metricas, advertencias);

  it("usa las mismas cifras que la pantalla", () => {
    expect(contenido.corridas).toHaveLength(doc.corridas.length);
    const gpsResumen = contenido.resumen.find((f) => f[0] === "GPS");
    expect(gpsResumen[1]).toBe(`${metricas.resumen.GPS.factibles} / ${metricas.resumen.GPS.total}`);
  });

  it("marca las rutas infactibles con gap no comparable y nota explicativa", () => {
    const infactibles = contenido.corridas.filter((c) => c[6] === "Infactible");
    expect(infactibles.length).toBe(contenido.infactibles);
    expect(infactibles.every((c) => c[4] === "No comparable")).toBe(true);
    expect(contenido.notas).toContain(NOTA_INFACTIBLE);
  });

  it("incluye las advertencias de verificacion", () => {
    const alterado = JSON.parse(texto);
    alterado.corridas[1].metricas.distancia_total += 3;
    const r = procesarTexto(JSON.stringify(alterado));
    const c = contenidoReporte(r.doc, calcularMetricas(r.doc), r.advertencias);
    expect(c.notas.some((n) => n.includes("corrida 2"))).toBe(true);
  });

  it("genera un PDF con el nombre de la instancia", () => {
    const pdf = generarPdf(contenido);
    expect(pdf.output("arraybuffer").byteLength).toBeGreaterThan(1000);
    expect(nombreReporte(doc)).toBe("reporte_instancia1.pdf");
  });
});
