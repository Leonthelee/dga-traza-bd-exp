import argparse
import time
from datetime import datetime, timezone
from .config import load_settings
from .store import Store, now
from .db import connect, preflight, execute
from .loader import collect
from .service import validate_capture, error_text
from . import xe


def run(id, store):
    if not store.claim(id):
        return
    capture = store.get(id)["payload"]
    settings = None
    created = False
    failure = ""

    def ended():
        store.update(id, heartbeat=now())
        return bool(store.get(id)["stop_requested"]) or datetime.now(timezone.utc) >= datetime.fromisoformat(capture["deadline"])

    try:
        settings = load_settings()
        validate_capture(settings, capture)
        with connect(settings) as conn:
            preflight(conn, settings)
            if ended():
                store.update(id, status="stopped", message="Cancelada antes de iniciar.")
                return
            # Flag before DDL: a timeout can occur after SQL accepted CREATE.
            created = True
            execute(conn, capture["sql"])
            if not ended():
                xe.start(conn, capture["name"])
        next_read = time.monotonic() + 8
        while not ended():
            if time.monotonic() >= next_read:
                with connect(settings) as conn:
                    health = xe.status(conn, capture["name"])
                    if not health or not health[0]["running"]:
                        break
                    store.update(id, health=health[0])
                    collect(conn, store, capture, ended)
                next_read = time.monotonic() + 10
            time.sleep(1)
    except Exception as exc:
        failure = error_text(exc, settings)
    finally:
        if created:
            store.update(id, status="stopping", heartbeat=now())
            stopped = False
            for attempt in range(3):
                try:
                    with connect(settings) as conn:
                        preflight(conn, settings)
                        health = xe.status(conn, capture["name"])
                        if health and health[0]["running"]:
                            store.update(id, health=health[0])
                        xe.stop(conn, capture["name"])
                    stopped = True
                    break
                except Exception as exc:
                    failure = error_text(exc, settings)
                    time.sleep(2)
            if not stopped:
                store.update(id, status="attention", message="NO se pudo confirmar la parada en SQL Server: " + failure)
                return
            try:
                with connect(settings) as conn:
                    collect(conn, store, capture)
            except Exception as exc:
                failure = "Captura detenida; importación incompleta: " + error_text(exc, settings)
            store.update(id, status="stopped", heartbeat=now(), message=failure or "Captura detenida e importación final realizada. Revisar salud y retención.")
        elif failure:
            store.update(id, status="failed", heartbeat=now(), message=failure)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("id")
    parser.add_argument("--store")
    args = parser.parse_args()
    run(args.id, Store(args.store))
