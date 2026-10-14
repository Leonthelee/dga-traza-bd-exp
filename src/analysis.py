from collections import Counter
import hashlib
import re

import pandas as pd

BASELINE = (
    "Exps_PerBuscaExpPorCodExpF10",
    "Exps_TieneResApruebaF3",
    "Exps_TieneResAprElectronicaF10",
    "Exps_TraerRegPro",
    "Exps_SolExpSel4F6",
    "Exps_CuentaSolicF3",
    "Exps_ValSoliciEtapasSel",
    "Exps_SolEtDatSel4F4",
    "Exps_ConsCaracEtapaSel",
    "Exps_DatFechasExpSel",
)

LAYERS = {
    "Llamadas externas": ("rpc_completed", "sql_batch_completed"),
    "Módulos": ("module_end",),
    "Sentencias": ("sp_statement_completed", "sql_statement_completed"),
}


def object_label(event):
    if event.get("object_name"):
        return event["object_name"]
    if event.get("object_id"):
        return f"objeto {event.get('database_id')}:{event['object_id']}"
    match = re.search(r"\bexec(?:ute)?\s+(?:@\w+\s*=\s*)?((?:\[?\w+\]?\.)*\[?\w+\]?)",
                      event.get("text", ""), re.I)
    return match[1].replace("[", "").replace("]", "") if match else event["event"]


def summary(events, layer):
    selected = []
    for e in events:
        if e["event"] not in LAYERS[layer]:
            continue
        digest = hashlib.sha256(e.get("text", "").encode()).hexdigest()[:16]
        selected.append({"Evento": e["event"], "Base": e.get("database", ""),
                         "Objeto": object_label(e), "Firma": digest,
                         "Duración ms": e.get("duration_ms"), "Lecturas": e.get("reads"),
                         "Escrituras": e.get("writes"), "SQL": e.get("text", "")})
    if not selected:
        return pd.DataFrame()
    frame = pd.DataFrame(selected)
    group = frame.groupby(["Evento", "Base", "Objeto", "Firma"], dropna=False)
    result = group.agg(Llamadas=("SQL", "size"),
                       Duracion_total_ms=("Duración ms", lambda x: x.sum(min_count=1)),
                       Duracion_media_ms=("Duración ms", "mean"),
                       P95_ms=("Duración ms", lambda x: x.quantile(0.95)),
                       Lecturas=("Lecturas", lambda x: x.sum(min_count=1)),
                       SQL=("SQL", "first")).reset_index()
    return result.sort_values("Duracion_total_ms", ascending=False, na_position="last")


def patterns(events):
    checks = [
        (r"\bSELECT\s+\*", "SELECT *", "Revisar columnas necesarias."),
        (r"\bNOLOCK\b", "NOLOCK", "Revisar consistencia y aislamiento; no quitar automáticamente."),
        (r"\bCONVERT\s*\(", "CONVERT", "Revisar contexto y plan; la presencia sola no prueba un problema."),
        (r"\bCURSOR\b", "CURSOR", "Revisar volumen y alternativas."),
        (r"\bsp_(?:sproc_columns|stored_procedures)\b", "Metadatos", "Medir frecuencia y posible caché en cliente."),
    ]
    found = []
    for event in events:
        if event["event"] not in set().union(*LAYERS.values()):
            continue
        for pattern, name, message in checks:
            if re.search(pattern, event.get("text", ""), re.I):
                found.append({"Evento ID": event["event_id"], "Evento": event["event"],
                              "Objeto": object_label(event), "Indicio": name,
                              "Revisión": message, "SQL": event["text"]})
    return pd.DataFrame(found)


def parameters(text):
    user = re.search(r"@UsrLogin\s*=\s*N?'((?:''|[^'])*)'", text, re.I)
    session = re.search(r"@TabIdSesion\s*=\s*(\d+)", text, re.I)
    return {
        "UsrLogin declarado": user[1].replace("''", "'").strip() if user else None,
        "TabIdSesion declarado": session[1] if session else None,
    }


def tree(events):
    """Conservative serial request stack; no parent if request/order is unavailable.

    Relations are inferred from start/end order, not proof of UI causality.
    Unmatched ends and open frames remain explicitly incomplete.
    """
    result = []
    stacks = {}
    ordered = sorted(events, key=lambda e: (e.get("sequence") is None,
                                            e.get("sequence") or 0,
                                            e.get("timestamp", "")))
    starts = {"rpc_starting": "rpc_completed",
              "sql_batch_starting": "sql_batch_completed",
              "module_start": "module_end"}
    ends = set(starts.values())
    for event in ordered:
        if event["event"] not in set(starts) | ends:
            continue
        key = (event.get("session_id"), event.get("request_id"))
        valid = None not in key and event.get("sequence") is not None
        stack = stacks.setdefault(key, []) if valid else []
        if event["event"] in starts:
            if event["event"] != "module_start":
                stack.clear()
            node = {"id": len(result),
                    "parent": stack[-1][0]["id"] if stack else None,
                    "Objeto": object_label(event),
                    "SPID": key[0], "Request": key[1],
                    "Inicio UTC": event.get("timestamp"),
                    "Fin UTC": None, "Duración ms": None,
                    "Estado": "sin cierre" if valid else "sin correlación",
                    "Evento ID": event["event_id"]}
            result.append(node)
            if valid:
                stack.append((node, event))
        elif valid and stack:
            node, original = stack[-1]
            same = starts[original["event"]] == event["event"]
            if event["event"] == "module_end":
                same = same and (original.get("database_id"),
                                 original.get("object_id")) == (event.get("database_id"),
                                                               event.get("object_id"))
                if same:
                    same = event.get("object_id") is not None
            if same:
                stack.pop()
                node.update({"Fin UTC": event.get("timestamp"),
                             "Duración ms": event.get("duration_ms"),
                             "Estado": "pareado; relación inferida"})
                continue
            result.append({"id": len(result), "parent": None,
                           "Objeto": object_label(event),
                           "SPID": key[0], "Request": key[1],
                           "Estado": "cierre sin inicio compatible",
                           "Evento ID": event["event_id"]})
            stack.clear()
        else:
            result.append({"id": len(result), "parent": None,
                           "Objeto": object_label(event),
                           "SPID": key[0], "Request": key[1],
                           "Estado": "cierre sin inicio",
                           "Evento ID": event["event_id"]})
            stack.clear()
    return result


def baseline(events):
    observed = Counter(e.get("object_name", "").split(".")[-1].strip("[]").casefold()
                       for e in events if e["event"] == "module_start")
    return pd.DataFrame([{"Procedimiento": name,
                          "Esperado en una acción": 1,
                          "Observado": observed[name.casefold()],
                          "Resultado": "coincide" if observed[name.casefold()] == 1 else "revisar captura/acción"}
                         for name in BASELINE])


def tree_diagram(nodes, root_id):
    descendants = {root_id}
    for node in nodes:
        if node["parent"] in descendants:
            descendants.add(node["id"])
    selected = [n for n in nodes if n["id"] in descendants][:100]
    lines = ["flowchart TD"]
    for node in selected:
        label = re.sub(r"[^\w .:()/-]", "_", node["Objeto"])[:90]
        state = "pareado" if node["Estado"].startswith("pareado") else "incompleto"
        lines.append(f'N{node["id"]}["{label} ({state})"]')
    ids = {n["id"] for n in selected}
    for node in selected:
        if node["parent"] in ids:
            lines.append(f'N{node["parent"]} --> N{node["id"]}')
    return "\n".join(lines)
