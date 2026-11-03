import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// El esquema JSON vive en ../schema y lo comparten el pipeline y el visor:
// se permite al servidor de desarrollo leer la carpeta superior del repositorio.
export default defineConfig({
  plugins: [react()],
  server: { port: 5173, fs: { allow: [".."] } },
  test: { environment: "node" },
});
