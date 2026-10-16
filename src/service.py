import hashlib
import json
import os
import subprocess
import sys
import uuid
from datetime import datetime, timedelta, timezone
from .config import ROOT, DATA
from .db import connect, preflight
from . import xe


def fingerprint(settings):
    # Credentials can rotate; target and filters must never silently change.
    values = {key: getattr(settings, key) for key in ("server", "expected_server_name", "environment", "xel_directory", "login_filter", "databases")}
    return hashlib.sha256(json.dumps(values, sort_keys=True).encode()).hexdigest()


def prepare(settings, label, profile, minutes, spid=0, threshold_ms=0):
    if not 1 <= int(minutes) <= 15:
        raise ValueError("El piloto QA limita las capturas a 1–15 minutos.")
    if not label.strip():
        raise ValueError("Indique la acción que va a probar.")
    with connect(settings) as conn:
        info = preflight(conn, settings)
        metadata = xe.catalog(conn)
    id = uuid.uuid4().hex
    sql, pattern = xe.build_sql(settings, "TrazaQA_" + id, profile, metadata, spid, threshold_ms)
    return {"id": id, "name": "TrazaQA_" + id, "label": label.strip()[:150], "profile": profile,
            "minutes": int(minutes), "spid": int(spid), "threshold_ms": int(threshold_ms),
            "environment": settings.environment,
            "sql": sql, "pattern": pattern, "metadata": metadata, "server": info,
            "fingerprint": fingerprint(settings)}


def launch(store, capture):
    capture = dict(capture)
    capture["deadline"] = (datetime.now(timezone.utc) + timedelta(minutes=capture["minutes"])).isoformat()
    store.create(capture)
    DATA.mkdir(exist_ok=True)
    try:
        with (DATA / "worker.log").open("ab") as log:
            subprocess.Popen([sys.executable, "-m", "src.worker", capture["id"], "--store", str(store.path)],
                             cwd=ROOT, stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                             creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                             start_new_session=os.name != "nt")
    except Exception:
        store.update(capture["id"], status="failed", message="No se pudo iniciar el recolector.")
        raise


def validate_capture(settings, capture):
    if capture["fingerprint"] != fingerprint(settings):
        raise ValueError("La configuración cambió desde la preparación; restaure la configuración de esta captura.")


def recover(settings, store, id):
    capture = store.get(id)["payload"]
    validate_capture(settings, capture)
    store.update(id, stop_requested=1)
    with connect(settings) as conn:
        preflight(conn, settings)
        health = xe.status(conn, capture["name"])
        if health:
            store.update(id, health=health[0])
        xe.stop(conn, capture["name"])
    store.update(id, status="stopped", message="Parada verificada en SQL Server. Puede reimportar los XEL.")


def error_text(exc, settings=None):
    text = str(exc)
    if settings and settings.password:
        text = text.replace(settings.password, "[oculto]")
    return text[:1500]
