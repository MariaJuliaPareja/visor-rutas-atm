// CMP-09 Generacion de reportes (RF05). Usa las mismas cifras de CMP-07 que la pantalla,
// asi el reporte nunca contradice lo que el usuario vio. Se genera en el navegador (RNF06).
import { jsPDF } from "jspdf";
import { autoTable } from "jspdf-autotable";
import { FORMULACIONES, formato, resumenGerencial } from "../metricas/metricas.js";

export const NOTA_INFACTIBLE =
  "Ruta infactible: no visita cada cajero exactamente una vez. Su gap no es comparable y se excluye del resumen.";

export function nombreReporte(doc) {
  return `reporte_instancia${doc.instancia.id_instancia}.pdf`;
}

// Contenido del reporte como datos puros (probado sin generar el PDF).
export function contenidoReporte(doc, metricas, advertencias, gerencia = resumenGerencial(doc, metricas)) {
  const { corridas, resumen } = metricas;
  const inst = doc.instancia;
  const g = gerencia;
  const entero = (x) => formato(x, 0);
  const avisos = new Map(advertencias.map((a) => [a.id_corrida, a.mensaje]));
  return {
    titulo: "Reporte de optimización de rutas de reabastecimiento",
    gerencia: {
      sinAhorro: g.sinAhorro,
      cifras: [
        ["Ahorro en combustible al año", `S/ ${formato(g.porAnio.soles)}`, `S/ ${formato(g.porRecorrido.soles)} por recorrido`],
        ["Diésel ahorrado al año", `${entero(g.porAnio.litros)} litros`, `${formato(g.porRecorrido.litros)} litros por recorrido`],
        ["Distancia ahorrada", `${formato(g.porRecorrido.pct, 1)} %`, `${formato(g.porRecorrido.km)} km por recorrido · ${entero(g.porAnio.km)} km al año`],
        ["Tiempo ahorrado", `${entero(g.porRecorrido.min)} min por recorrido`, `${formato(g.porAnio.horas, 1)} h al año${g.tiempoEstimado ? " (estimado con velocidad media)" : " (tiempos de manejo por calles)"}`],
        ["CO2 evitado al año", `${entero(g.porAnio.co2)} kg`, `${formato(g.porRecorrido.co2)} kg por recorrido`],
      ],
      rutas: [
        ["Habitual (orden de la planilla)", formato(g.habitual.km), entero(g.habitual.min), formato(g.consumo.habitual.litros), formato(g.consumo.habitual.soles), [...g.habitual.secuencia, g.habitual.secuencia[0]].join(" - ")],
        ["Propuesta", formato(g.propuesta.km), entero(g.propuesta.min), formato(g.consumo.propuesta.litros), formato(g.consumo.propuesta.soles), [...g.propuesta.secuencia, g.propuesta.secuencia[0]].join(" - ")],
      ],
      origen: `Ruta propuesta: ${g.propuesta.origen}. ${g.alcanzaOptimo ? "Coincide con la mejor ruta posible (Held-Karp)." : `La mejor ruta posible mide ${formato(g.optimoKm)} km (Held-Karp).`}`,
      supuestos: `Supuestos: rendimiento ${formato(g.supuestos.rendimiento_km_l, 1)} km/l · diésel S/ ${formato(g.supuestos.precio_soles_l)} por litro · ${formato(g.supuestos.co2_kg_l)} kg CO2 por litro · ${entero(g.supuestos.recorridos_anio)} recorridos al año${g.tiempoEstimado ? ` · velocidad media ${entero(g.supuestos.velocidad_kmh)} km/h` : ""}.`,
    },
    paradas: inst.cajeros.map((c) => [String(c.id_cajero), c.nombre ?? (c.id_cajero === 0 ? "Depósito" : `Cajero ${c.id_cajero}`), c.direccion ?? "—"]),
    fuente: inst.fuente?.tipo === "osm"
      ? `Ubicaciones de cajeros ${inst.fuente.entidad ?? ""}: ${inst.fuente.atribucion ?? "OpenStreetMap"}. Son ubicaciones públicas; no se usan datos operativos del banco.`
      : "Ubicaciones sintéticas generadas para la prueba.",
    encabezado: [
      ["Instancia", `${inst.id_instancia} (${inst.tipo_instancia})`],
      ["Cajeros", String(inst.cajeros.length)],
      ["Línea base (Held-Karp)", `${formato(inst.linea_base.dist_optima)} km · ruta ${inst.linea_base.ruta.join(" - ")}`],
      ["Versión del esquema", doc.version_esquema],
      ["Archivo generado el", doc.fecha_generacion],
    ],
    resumen: FORMULACIONES.map((f) => {
      const r = resumen[f];
      return [
        f,
        r.total === 0 ? "Sin corridas" : `${r.factibles} / ${r.total}`,
        r.mejorGap === null ? "Sin rutas factibles" : `${formato(r.mejorGap)} %`,
        r.ahorroVsGps === null ? "No calculable" : `${formato(r.ahorroVsGps)} %`,
      ];
    }),
    corridas: corridas.map((c) => [
      String(c.id_corrida),
      c.formulacion,
      c.sampler,
      formato(c.metricas.distancia_total),
      c.gap === null ? "No comparable" : formato(c.gap),
      c.metricas.chain_break_fraction === null ? "No aplica" : formato(c.metricas.chain_break_fraction, 3),
      c.ruta.factible ? "Sí" : "Infactible",
      c.ruta.secuencia.join(" - "),
    ]),
    infactibles: corridas.filter((c) => !c.ruta.factible).length,
    notas: [
      ...(corridas.some((c) => !c.ruta.factible) ? [NOTA_INFACTIBLE] : []),
      ...[...avisos.values()],
      "El resumen solo considera rutas factibles.",
    ],
  };
}

