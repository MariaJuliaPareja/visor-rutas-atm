// Persistencia NoSQL documental en el navegador (IndexedDB). Implementa el modelo de la practica 06
// como colecciones de documentos: las entidades debiles 1:1 (cajeros, matriz, linea base, ruta y
// metricas) van embebidas en su documento dueno, y cada corrida es un documento propio.
//
//   instancias  clave = "<id_instancia>@<fecha_generacion>"
//               { clave, id_instancia, tipo_instancia, cajeros[], matriz_distancias, linea_base,
//                 version_esquema, fecha_generacion, nombre_archivo, guardado_en, num_corridas }
//   corridas    clave = [clave_instancia, id_corrida]
//               { clave_instancia, id_corrida, formulacion, sampler, parametros, ruta{}, metricas{} }
//               indices: por_instancia, por_formulacion ([clave_instancia, formulacion])
//   preferencias clave = nombre de la preferencia (p. ej. "supuestos_gerencia")
//               { clave, valor, actualizado_en }
//
// Los datos no salen del equipo del usuario (RNF06): IndexedDB es local al navegador y al sitio.
import { validarEstructura, validarReglas } from "../carga/validacion.js";

export const NOMBRE_BD = "rutas_atm";
export const VERSION_BD = 2; // 2: coleccion preferencias

const promesa = (solicitud) =>
  new Promise((resolver, rechazar) => {
    solicitud.onsuccess = () => resolver(solicitud.result);
    solicitud.onerror = () => rechazar(solicitud.error);
  });

const terminada = (tx) =>
  new Promise((resolver, rechazar) => {
    tx.oncomplete = () => resolver();
    tx.onerror = () => rechazar(tx.error);
    tx.onabort = () => rechazar(tx.error ?? new Error("transacción abortada"));
  });

export function disponible() {
  try {
    return typeof indexedDB !== "undefined" && indexedDB !== null;
  } catch {
    return false;
  }
}

export function abrir() {
  const solicitud = indexedDB.open(NOMBRE_BD, VERSION_BD);
  solicitud.onupgradeneeded = () => {
    const bd = solicitud.result;
    if (!bd.objectStoreNames.contains("instancias")) bd.createObjectStore("instancias", { keyPath: "clave" });
    if (!bd.objectStoreNames.contains("corridas")) {
      const corridas = bd.createObjectStore("corridas", { keyPath: ["clave_instancia", "id_corrida"] });
      corridas.createIndex("por_instancia", "clave_instancia");
      corridas.createIndex("por_formulacion", ["clave_instancia", "formulacion"]);
    }
    if (!bd.objectStoreNames.contains("preferencias")) bd.createObjectStore("preferencias", { keyPath: "clave" });
  };
  return promesa(solicitud);
}

export const claveDe = (doc) => `${doc.instancia.id_instancia}@${doc.fecha_generacion}`;

// Guarda un archivo ya validado. Instancia y corridas se escriben en UNA transaccion:
// o queda el lote completo o no queda nada. Volver a cargar el mismo archivo lo reemplaza.
export async function guardarLote(bd, doc, nombreArchivo) {
  const clave = claveDe(doc);
  const tx = bd.transaction(["instancias", "corridas"], "readwrite");
  const instancias = tx.objectStore("instancias");
  const corridas = tx.objectStore("corridas");
  const previas = await promesa(corridas.index("por_instancia").getAllKeys(clave));
  for (const k of previas) corridas.delete(k);
  instancias.put({
    clave,
    ...doc.instancia,
    version_esquema: doc.version_esquema,
    fecha_generacion: doc.fecha_generacion,
    nombre_archivo: nombreArchivo,
    guardado_en: new Date().toISOString(),
    num_corridas: doc.corridas.length,
  });
  for (const c of doc.corridas) corridas.put({ clave_instancia: clave, ...c });
  await terminada(tx);
  return clave;
}

export async function listarLotes(bd) {
  const tx = bd.transaction("instancias", "readonly");
  const todas = await promesa(tx.objectStore("instancias").getAll());
  return todas
    .map(({ clave, id_instancia, tipo_instancia, cajeros, fecha_generacion, nombre_archivo, guardado_en, num_corridas }) => ({
      clave, id_instancia, tipo_instancia, num_cajeros: cajeros.length, fecha_generacion, nombre_archivo, guardado_en, num_corridas,
    }))
    .sort((a, b) => b.guardado_en.localeCompare(a.guardado_en));
}

// Reconstruye el archivo de intercambio desde las colecciones y lo vuelve a validar:
// lo guardado en el navegador no se da por confiable (pudo alterarse o corromperse).
export async function cargarLote(bd, clave) {
  const tx = bd.transaction(["instancias", "corridas"], "readonly");
  const inst = await promesa(tx.objectStore("instancias").get(clave));
  if (!inst) throw new Error("El lote ya no existe en este navegador.");
  const corridas = await promesa(tx.objectStore("corridas").index("por_instancia").getAll(clave));
  // Todo lo que no es metadato de almacenamiento es la instancia original, incluidos los campos
  // opcionales (matriz_tiempos, fuente): antes se perdian al reabrir desde el historial.
  const { clave: _c, version_esquema, fecha_generacion, nombre_archivo, guardado_en: _g, num_corridas: _n, ...instancia } = inst;
  const doc = {
    version_esquema,
    fecha_generacion,
    instancia,
    corridas: corridas
      .sort((a, b) => a.id_corrida - b.id_corrida)
      .map(({ clave_instancia: _, ...c }) => c),
  };
  validarEstructura(doc);
  const advertencias = validarReglas(doc);
  return { doc, advertencias, nombre: nombre_archivo };
}

export async function contarPorFormulacion(bd, clave, formulacion) {
  const tx = bd.transaction("corridas", "readonly");
  return promesa(tx.objectStore("corridas").index("por_formulacion").count([clave, formulacion]));
}

export async function eliminarLote(bd, clave) {
  const tx = bd.transaction(["instancias", "corridas"], "readwrite");
  const corridas = tx.objectStore("corridas");
  const claves = await promesa(corridas.index("por_instancia").getAllKeys(clave));
  for (const k of claves) corridas.delete(k);
  tx.objectStore("instancias").delete(clave);
  await terminada(tx);
}

export async function borrarTodo(bd) {
  const tx = bd.transaction(["instancias", "corridas", "preferencias"], "readwrite");
  tx.objectStore("instancias").clear();
  tx.objectStore("corridas").clear();
  tx.objectStore("preferencias").clear();
  await terminada(tx);
}

// Preferencias del usuario (p. ej. los supuestos del resumen para gerencia).
export async function guardarPreferencia(bd, clave, valor) {
  const tx = bd.transaction("preferencias", "readwrite");
  tx.objectStore("preferencias").put({ clave, valor, actualizado_en: new Date().toISOString() });
  await terminada(tx);
}

export async function leerPreferencia(bd, clave) {
  const tx = bd.transaction("preferencias", "readonly");
  const doc = await promesa(tx.objectStore("preferencias").get(clave));
  return doc?.valor ?? null;
}
