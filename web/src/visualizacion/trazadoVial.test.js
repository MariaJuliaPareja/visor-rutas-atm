import { beforeEach, describe, expect, it, vi } from "vitest";
import { consultaRuta, limpiarCache, trazarPorCalles } from "./trazadoVial.js";

const puntos = [[-16.39, -71.53], [-16.40, -71.52], [-16.39, -71.53]];
const respuestaOk = {
  code: "Ok",
  routes: [{ distance: 2350, geometry: { coordinates: [[-71.53, -16.39], [-71.525, -16.395], [-71.52, -16.40], [-71.53, -16.39]] } }],
};
const fetchCon = (cuerpo, ok = true, status = 200) => vi.fn(async () => ({ ok, status, json: async () => cuerpo }));

describe("CMP-08 trazado por calles (OSRM)", () => {
  beforeEach(() => limpiarCache());

  it("arma la consulta en orden longitud,latitud", () => {
    expect(consultaRuta(puntos, "https://osrm.local/")).toBe(
      "https://osrm.local/route/v1/driving/-71.530000,-16.390000;-71.520000,-16.400000;-71.530000,-16.390000?overview=full&geometries=geojson",
    );
  });

  it("devuelve el trazo en latitud,longitud y la distancia en km", async () => {
    const r = await trazarPorCalles(puntos, { fetchFn: fetchCon(respuestaOk) });
    expect(r.trazo[1]).toEqual([-16.395, -71.525]);
    expect(r.km).toBeCloseTo(2.35);
  });

  it("reutiliza la respuesta guardada para la misma ruta", async () => {
    const f = fetchCon(respuestaOk);
    await trazarPorCalles(puntos, { fetchFn: f });
    await trazarPorCalles(puntos, { fetchFn: f });
    expect(f).toHaveBeenCalledTimes(1);
  });

  it("lanza un error si el servicio falla o no encuentra camino", async () => {
    await expect(trazarPorCalles(puntos, { fetchFn: fetchCon({}, false, 429) })).rejects.toThrow("429");
    await expect(trazarPorCalles(puntos, { fetchFn: fetchCon({ code: "NoRoute", routes: [] }) })).rejects.toThrow("NoRoute");
  });
});
