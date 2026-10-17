"""Tests unitarios de la API REST Backend — Módulo de Oposiciones DGA Gob.cl
Verifica contratos de datos, validación Módulo 11 de RUT, cascada de catálogos y registro.
"""

import copy
import pytest
from starlette.testclient import TestClient

from backend.server import app
import src.oposiciones as op


@pytest.fixture(autouse=True)
def restore_demo_state():
    a = copy.deepcopy(op.DEMO_RESULTADOS_BUSQUEDA)
    b = copy.deepcopy(op.DEMO_OPOSICIONES_STORE)
    yield
    op.DEMO_RESULTADOS_BUSQUEDA[:] = a
    op.DEMO_OPOSICIONES_STORE.clear()
    op.DEMO_OPOSICIONES_STORE.update(b)


@pytest.fixture
def client():
    return TestClient(app)



def test_api_health(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "dga-modulo-oposiciones-backend"


def test_api_catalogo_regiones_ordered_1_to_16(client):
    response = client.get("/api/catalogo/regiones")
    assert response.status_code == 200
    res = response.json()
    assert res["success"] is True
    data = res["data"]
    assert len(data) == 16
    assert [r["RegCodigo"] for r in data] == list(range(1, 17))


def test_api_catalogo_cascadas(client):
    # Región 13 (Metropolitana) -> Provincias
    r_prov = client.get("/api/catalogo/provincias?reg_codigo=13")
    assert r_prov.status_code == 200
    provincias = r_prov.json()["data"]
    assert len(provincias) > 0
    pro_2 = [p for p in provincias if p["ProCodigo"] == 2]  # Cordillera
    assert len(pro_2) == 1

    # Región 13 + Provincia 2 (Cordillera) -> Comunas
    r_com = client.get("/api/catalogo/comunas?reg_codigo=13&pro_codigo=2")
    assert r_com.status_code == 200
    comunas = r_com.json()["data"]
    assert any(c["ComNombre"] == "Puente Alto" for c in comunas)



def test_api_search_oposiciones_demo(client):
    response = client.get("/api/oposiciones/search")
    assert response.status_code == 200
    res = response.json()
    assert res["success"] is True
    assert res["total"] >= 5
    assert res["con_oposiciones"] >= 1
    # Cada fila contiene campos obligatorios
    first = res["data"][0]
    assert "ExpConcatLlave" in first
    assert "RutSolicitante" in first
    assert "FechaSolicitud" in first
    assert "NumOposiciones" in first
    assert "Estado" in first


def test_api_search_filtered(client):
    response = client.get("/api/oposiciones/search?exp_llave=ND-0802-4437")
    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) == 1
    assert data[0]["ExpConcatLlave"] == "ND-0802-4437"


def test_api_detalle_oposiciones(client):
    response = client.get("/api/oposiciones/detalle?exp_codigo=ND-0802-4437")
    assert response.status_code == 200
    res = response.json()
    assert res["success"] is True
    assert res["exp_codigo"] == "ND-0802-4437"
    assert len(res["data"]) >= 1


def test_api_agregar_oposicion_rejects_bad_rut(client):
    bad_payload = {
        "exp_codigo": "ND-0802-4437",
        "fecha_ingreso": "15/10/2026",
        "doc_nro": "OPO-2026-TEST",
        "opositor_nombre": "Test Invalido",
        "opositor_rut": "12345678-9",  # DV incorrecto
        "observaciones": "Test",
    }
    response = client.post("/api/oposiciones/agregar", json=bad_payload)
    assert response.status_code == 400
    assert "no es válido según algoritmo Módulo 11" in response.json()["detail"]


def test_api_agregar_oposicion_success_demo(client):
    # RUT con DV válido: 76012345-5
    good_payload = {
        "exp_codigo": "ND-0802-4437",
        "fecha_ingreso": "15/10/2026",
        "doc_nro": "OPO-2026-TEST-OK",
        "opositor_nombre": "Agricola Test SpA",
        "opositor_rut": "76012345-5",
        "observaciones": "Ingreso oficial test API",
    }
    response = client.post("/api/oposiciones/agregar", json=good_payload)
    assert response.status_code == 200
    res = response.json()
    assert res["success"] is True
    assert "Oposición registrada exitosamente" in res["message"]
