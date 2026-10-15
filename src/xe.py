import re
from pathlib import PureWindowsPath
from .db import rows, execute

PROFILES = {
    "rendimiento": ["rpc_completed", "sql_batch_completed", "error_reported"],
    "detalle": ["rpc_starting", "rpc_completed", "sql_batch_starting", "sql_batch_completed",
                "module_start", "module_end", "sp_statement_completed", "sql_statement_completed", "error_reported"],
}
ACTIONS = [("sqlserver", n) for n in ("session_id", "request_id", "database_name", "client_app_name",
           "client_hostname", "server_principal_name", "sql_text")] + [("package0", "event_sequence")]


def literal(value):
    return "N'" + str(value).replace("'", "''") + "'"


def session_identifier(name):
    if not re.fullmatch(r"TrazaQA_[a-f0-9]{32}", name):
        raise ValueError("Solo se permiten sesiones creadas por TrazaQA.")
    return f"[{name}]"


def catalog(conn):
    objects = rows(conn, """SELECT p.name package, o.name, o.object_type FROM sys.dm_xe_objects o
        JOIN sys.dm_xe_packages p ON p.guid=o.package_guid
        WHERE p.name IN ('sqlserver','package0')""")
    columns = rows(conn, """SELECT p.name package, c.object_name, c.name, c.description, c.column_type
        FROM sys.dm_xe_object_columns c JOIN sys.dm_xe_packages p ON p.guid=c.object_package_guid
        WHERE p.name='sqlserver'""")
    return {"objects": objects, "columns": columns}


def build_sql(settings, name, profile, metadata, spid=0, threshold_ms=0):
    ident = session_identifier(name)
    if profile not in PROFILES:
        raise ValueError("Perfil no válido.")
    if not 0 <= int(spid) <= 32767 or not 0 <= int(threshold_ms) <= 60000:
        raise ValueError("SPID o umbral fuera de rango.")
    if profile == "detalle" and threshold_ms:
        raise ValueError("Detalle no admite filtro de duración.")
    available = {(o["package"], o["name"], o["object_type"]) for o in metadata["objects"]}
    required = [("sqlserver", e, "event") for e in PROFILES[profile]]
    required += [(p, n, "action") for p, n in ACTIONS]
    required += [("sqlserver", n, "pred_source") for n in ("server_principal_name", "client_app_name")]
    if spid:
        required.append(("sqlserver", "session_id", "pred_source"))
    missing = [f"{p}.{n} ({t})" for p, n, t in required if (p, n, t) not in available]
    if missing:
        raise ValueError("La instancia no ofrece los componentes requeridos: " + ", ".join(missing))
    predicate = f"([sqlserver].[server_principal_name]={literal(settings.login_filter)}) AND ([sqlserver].[client_app_name]<>N'TrazaBD_EXP_QA')"
    if spid:
        predicate += f" AND ([sqlserver].[session_id]=({int(spid)}))"
    actions = ",".join(f"[{p}].[{n}]" for p, n in ACTIONS)
    events = []
    for event in PROFILES[profile]:
        where = predicate
        if threshold_ms and event != "error_reported":
            description = next((c["description"] or "" for c in metadata["columns"]
                                if c["object_name"] == event and c["name"] == "duration"), "").lower()
            if "microsecond" not in description:
                raise ValueError(f"No se pudo confirmar la unidad duration de {event}; use umbral 0.")
            where += f" AND ([duration]>=({int(threshold_ms) * 1000}))"
        events.append(f"ADD EVENT [sqlserver].[{event}](ACTION({actions}) WHERE ({where}))")
    if not settings.xel_directory or settings.xel_directory in (".", "DEFAULT") or settings.xel_directory.startswith("/"):
        path = name + ".xel"
        pattern = name + "*.xel"
    else:
        path = str(PureWindowsPath(settings.xel_directory) / (name + ".xel"))
        pattern = path[:-4] + "*.xel"
    sql = f"CREATE EVENT SESSION {ident} ON SERVER\n" + ",\n".join(events)
    sql += f"\nADD TARGET [package0].[event_file](SET filename={literal(path)},max_file_size=(64),max_rollover_files=(8))"
    sql += "\nWITH (MAX_MEMORY=4096 KB,EVENT_RETENTION_MODE=ALLOW_SINGLE_EVENT_LOSS,MAX_DISPATCH_LATENCY=5 SECONDS,TRACK_CAUSALITY=ON,STARTUP_STATE=OFF);"
    return sql, pattern


def status(conn, name):
    session_identifier(name)
    return rows(conn, """SELECT s.name, CASE WHEN d.name IS NULL THEN 0 ELSE 1 END running,
        d.dropped_event_count, d.dropped_buffer_count, d.largest_event_dropped_size
        FROM sys.server_event_sessions s LEFT JOIN sys.dm_xe_sessions d ON s.name=d.name
        WHERE s.name=?""", name)


def start(conn, name):
    execute(conn, f"ALTER EVENT SESSION {session_identifier(name)} ON SERVER STATE=START;")


def stop(conn, name):
    state = status(conn, name)
    if state and state[0]["running"]:
        execute(conn, f"ALTER EVENT SESSION {session_identifier(name)} ON SERVER STATE=STOP;")


def drop(conn, name):
    state = status(conn, name)
    if state and state[0]["running"]:
        raise ValueError("Detenga la sesión antes de quitar su definición.")
    if state:
        execute(conn, f"DROP EVENT SESSION {session_identifier(name)} ON SERVER;")
