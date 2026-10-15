from streamlit.testing.v1 import AppTest
from src.config import ROOT


def test_demo_navigation_and_export():
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=20).run()
    assert not app.exception
    assert any(m.value == "50" for m in list(app.metric) + list(app.sidebar.metric))
    for section in ["Módulo Oposiciones (Gob.cl)", "Secuencia y árbol", "Inspector searchSolicitudes", "Patrones", "Línea base", "Evidencia", "Control QA"]:
        app.radio(key="section").set_value(section).run()
        assert not app.exception, section
    app.radio(key="section").set_value("Evidencia").run()
    app.button[0].click().run()
    assert not app.exception


def test_unconfigured_qa_is_not_connected(monkeypatch):
    monkeypatch.setattr("src.config.load_settings", lambda *args, **kwargs: (_ for _ in ()).throw(ValueError("Falta .streamlit/secrets.toml")))
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=20).run()
    app.radio(key="mode").set_value("SQL Server QA").run()
    app.radio(key="section").set_value("Control QA").run()
    assert not app.exception
    assert app.warning
