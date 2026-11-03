// CMP-06 Carga y validacion. Aplica el mismo contrato que el pipeline (schema/) en dos niveles,
// mas la migracion de versiones. Todo ocurre en el navegador: el archivo no se envia a ningun servidor (RNF06).
import Ajv2020 from "ajv/dist/2020.js";
import addFormats from "ajv-formats";
import esquema from "../../../schema/esquema_archivo_intercambio.schema.json";

export const VERSION_ESQUEMA = "1.1";
export const LIMITE_BYTES = 1024 * 1024; // 1 MB: una instancia de 100 cajeros con decenas de corridas ocupa menos

const ajv = new Ajv2020({ allErrors: true, strict: false, verbose: true });
addFormats(ajv);
const validarEsquema = ajv.compile(esquema);

const MIGRACIONES = {
  "1.0": (doc) => ({
    ...doc,
    version_esquema: "1.1",
    corridas: doc.corridas.map((c) => ({ sampler: "qpu", ...c })),
  }),
};

export class ErrorDeCarga extends Error {
  constructor(paso, titulo, detalles = []) {
    super(titulo);
    this.paso = paso;
    this.detalles = detalles;
  }
}

export const PASOS = [
  "Formato .json",
  "Tamaño del archivo",
  "Lectura del archivo",
  "Versión del esquema",
  "Estructura del esquema",
  "Reglas entre entidades",
];

export function validarArchivo(nombre, tamano) {
  if (!nombre.toLowerCase().endsWith(".json"))
    throw new ErrorDeCarga(0, "Solo se aceptan archivos .json generados por el pipeline.");
  if (tamano > LIMITE_BYTES)
    throw new ErrorDeCarga(1, `El archivo supera el tamaño máximo de ${LIMITE_BYTES / 1024 / 1024} MB.`);
}

export function leer(texto) {
  try {
    return JSON.parse(texto);
  } catch {
    throw new ErrorDeCarga(2, "No se pudo leer el archivo: el JSON está dañado.");
  }
}

export function migrar(doc) {
  let actual = doc;
  while (actual.version_esquema !== VERSION_ESQUEMA) {
    const migracion = MIGRACIONES[actual.version_esquema];
    if (!migracion)
      throw new ErrorDeCarga(3, `Versión del esquema ${actual.version_esquema ?? "ausente"} no compatible. Versión esperada: 1.x.`);
    actual = migracion(actual);
  }
  return actual;
}

export function validarEstructura(doc) {
  if (validarEsquema(doc)) return;
  const detalles = validarEsquema.errors.map((e) => `${e.instancePath.slice(1) || "(raíz)"}: ${mensajeEnEspanol(e)}`);
  throw new ErrorDeCarga(4, "El archivo no cumple la estructura esperada.", detalles);
}

function mensajeEnEspanol(e) {
  const p = e.params;
  switch (e.keyword) {
    case "enum": return `${JSON.stringify(e.data)} no es un valor permitido (valores válidos: ${p.allowedValues.join(", ")})`;
    case "type": return `debe ser de tipo ${p.type}`;
    case "required": return `falta el campo obligatorio '${p.missingProperty}'`;
    case "additionalProperties": return `campo no definido en el esquema: '${p.additionalProperty}'`;
    case "minimum": case "maximum": case "exclusiveMinimum": case "exclusiveMaximum":
      return `debe ser ${p.comparison} ${p.limit}`;
    case "minItems": return `debe tener al menos ${p.limit} elementos`;
    case "maxItems": return `debe tener como máximo ${p.limit} elementos`;
    case "uniqueItems": return `tiene elementos repetidos (posiciones ${p.j} y ${p.i})`;
    case "pattern": return "no tiene el formato esperado";
    case "format": return `no es un valor ${p.format} válido`;
    default: return e.message;
  }
}

export function validarReglas(doc, toleranciaKm = 0.01) {
  const errores = [];
  const advertencias = [];
  const { cajeros, matriz_distancias, linea_base } = doc.instancia;
  const n = cajeros.length;
  const d = matriz_distancias.distancias;
  const esPermutacion = (s) => s.length === n && [...s].sort((a, b) => a - b).every((v, i) => v === i);

  if (!cajeros.every((c, i) => c.id_cajero === i)) errores.push("id_cajero debe ser consecutivo de 0 a n-1 y en orden");
  if (d.length !== n || d.some((fila) => fila.length !== n)) {
    errores.push(`la matriz de distancias debe ser de ${n} x ${n}`);
    throw new ErrorDeCarga(5, `Se encontraron ${errores.length} problemas en el archivo:`, errores);
  }
  if (d.some((fila, i) => fila[i] !== 0)) errores.push("la diagonal de la matriz de distancias debe ser 0");
  if (!esPermutacion(linea_base.ruta)) errores.push("la ruta de la línea base debe visitar cada cajero exactamente una vez");
  const ids = doc.corridas.map((c) => c.id_corrida);
  if (new Set(ids).size !== ids.length) errores.push("id_corrida debe ser único");

  for (const c of doc.corridas) {
    const s = c.ruta.secuencia;
    if (s.some((i) => i >= n)) {
      errores.push(`Corrida ${c.id_corrida}: la ruta referencia a un cajero inexistente`);
      continue;
    }
    if (c.ruta.factible !== esPermutacion(s)) errores.push(`Corrida ${c.id_corrida}: el campo 'factible' no coincide con la secuencia`);
    if (c.sampler === "qpu" && c.metricas.tiempo_anneal === null)
      errores.push(`Corrida ${c.id_corrida}: una corrida en QPU debe registrar tiempo_anneal`);
    if (Math.abs(distanciaRuta(s, d) - c.metricas.distancia_total) > toleranciaKm)
      advertencias.push({ id_corrida: c.id_corrida, mensaje: `En la corrida ${c.id_corrida}, la distancia almacenada no coincide con la recalculada a partir de la matriz de distancias.` });
  }
  if (errores.length) throw new ErrorDeCarga(5, `Se encontraron ${errores.length} problemas en el archivo:`, errores);
  return advertencias;
}

export function distanciaRuta(s, d) {
  if (s.length < 2) return 0;
  return s.reduce((acc, v, k) => acc + d[v][s[(k + 1) % s.length]], 0);
}

// Valida un texto ya leido; devuelve { doc, advertencias } o lanza ErrorDeCarga (todo o nada).
export function procesarTexto(texto) {
  const doc = migrar(leer(texto));
  validarEstructura(doc);
  const advertencias = validarReglas(doc);
  return { doc, advertencias };
}
