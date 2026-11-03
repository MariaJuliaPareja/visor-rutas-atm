import "fake-indexeddb/auto";
import { readFileSync } from "node:fs";
import { beforeEach, describe, expect, it } from "vitest";
import { procesarTexto } from "../carga/validacion.js";
import {
  abrir, borrarTodo, cargarLote, claveDe, contarPorFormulacion, eliminarLote, guardarLote, listarLotes,
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
