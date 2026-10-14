from io import BytesIO
import re
import pandas as pd


def safe_cell(value):
    if isinstance(value, str):
        value = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", value)
        if value.lstrip().startswith(("=", "+", "-", "@")):
            return "'" + value
    return value


def safe_frame(frame):
    return frame.map(safe_cell)


def csv_bytes(frame):
    return safe_frame(frame).to_csv(index=False).encode("utf-8-sig")


def excel_bytes(sheets):
    out = BytesIO()
    with pd.ExcelWriter(out, engine="openpyxl") as writer:
        for name, frame in sheets.items():
            safe_frame(frame).to_excel(writer, sheet_name=name[:31], index=False)
            sheet = writer.sheets[name[:31]]
            sheet.freeze_panes = "A2"
            sheet.auto_filter.ref = sheet.dimensions
            for col in sheet.columns:
                sheet.column_dimensions[col[0].column_letter].width = min(55, max(14, len(str(col[0].value)) + 3))
    return out.getvalue()


def markdown_rag_summary(events):
    """Genera documento Markdown estructurado para inyectar en knowledge del RAG BPM."""
    from src.analysis import object_label, patterns, tree, tree_diagram

    lines = [
        "# 🗺️ Trazabilidad de Procedimientos Almacenados: BD_EXP / BD_PAR / BD_MAP",
        "",
        "> **DGA Core Tools - by Daniel Díaz L. & AI Engine Antigravity**  ",
        "> Documento generado para el Centinela RAG de `dga-bpm-orchestrator`.",
        "",
        "## 1. Resumen Ejecutivo de Eventos Capturados",
        "",
        f"- **Total de Eventos Analizados:** {len(events)}",
    ]

    counter = {}
    params_found = set()
    for e in events:
        obj = object_label(e)
        db = e.get("database", "N/A")
        dur = e.get("duration_ms") or 0
        reads = e.get("reads") or 0
        if obj not in counter:
            counter[obj] = {"db": db, "count": 0, "duration_sum": 0, "reads_sum": 0}
        counter[obj]["count"] += 1
        counter[obj]["duration_sum"] += dur
        counter[obj]["reads_sum"] += reads

        txt = e.get("text", "")
        if "@UsrLogin" in txt:
            params_found.add("@UsrLogin")
        if "@TabIdSesion" in txt:
            params_found.add("@TabIdSesion")
        if "@CodExp" in txt:
            params_found.add("@CodExpediente / @CodExp")

    lines.append("")
    lines.append("### Procedimientos y Módulos Identificados")
    lines.append("")
    lines.append("| Objeto / Procedimiento | Base de Datos | Ejecuciones | Duración Total (ms) | Lecturas Acumuladas |")
    lines.append("| :--- | :--- | :--- | :--- | :--- |")
    for obj, data in sorted(counter.items(), key=lambda x: x[1]["duration_sum"], reverse=True):
        lines.append(f"| `{obj}` | `{data['db']}` | {data['count']} | {data['duration_sum']:.1f} | {data['reads_sum']} |")

    lines.append("")
    lines.append("## 2. Parámetros de Contexto y Sesión Detectados")
    lines.append("")
    if params_found:
        for p in sorted(params_found):
            lines.append(f"- Parámetro detectado en TextData: `{p}`")
    else:
        lines.append("- No se detectaron parámetros contextuales explícitos en el TextData.")

    lines.append("")
    lines.append("## 3. Jerarquía y Árbol de Ejecución (Mermaid)")
    lines.append("")
    nodes = tree(events)
    roots = [n["id"] for n in nodes if n["parent"] is None]
    if roots:
        lines.append("```mermaid")
        lines.append(tree_diagram(nodes, roots[0]))
        lines.append("```")
    else:
        lines.append("*(No se pudo inferir árbol completo por falta de eventos pareados)*")

    lines.append("")
    lines.append("## 4. Patrones y Hallazgos para Guardrails")
    lines.append("")
    pat_df = patterns(events)
    if not pat_df.empty:
        lines.append("| Objeto | Indicio Detectado | Recomendación / Guardrail |")
        lines.append("| :--- | :--- | :--- |")
        for _, row in pat_df.drop_duplicates(subset=["Objeto", "Indicio"]).iterrows():
            lines.append(f"| `{row['Objeto']}` | `{row['Indicio']}` | {row['Revisión']} |")
    else:
        lines.append("- Cero patrones anómalos o de riesgo detectados en la muestra.")

    lines.append("")
    return "\n".join(lines)
