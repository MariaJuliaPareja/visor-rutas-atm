// CMP-09 Generacion de reportes (RF05). Usa las mismas cifras de CMP-07 que la pantalla,
// asi el reporte nunca contradice lo que el usuario vio. Se genera en el navegador (RNF06).
import { jsPDF } from "jspdf";
import { autoTable } from "jspdf-autotable";
import { FORMULACIONES, formato } from "../metricas/metricas.js";

export const NOTA_INFACTIBLE =
  "Ruta infactible: no visita cada cajero exactamente una vez. Su gap no es comparable y se excluye del resumen.";

export function nombreReporte(doc) {
  return `reporte_instancia${doc.instancia.id_instancia}.pdf`;
}

// Contenido del reporte como datos puros (probado sin generar el PDF).
export function contenidoReporte(doc, { corridas, resumen }, advertencias) {
  const inst = doc.instancia;
  const avisos = new Map(advertencias.map((a) => [a.id_corrida, a.mensaje]));
  return {
    titulo: "Reporte consolidado de corridas",
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
  pdf.setFont("helvetica", "bold");
  pdf.setFontSize(16);
  pdf.text(contenido.titulo, 40, 50);

  autoTable(pdf, {
    startY: 70,
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
