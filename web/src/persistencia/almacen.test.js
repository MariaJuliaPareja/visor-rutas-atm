import "fake-indexeddb/auto";
import { readFileSync } from "node:fs";
import { beforeEach, describe, expect, it } from "vitest";
import { procesarTexto } from "../carga/validacion.js";
import {
  abrir, borrarTodo, cargarLote, claveDe, contarPorFormulacion, eliminarLote, guardarLote, guardarPreferencia,
  leerPreferencia, listarLotes,
} from "./almacen.js";

const texto = readFileSync(new URL("../../../ejemplos/corridas_ejemplo.json", import.meta.url), "utf8");
const { doc } = procesarTexto(texto);
let bd;

beforeEach(async () => {
  bd = await abrir();
  await borrarTodo(bd);
});

describe("persistencia NoSQL en IndexedDB", () => {
  it("guarda un lote y lo reconstruye identico al archivo original", async () => {
    const clave = await guardarLote(bd, doc, "corridas_ejemplo.json");
    expect(clave).toBe(claveDe(doc));
    const recuperado = await cargarLote(bd, clave);
    expect(recuperado.doc).toEqual(doc);
    expect(recuperado.nombre).toBe("corridas_ejemplo.json");
  });

  it("lista los lotes con su resumen", async () => {
    await guardarLote(bd, doc, "a.json");
    const [lote] = await listarLotes(bd);
    expect(lote).toMatchObject({ id_instancia: 1, num_cajeros: doc.instancia.cajeros.length, num_corridas: doc.corridas.length });
  });

  it("volver a cargar el mismo archivo lo reemplaza sin duplicar corridas", async () => {
    await guardarLote(bd, doc, "a.json");
    const recortado = { ...doc, corridas: doc.corridas.slice(0, 2) };
    const clave = await guardarLote(bd, recortado, "a.json");
    expect(await listarLotes(bd)).toHaveLength(1);
    expect((await cargarLote(bd, clave)).doc.corridas).toHaveLength(2);
  });

  it("consulta corridas por formulacion con el indice", async () => {
    const clave = await guardarLote(bd, doc, "a.json");
    const gps = doc.corridas.filter((c) => c.formulacion === "GPS").length;
    expect(await contarPorFormulacion(bd, clave, "GPS")).toBe(gps);
  });

  it("elimina un lote con todas sus corridas", async () => {
    const clave = await guardarLote(bd, doc, "a.json");
    await eliminarLote(bd, clave);
    expect(await listarLotes(bd)).toEqual([]);
    await expect(cargarLote(bd, clave)).rejects.toThrow(/ya no existe/);
  });

  it("revalida al cargar: un documento alterado en el navegador se rechaza", async () => {
    const clave = await guardarLote(bd, doc, "a.json");
    const tx = bd.transaction("corridas", "readwrite");
    tx.objectStore("corridas").put({ clave_instancia: clave, ...doc.corridas[0], formulacion: "GPU" });
    await new Promise((r) => { tx.oncomplete = r; });
    await expect(cargarLote(bd, clave)).rejects.toThrow(/estructura/);
  });
});

describe("persistencia de campos opcionales y preferencias", () => {
  it("conserva matriz_tiempos, fuente y nombres al reabrir desde el historial", async () => {
    const n = doc.instancia.cajeros.length;
    const conExtras = structuredClone(doc);
    conExtras.instancia.matriz_tiempos = { unidad: "min", tiempos: doc.instancia.matriz_distancias.distancias.map((f) => f.map((x) => x * 3)) };
    conExtras.instancia.fuente = { tipo: "osm", entidad: "BBVA", atribucion: "OSM" };
    conExtras.instancia.cajeros[0] = { ...conExtras.instancia.cajeros[0], nombre: "Base de operaciones", rol: "deposito" };
    const clave = await guardarLote(bd, conExtras, "real.json");
    const { doc: recuperado } = await cargarLote(bd, clave);
    expect(recuperado).toEqual(conExtras);
    expect(recuperado.instancia.matriz_tiempos.tiempos).toHaveLength(n);
  });

  it("guarda y lee los supuestos del resumen para gerencia", async () => {
    expect(await leerPreferencia(bd, "supuestos_gerencia")).toBeNull();
    await guardarPreferencia(bd, "supuestos_gerencia", { precio_soles_l: 4.5 });
    expect(await leerPreferencia(bd, "supuestos_gerencia")).toEqual({ precio_soles_l: 4.5 });
  });
});
