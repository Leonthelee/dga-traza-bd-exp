from src.oposiciones import (
    agregar_oposicion,
    clean_rut,
    fetch_comunas,
    fetch_oposiciones_detalle,
    fetch_provincias,
    fetch_regiones,
    fetch_tipos_tramite,
    normalize_fecha,
    search_expedientes,
    validate_rut,
)


def test_clean_rut():
    assert clean_rut("000000000076122587-1") == "76122587-1"
    assert clean_rut("00000069070100-5") == "69070100-5"
    assert clean_rut("12345678-9") == "12345678-9"
    assert clean_rut("") == "S/I"
    assert clean_rut(None) == "S/I"


def test_validate_rut_and_normalize_fecha():
    # Validaciones RUT Módulo 11
    assert validate_rut("76122587-1") is True
    assert validate_rut("76.122.587-1") is True
    assert validate_rut("69070100-6") is True
    assert validate_rut("69070100-5") is False  # DV incorrecto
    assert validate_rut("76122587-9") is False  # DV incorrecto
    assert validate_rut("invalido") is False
    assert validate_rut("") is False
    assert validate_rut(None) is False

    # Normalización de fechas centinela
    assert normalize_fecha("01/01/1900") == "S/I"
    assert normalize_fecha("1900-01-01") == "S/I"
    assert normalize_fecha("") == "S/I"
    assert normalize_fecha(None) == "S/I"
    assert normalize_fecha("15/10/2026") == "15/10/2026"


def test_demo_catalogs_and_cascades():
    # Tipos de tramite
    tipos = fetch_tipos_tramite(conn=None)
    assert len(tipos) >= 5
    assert any(t["Sigla"] == "ND" for t in tipos)

    # Regiones
    regiones = fetch_regiones(conn=None)
    assert len(regiones) == 16
    assert any(r["RegCodigo"] == 13 for r in regiones)
    assert any(r["RegCodigo"] == 16 for r in regiones)  # Ñuble
    assert any(r["RegCodigo"] == 15 for r in regiones)  # Arica y Parinacota
    assert any(r["RegCodigo"] == 12 for r in regiones)  # Magallanes

    # Provincias (RM = 13)
    provincias_rm = fetch_provincias(13, conn=None)
    assert len(provincias_rm) >= 3
    assert any(p["ProNombre"] == "Cordillera" for p in provincias_rm)

    # Comunas (RM = 13, Cordillera = 2)
    comunas_cord = fetch_comunas(13, 2, conn=None)
    assert len(comunas_cord) >= 1
    assert any("Puente Alto" in c["ComNombre"] for c in comunas_cord)


def test_demo_search_and_detalle():
    # Busqueda sin filtro
    res_all = search_expedientes(conn=None)
    assert len(res_all) >= 4
    assert any(r["NumOposiciones"] == "0 - No" for r in res_all)
    assert any(" - Sí" in r["NumOposiciones"] for r in res_all)

    # Verificacion de RUT Solicitante y Fecha Solicitud
    row_4437 = next(r for r in res_all if r["ExpConcatLlave"] == "ND-0802-4437")
    assert row_4437["RutSolicitante"] == "76122587-1"
    assert row_4437["FechaSolicitud"] == "30/05/2012"
    assert row_4437["NumOposiciones"] == "98 - Sí"
    assert row_4437["NumOposicionesRaw"] == 98

    # Detalle de oposiciones
    det = fetch_oposiciones_detalle("ND-0802-4437", conn=None)
    assert len(det) >= 2
    assert "RUCUE" in det[0]["NombreOpositor"]


def test_agregar_oposicion():
    # Registrar oposicion en expediente existente
    resp = agregar_oposicion(
        exp_codigo="ND-1301-5020",
        fecha_ingreso="15/10/2026",
        doc_nro="SSD-2026-9901",
        opositor_nombre="CANALISTAS DEL MAIPO S.A.",
        opositor_rut="76.999.888-8",
        observaciones="Oposición deducida por afectación de derechos.",
        conn=None,
    )
    assert resp["success"] is True
    assert "Instancia N°" in resp["message"]
    assert resp["numero_oposicion"] >= 1

    # Verificar que aparece en el detalle de oposiciones
    detalles = fetch_oposiciones_detalle("ND-1301-5020", conn=None)
    assert len(detalles) >= 1
    assert any("CANALISTAS DEL MAIPO" in d["NombreOpositor"] for d in detalles)

    # Validaciones de rechazo
    bad_rut = agregar_oposicion("ND-1301-5020", "15/10/2026", "SSD-1", "OP", "12345678-0")
    assert bad_rut["success"] is False
    assert "no es válido" in bad_rut["message"]

    bad_exp = agregar_oposicion("ND-1301-5020-DEMASIADO-LARGO", "15/10/2026", "SSD-1", "OP", "76122587-1")
    assert bad_exp["success"] is False
    assert "excede el largo máximo" in bad_exp["message"]

    bad_name = agregar_oposicion("ND-1301-5020", "15/10/2026", "SSD-1", "", "76122587-1")
    assert bad_name["success"] is False
    assert "nombre o razón social" in bad_name["message"]

    bad_date = agregar_oposicion("ND-1301-5020", "2026-13-40", "SSD-1", "OP", "76122587-1")
    assert bad_date["success"] is False
    assert "formato válido" in bad_date["message"]

    # Simulación con Mock de conexión SQL para verificar vinculación de persona
    executed_sqls = []
    class MockCursor:
        def execute(self, sql, params):
            executed_sqls.append(sql)
        def fetchone(self):
            return (0, "OK", 9001, 1)
        def close(self):
            pass

    class MockConnection:
        def cursor(self):
            return MockCursor()
        def commit(self):
            pass

    resp_mock = agregar_oposicion(
        exp_codigo="ND-0802-4437",
        fecha_ingreso="15/10/2026",
        doc_nro="SSD-2026-001",
        opositor_nombre="CANALISTAS DEL LAJA",
        opositor_rut="76122587-1",
        conn=MockConnection(),
    )
    assert resp_mock["success"] is True
    assert any("CPA_SaveRelacionVinculadoPerPortal" in s for s in executed_sqls)

