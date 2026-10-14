from contextlib import contextmanager
from datetime import datetime, timezone
import json
import sqlite3
from pathlib import Path
from .config import DATA


def now():
    return datetime.now(timezone.utc).isoformat()


class Store:
    def __init__(self, path=None):
        self.path = Path(path) if path else DATA / "qa.sqlite3"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as con:
            con.executescript("""
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS captures (
                id TEXT PRIMARY KEY, status TEXT NOT NULL, payload TEXT NOT NULL,
                created TEXT NOT NULL, heartbeat TEXT, stop_requested INTEGER NOT NULL DEFAULT 0,
                message TEXT NOT NULL DEFAULT '', health TEXT NOT NULL DEFAULT '{}');
            CREATE TABLE IF NOT EXISTS events (
                capture_id TEXT NOT NULL, event_id TEXT NOT NULL, payload TEXT NOT NULL, raw_xml TEXT NOT NULL,
                PRIMARY KEY(capture_id,event_id));
            CREATE INDEX IF NOT EXISTS idx_events_capture ON events(capture_id);
            CREATE TABLE IF NOT EXISTS objects(capture_id TEXT, database_id INTEGER, object_id INTEGER, name TEXT,
                PRIMARY KEY(capture_id,database_id,object_id));
            """)

    @contextmanager
    def connection(self):
        con = sqlite3.connect(self.path, timeout=20)
        con.row_factory = sqlite3.Row
        try:
            with con:
                yield con
        finally:
            con.close()

    def create(self, capture):
        with self.connection() as con:
            con.execute("BEGIN IMMEDIATE")
            if con.execute("SELECT 1 FROM captures WHERE status IN ('queued','running','stopping','attention') LIMIT 1").fetchone():
                raise ValueError("Ya hay una captura activa o pendiente de recuperación. Resuélvala antes de iniciar otra.")
            con.execute("INSERT INTO captures(id,status,payload,created) VALUES(?,?,?,?)",
                        (capture["id"], "queued", json.dumps(capture, ensure_ascii=False), now()))

    def get(self, id):
        with self.connection() as con:
            row = con.execute("SELECT * FROM captures WHERE id=?", (id,)).fetchone()
        if row is None:
            raise ValueError("Captura no encontrada.")
        result = dict(row)
        result["payload"] = json.loads(result["payload"])
        result["health"] = json.loads(result["health"])
        return result

    def list(self):
        with self.connection() as con:
            return [dict(row) for row in con.execute("SELECT id,status,created,heartbeat,message FROM captures ORDER BY created DESC")]

    def update(self, id, **values):
        if not values or set(values) - {"status", "heartbeat", "stop_requested", "message", "health"}:
            raise ValueError("Campos de estado no permitidos.")
        if "health" in values:
            values["health"] = json.dumps(values["health"])
        with self.connection() as con:
            con.execute("UPDATE captures SET " + ",".join(f"{key}=?" for key in values) + " WHERE id=?", (*values.values(), id))

    def claim(self, id):
        with self.connection() as con:
            cur = con.execute("UPDATE captures SET status='running',heartbeat=? WHERE id=? AND status='queued'", (now(), id))
            return cur.rowcount == 1

    def insert_events(self, id, batch):
        with self.connection() as con:
            before = con.total_changes
            con.executemany("INSERT OR IGNORE INTO events VALUES(?,?,?,?)",
                            [(id, event["event_id"], json.dumps(event, ensure_ascii=False), xml) for event, xml in batch])
            return con.total_changes - before

    def count(self, id):
        with self.connection() as con:
            return con.execute("SELECT COUNT(*) FROM events WHERE capture_id=?", (id,)).fetchone()[0]

    def events(self, id, limit=100000):
        with self.connection() as con:
            result = [json.loads(row[0]) for row in con.execute("SELECT payload FROM events WHERE capture_id=? LIMIT ?", (id, limit))]
            names = {(r[0], r[1]): r[2] for r in con.execute("SELECT database_id,object_id,name FROM objects WHERE capture_id=?", (id,))}
        for event in result:
            if not event.get("object_name"):
                event["object_name"] = names.get((event.get("database_id"), event.get("object_id")), "")
        return result

    def save_names(self, id, names):
        with self.connection() as con:
            con.executemany("INSERT OR REPLACE INTO objects VALUES(?,?,?,?)", [(id, db, obj, name) for (db, obj), name in names.items() if name])

    def raw(self, id, event_id):
        with self.connection() as con:
            row = con.execute("SELECT raw_xml FROM events WHERE capture_id=? AND event_id=?", (id, event_id)).fetchone()
        return row[0] if row else ""
