from .db import rows
from .events import parse_event
from .governance import default_audit_logger


def collect(conn, store, capture, should_stop=lambda: False, audit_logger=None):
    """Re-read retained XEL files, commit in chunks, deduplicate by full event identity.

    file_offset is a block offset, NOT a unique event id. Re-reading avoids skipping
    other events sharing that block after a crash. No TOP/OFFSET pagination.
    """
    logger = audit_logger or default_audit_logger
    cursor = conn.cursor()
    names = {}
    total = 0
    collected_hashes = []
    try:
        cursor.execute("SELECT file_name,file_offset,event_data FROM sys.fn_xe_file_target_read_file(?,NULL,NULL,NULL)",
                       capture["pattern"])
        while not should_stop():
            raw = cursor.fetchmany(250)
            if not raw:
                break
            batch = []
            for filename, offset, xml in raw:
                event = parse_event(str(xml), filename, int(offset), capture["metadata"])
                key = (event["database_id"], event["object_id"])
                if all(key) and not event["object_name"] and key not in names:
                    names[key] = None
                batch.append((event, str(xml)))
                collected_hashes.append({"sha256": event["event_id"], "event": event["event"]})
            total += store.insert_events(capture["id"], batch)
    finally:
        cursor.close()
    for db, obj in names:
        if should_stop():
            break
        try:
            found = rows(conn, "SELECT OBJECT_SCHEMA_NAME(?,?) + N'.' + OBJECT_NAME(?,?) name",
                         obj, db, obj, db)
            names[(db, obj)] = found[0]["name"]
        except Exception:
            names[(db, obj)] = None
    store.save_names(capture["id"], names)
    logger.log_query(
        operation="collect_xel_events",
        query_params={"capture_id": capture.get("id"), "pattern": capture.get("pattern")},
        fragments=collected_hashes,
        environment=capture.get("environment", "QA"),
        abstained=len(collected_hashes) == 0,
        abstention_reason="Cero eventos XEL leídos en el ciclo." if not collected_hashes else None,
        metadata={"inserted_new": total},
    )
    return total

