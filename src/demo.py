from datetime import datetime, timedelta, timezone
from xml.sax.saxutils import escape
from .analysis import BASELINE
from .events import parse_event


def demo_events():
    metadata = {"columns": [{"object_name": e, "name": f, "description": "microseconds"}
                             for e in ("rpc_completed", "module_end", "sp_statement_completed") for f in ("duration", "cpu_time")]}
    result, raw = [], {}
    origin = datetime(2026, 10, 9, 12, tzinfo=timezone.utc)
    seq = 0

    def add(event, oid, name, text, duration=0):
        nonlocal seq
        seq += 1
        timestamp = (origin + timedelta(milliseconds=seq * 10)).isoformat()
        values = {"object_id": oid, "source_database_id": 7, "object_name": name, "statement": text,
                  "session_id": 71, "request_id": 0, "event_sequence": seq, "database_name": "BD_EXP",
                  "duration": duration, "cpu_time": duration // 3, "logical_reads": 12, "writes": 0}
        xml = f'<event name="{event}" timestamp="{timestamp}">' + ''.join(f'<data name="{key}"><value>{escape(str(val))}</value></data>' for key, val in values.items()) + '</event>'
        parsed = parse_event(xml, "DEMO_sintetica.xel", 1024, metadata)
        result.append(parsed)
        raw[parsed["event_id"]] = xml

    for i, name in enumerate(BASELINE):
        sql = f"EXEC BD_EXP.dbo.{name} @UsrLogin='usuario_demo', @TabIdSesion=123"
        add("rpc_starting", i + 100, name, sql)
        add("module_start", i + 100, name, sql)
        add("sp_statement_completed", i + 100, name, "SELECT * FROM dbo.Ejemplo WITH (NOLOCK) WHERE Codigo=1", 2000 + i * 1000)
        add("module_end", i + 100, name, sql, 5000 + i * 1000)
        add("rpc_completed", i + 100, name, sql, 6000 + i * 1000)
    return result, raw
