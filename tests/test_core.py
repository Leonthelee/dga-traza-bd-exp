from dataclasses import replace
import io
import pytest
from openpyxl import load_workbook
import pandas as pd
from src.config import Settings
from src.db import connection_string, preflight
from src.xe import build_sql, session_identifier, PROFILES, ACTIONS
from src.events import parse_event
from src.demo import demo_events
from src.analysis import tree, summary, baseline, parameters
from src.store import Store
from src.export import excel_bytes, csv_bytes, markdown_rag_summary
from src.service import validate_capture, fingerprint


@pytest.fixture
def settings():
    return Settings(server="QA", expected_server_name="QA", xel_directory=r"D:\Traces", databases=("BD_EXP",), login_filter="qa'login")


def metadata():
    objects = [{"package": "sqlserver", "name": e, "object_type": "event"} for e in PROFILES["detalle"]]
    objects += [{"package": p, "name": n, "object_type": "action"} for p, n in ACTIONS]
    objects += [{"package": "sqlserver", "name": n, "object_type": "pred_source"} for n in ("server_principal_name", "client_app_name", "session_id")]
    return {"objects": objects, "columns": [{"object_name": e, "name": "duration", "description": "microseconds"} for e in PROFILES["detalle"]]}


def test_qa_guard_and_connection_escaping(settings):
    with pytest.raises(ValueError, match="environment"):
        replace(settings, environment="DEV_TEST").validate()
    # PROD is now allowed
    replace(settings, environment="PROD").validate()
    text = connection_string(replace(settings, trusted_connection=False, username="u", password="x};SERVER=other"))
    assert "PWD={x}};SERVER=other}" in text


def test_sql_scoping_escaping_and_no_duration_in_detail(settings):
    sql, pattern = build_sql(settings, "TrazaQA_" + "a" * 32, "detalle", metadata(), spid=71)
    assert "qa''login" in sql
    assert "session_id]=(71)" in sql
    assert "STARTUP_STATE=OFF" in sql
    assert "[duration]>=" not in sql
    assert pattern.endswith("*.xel")
    with pytest.raises(ValueError):
        build_sql(settings, "TrazaQA_" + "a" * 32, "detalle", metadata(), threshold_ms=10)
    with pytest.raises(ValueError):
        session_identifier("system_health")


def test_missing_capabilities_and_unknown_units_block_threshold(settings):
    with pytest.raises(ValueError, match="componentes"):
        build_sql(settings, "TrazaQA_" + "b" * 32, "detalle", {"objects": [], "columns": []})
    data = metadata()
    data["columns"] = []
    with pytest.raises(ValueError, match="unidad"):
        build_sql(settings, "TrazaQA_" + "b" * 32, "rendimiento", data, threshold_ms=10)


def test_same_xel_block_events_are_not_lost_and_reimports_are_idempotent(tmp_path):
    events, raw = demo_events()
    store = Store(tmp_path / "test.sqlite")
    store.create({"id": "demo"})
    batch = [(e, raw[e["event_id"]]) for e in events]
    assert store.insert_events("demo", batch) == 50
    assert store.insert_events("demo", batch) == 0
    assert store.count("demo") == 50
    assert len({e["offset"] for e in events}) == 1


def test_atomic_capture_claim_and_no_duplicate_active(tmp_path):
    store = Store(tmp_path / "test.sqlite")
    store.create({"id": "first"})
    with pytest.raises(ValueError):
        store.create({"id": "second"})
    assert store.claim("first")
    assert not store.claim("first")
    store.update("first", status="stopped")
    store.create({"id": "second"})


def test_demo_baseline_and_metrics_do_not_double_count():
    events, _ = demo_events()
    assert baseline(events)["Observado"].tolist() == [1] * 10
    assert summary(events, "Llamadas externas")["Llamadas"].sum() == 10
    assert summary(events, "Módulos")["Llamadas"].sum() == 10
    assert summary(events, "Sentencias")["Llamadas"].sum() == 10
    nodes = tree(events)
    assert len(nodes) == 20
    assert all(n["Estado"] == "pareado; relación inferida" for n in nodes)
    assert len([n for n in nodes if n["parent"] is None]) == 10


def test_missing_start_and_missing_request_do_not_invent_parents():
    events, _ = demo_events()
    nodes = tree(events[2:5])
    assert all(n["parent"] is None for n in nodes)
    events[1]["request_id"] = None
    nodes = tree(events[:5])
    assert nodes[1]["parent"] is None
    assert nodes[1]["Estado"] == "sin correlación"


def test_reused_request_id_does_not_attach_to_old_unclosed_call():
    events, _ = demo_events()
    nodes = tree(events[:2] + events[5:10])
    assert nodes[2]["parent"] is None
    assert nodes[0]["Estado"] == "sin cierre"


def test_unknown_units_preserved_and_xml_entities_rejected():
    event = parse_event('<event name="x"><data name="duration"><value>2500</value></data></event>', "f", 0)
    assert event["duration_raw"] == 2500 and event["duration_ms"] is None
    with pytest.raises(Exception):
        parse_event('<!DOCTYPE x [<!ENTITY e SYSTEM "file:///C:/secret">]><event>&e;</event>', "f", 0)


def test_business_parameters_are_optional_and_unescape_quotes():
    assert parameters("EXEC p @UsrLogin=N'O''Brien   ', @TabIdSesion=12")["UsrLogin declarado"] == "O'Brien"
    assert parameters("EXEC p @UsrLogin=@variable")["UsrLogin declarado"] is None


def test_exports_do_not_execute_spreadsheet_formulas():
    frame = pd.DataFrame({"SQL": ["=HYPERLINK(\"x\")", "@UsrLogin=1", "SELECT 1"]})
    book = load_workbook(io.BytesIO(excel_bytes({"Eventos": frame})))
    assert book.active["A2"].data_type != "f"
    assert book.active["A2"].value.startswith("'")
    assert "'@UsrLogin" in csv_bytes(frame).decode("utf-8-sig")


def test_changed_target_rejected(settings):
    with pytest.raises(ValueError, match="configuración"):
        validate_capture(replace(settings, server="OTHER"), {"fingerprint": fingerprint(settings)})


def test_preflight_rejects_server_mismatch(settings, monkeypatch):
    monkeypatch.setattr("src.db.rows", lambda *args: [{"server_name": "PROD", "version": "15.0", "can_control": 1, "can_read": 1}])
    with pytest.raises(ValueError, match="servidor"):
        preflight(None, settings)


def test_markdown_rag_summary_export():
    events, _ = demo_events()
    md = markdown_rag_summary(events)
    assert "# 🗺️ Trazabilidad de Procedimientos Almacenados" in md
    assert "DGA Core Tools - by Daniel Díaz L. & AI Engine Antigravity" in md
    assert "flowchart TD" in md
    assert "Procedimientos y Módulos Identificados" in md


def test_parse_expediente_and_search_solicitudes_mapping():
    from src.inspector import parse_expediente, SECUENCIA_SEARCH_SOLICITUDES
    info = parse_expediente("ND-1204-390")
    assert info is not None
    assert info["tex_codigo"] == 1
    assert info["reg_codigo"] == 12
    assert info["pro_codigo"] == 4
    assert info["exp_codigo"] == 390
    assert info["tabla_objeto_principal"] == "BD_EXP..Expt_ObjetoNegocioND"

    assert len(SECUENCIA_SEARCH_SOLICITUDES) == 10
    assert SECUENCIA_SEARCH_SOLICITUDES[0]["sp"] == "CPA_BusquedaExpedientesOp"
    assert parse_expediente("invalido") is None
