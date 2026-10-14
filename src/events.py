from defusedxml import ElementTree as ET
import hashlib


def number(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def unit(metadata, event, field):
    desc = next((c.get("description") or "" for c in metadata.get("columns", [])
                 if c["object_name"] == event and c["name"] == field), "").lower()
    if "microsecond" in desc:
        return "us"
    if "millisecond" in desc:
        return "ms"
    return "desconocida"


def parse_event(xml, filename, offset, metadata=None):
    root = ET.fromstring(xml)
    if root.tag != "event":
        raise ValueError("Se esperaba un evento XE.")
    fields, labels = {}, {}
    for node in root:
        name = node.get("name")
        if name:
            fields[name] = node.findtext("value")
            labels[name] = node.findtext("text")
    event = root.get("name", "")
    duration = number(fields.get("duration"))
    duration_unit = unit(metadata or {}, event, "duration")
    duration_ms = duration / 1000 if duration is not None and duration_unit == "us" else duration if duration_unit == "ms" else None
    text = fields.get("statement") or fields.get("batch_text") or fields.get("sql_text") or ""
    identity = f"{filename}\0{offset}\0{xml}".encode("utf-8")
    return {
        "event_id": hashlib.sha256(identity).hexdigest(), "event": event,
        "timestamp": root.get("timestamp", ""), "session_id": number(fields.get("session_id")),
        "request_id": number(fields.get("request_id")), "sequence": number(fields.get("event_sequence")),
        "database": fields.get("database_name") or "", "database_id": number(fields.get("source_database_id") or fields.get("database_id")),
        "object_id": number(fields.get("object_id")), "object_name": fields.get("object_name") or "",
        "object_type": labels.get("object_type") or fields.get("object_type") or "",
        "nest_level": number(fields.get("nest_level")), "text": text,
        "duration_raw": duration, "duration_unit": duration_unit, "duration_ms": duration_ms,
        "cpu_raw": number(fields.get("cpu_time")), "cpu_unit": unit(metadata or {}, event, "cpu_time"),
        "reads": number(fields.get("logical_reads")), "writes": number(fields.get("writes")),
        "activity_id": fields.get("attach_activity_id"), "activity_id_xfer": fields.get("attach_activity_id_xfer"),
        "error": fields.get("message") or "", "filename": filename, "offset": offset,
    }
