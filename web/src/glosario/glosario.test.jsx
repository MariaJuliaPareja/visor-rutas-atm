import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { entradas, exigirEntrada, LIMITE_DEFINICION } from "./indice.js";
import Termino, { estaVisible, reducir } from "./Termino.jsx";

const BASE = { sobre: false, foco: false, anclado: false, cerrado: false };
const SRC = fileURLToPath(new URL("..", import.meta.url));

function archivosJs(directorio) {
  return readdirSync(directorio).flatMap((nombre) => {
    const ruta = join(directorio, nombre);
    if (statSync(ruta).isDirectory()) return archivosJs(ruta);
    return /\.(js|jsx)$/.test(nombre) ? [ruta] : [];
  });
}

function idsUsados() {
  const ids = new Set();
  for (const ruta of archivosJs(SRC)) {
    const texto = readFileSync(ruta, "utf8");
    for (const etiqueta of texto.matchAll(/<Termino\b[^>]*>/g)) {
      for (const literal of etiqueta[0].matchAll(/"([a-z0-9-]+)"/g)) ids.add(literal[1]);
    }
  }
  return ids;
}

describe("glosario", () => {
  it("tiene ids unicos y definiciones dentro del limite", () => {
    const ids = entradas.map((entrada) => entrada.id);
    expect(new Set(ids).size).toBe(ids.length);
    for (const entrada of entradas) {
      expect(entrada.termino.trim().length).toBeGreaterThan(0);
      expect(entrada.definicion.trim().length).toBeGreaterThan(0);
      expect(entrada.definicion.length).toBeLessThanOrEqual(LIMITE_DEFINICION);
    }
  });

  it("todo Termino usado en el codigo existe en el glosario", () => {
    const usados = idsUsados();
    expect(usados.size).toBeGreaterThan(0);
    for (const id of usados) expect(exigirEntrada(id, false)).not.toBeNull();
  });

  it("en desarrollo un id desconocido falla y en produccion no", () => {
    expect(() => exigirEntrada("no-existe", true)).toThrow(/no-existe/);
    expect(exigirEntrada("no-existe", false)).toBeNull();
  });
});

describe("Termino", () => {
  it("abre con foco y con clic, y cierra con Escape", () => {
    expect(estaVisible(reducir(BASE, "foco"))).toBe(true);
    const abierto = reducir(BASE, "toque");
    expect(estaVisible(abierto)).toBe(true);
    expect(estaVisible(reducir(abierto, "toque"))).toBe(false);
    expect(estaVisible(reducir(reducir(BASE, "foco"), "escape"))).toBe(false);
  });

  it("relaciona el boton con el tooltip por aria-describedby", () => {
    const html = renderToStaticMarkup(<Termino id="factibilidad">Factible</Termino>);
    const descrito = html.match(/aria-describedby="([^"]+)"/);
    expect(descrito).not.toBeNull();
    expect(html).toContain(`id="${descrito[1]}"`);
    expect(html).toContain('role="tooltip"');
  });
});
