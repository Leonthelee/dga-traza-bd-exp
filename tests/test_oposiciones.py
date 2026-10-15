from src.oposiciones import (
    agregar_oposicion,
    clean_rut,
    fetch_comunas,
    fetch_oposiciones_detalle,
    fetch_provincias,
    fetch_regiones,
    fetch_tipos_tramite,
    search_expedientes,
    DEMO_REGIONES,
    DEMO_PROVINCIAS,
    DEMO_COMUNAS,
)


def test_clean_rut():
    assert clean_rut("000000000076122587-1") == "76122587-1"
    assert clean_rut("00000069070100-5") == "69070100-5"
    assert clean_rut("12345678-9") == "12345678-9"
    assert clean_rut("") == "S/I"
    assert clean_rut(None) == "S/I"


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
        opositor_rut="76.999.888-2",
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

    # Verificar que el expediente ahora tiene oposicion activa
    res = search_expedientes(exp_llave="ND-1301-5020", conn=None)
    assert len(res) == 1
    assert res[0]["NumOposicionesRaw"] >= 1
    assert " - Sí" in res[0]["NumOposiciones"]
    assert res[0]["Estado"] == "CON OPOSICIÓN"

