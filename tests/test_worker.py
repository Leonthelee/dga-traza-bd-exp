from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import pytest
from src.store import Store
from src import worker


@contextmanager
def fake_connection(settings):
    yield object()


@pytest.fixture
def setup_worker(tmp_path, monkeypatch):
    store = Store(tmp_path / "worker.sqlite")
    capture = {"id": "x", "name": "TrazaQA_" + "a" * 32, "sql": "CREATE", "metadata": {},
               "deadline": (datetime.now(timezone.utc) + timedelta(minutes=1)).isoformat()}
    store.create(capture)
    monkeypatch.setattr(worker, "load_settings", lambda: None)
    monkeypatch.setattr(worker, "validate_capture", lambda *a: None)
    monkeypatch.setattr(worker, "preflight", lambda *a: None)
    monkeypatch.setattr(worker, "connect", fake_connection)
    monkeypatch.setattr(worker.time, "sleep", lambda *a: None)
    monkeypatch.setattr(worker.xe, "status", lambda *a: [{"running": 1, "dropped_event_count": 2}])
    monkeypatch.setattr(worker, "collect", lambda *a: 0)
    return store


def test_cancelled_before_start_executes_no_ddl(setup_worker, monkeypatch):
    store = setup_worker
    store.update("x", stop_requested=1)
    calls = []
    monkeypatch.setattr(worker, "execute", lambda *a: calls.append("ddl"))
    worker.run("x", store)
    assert not calls
    assert store.get("x")["status"] == "stopped"


def test_start_failure_still_stops_session(setup_worker, monkeypatch):
    store = setup_worker
    calls = []
    monkeypatch.setattr(worker, "execute", lambda *a: None)
    def fail(*a):
        raise RuntimeError("start failed")
    monkeypatch.setattr(worker.xe, "start", fail)
    monkeypatch.setattr(worker.xe, "stop", lambda *a: calls.append("stop"))
    worker.run("x", store)
    assert calls == ["stop"]
    assert store.get("x")["status"] == "stopped"
    assert store.get("x")["health"]["dropped_event_count"] == 2


def test_stop_failure_is_attention_not_success(setup_worker, monkeypatch):
    store = setup_worker
    monkeypatch.setattr(worker, "execute", lambda *a: None)
    def fail(*a):
        raise RuntimeError("network down")
    monkeypatch.setattr(worker.xe, "start", fail)
    monkeypatch.setattr(worker.xe, "stop", fail)
    worker.run("x", store)
    assert store.get("x")["status"] == "attention"
    assert "NO se pudo" in store.get("x")["message"]


def test_lost_create_acknowledgement_attempts_cleanup(setup_worker, monkeypatch):
    store = setup_worker
    calls = []
    def fail(*a):
        raise RuntimeError("DDL acknowledgement timeout")
    monkeypatch.setattr(worker, "execute", fail)
    monkeypatch.setattr(worker.xe, "stop", lambda *a: calls.append("stop"))
    worker.run("x", store)
    assert calls == ["stop"]
