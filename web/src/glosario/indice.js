import entradas from "./glosario.json";

export const LIMITE_DEFINICION = 240;

const INDICE = new Map(entradas.map((entrada) => [entrada.id, entrada]));

export function exigirEntrada(id, desarrollo = import.meta.env?.DEV) {
  const entrada = INDICE.get(id);
  if (!entrada && desarrollo) {
    throw new Error(`No hay entrada de glosario con id "${id}".`);
  }
  return entrada ?? null;
}

export { entradas };