export function generarPdf(contenido) {
  const pdf = new jsPDF({ orientation: "landscape", unit: "pt", format: "a4" });
  const g = contenido.gerencia;
  pdf.setFont("helvetica", "bold");
  pdf.setFontSize(16);
  pdf.text(contenido.titulo, 40, 50);

  // Pagina 1: resumen para gerencia
  pdf.setFontSize(12);
  pdf.text("Resumen para gerencia", 40, 78);
  autoTable(pdf, {
    startY: 88,
    body: g.sinAhorro
      ? [[{ content: "En esta instancia el orden de la planilla ya es la mejor ruta: no hay ahorro que reportar. Con más cajeros por recorrido es menos probable que el orden de la planilla sea el óptimo.", colSpan: 3 }]]
      : g.cifras,
    theme: "grid",
    styles: { fontSize: 11, cellPadding: 6 },
    columnStyles: { 0: { fontStyle: "bold", cellWidth: 220 }, 1: { fontStyle: "bold", fontSize: 13, cellWidth: 200 } },
  });
  autoTable(pdf, {
    head: [["Ruta", "km", "min", "Diésel (L)", "Costo (S/)", "Orden de visita"]],
    body: g.rutas,
    headStyles: { fillColor: [20, 33, 61] },
    styles: { fontSize: 10 },
  });
  pdf.setFont("helvetica", "normal");
  pdf.setFontSize(9);
  let yg = pdf.lastAutoTable.finalY + 18;
  for (const linea of [g.origen, g.supuestos, contenido.fuente]) {
    const partes = pdf.splitTextToSize(linea, 760);
    pdf.text(partes, 40, yg);
    yg += partes.length * 12 + 2;
  }
  autoTable(pdf, {
    startY: yg + 6,
    head: [["Punto", "Nombre", "Dirección"]],
    body: contenido.paradas,
    headStyles: { fillColor: [20, 33, 61] },
    styles: { fontSize: 9 },
  });

  // Pagina 2: detalle tecnico
  pdf.addPage();
  pdf.setFont("helvetica", "bold");
  pdf.setFontSize(12);
  pdf.text("Detalle técnico de las corridas", 40, 50);
  autoTable(pdf, {
    startY: 60,
    body: contenido.encabezado,
    theme: "plain",
    styles: { fontSize: 10, cellPadding: 3 },
    columnStyles: { 0: { fontStyle: "bold", cellWidth: 160 } },
  });
  autoTable(pdf, {
    head: [["Formulación", "Rutas factibles", "Mejor gap", "% de ahorro respecto a GPS"]],
    body: contenido.resumen,
    headStyles: { fillColor: [20, 33, 61] },
    styles: { fontSize: 10 },
  });
  autoTable(pdf, {
    head: [["Corrida", "Formulación", "Sampler", "Distancia (km)", "Gap (%)", "Chain break fraction", "Factible", "Secuencia"]],
    body: contenido.corridas,
    headStyles: { fillColor: [20, 33, 61] },
    styles: { fontSize: 9 },
    didParseCell: (d) => {
      if (d.section === "body" && d.column.index === 6 && d.cell.raw === "Infactible") d.cell.styles.textColor = [180, 35, 24];
    },
  });

  let y = pdf.lastAutoTable.finalY + 24;
  pdf.setFont("helvetica", "normal");
  pdf.setFontSize(9);
  for (const nota of contenido.notas) {
    const lineas = pdf.splitTextToSize(`Nota. ${nota}`, 760);
    pdf.text(lineas, 40, y);
    y += lineas.length * 12;
  }
  return pdf;
}
