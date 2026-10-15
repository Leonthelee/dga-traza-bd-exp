from src.oposiciones import (
    fetch_tipos_tramite,
    fetch_regiones,
    fetch_provincias,
    fetch_comunas,
    search_expedientes,
    fetch_oposiciones_detalle,
    DEMO_REGIONES,
    DEMO_PROVINCIAS,
    DEMO_COMUNAS,
)


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
    assert len(res_all) >= 3

    # Busqueda por expediente
    res_filter = search_expedientes(exp_llave="ND-0802-4437", conn=None)
    assert len(res_filter) == 1
    assert res_filter[0]["ExpConcatLlave"] == "ND-0802-4437"
    assert res_filter[0]["NumOposiciones"] == 98

    # Detalle de oposiciones
    det = fetch_oposiciones_detalle("ND-0802-4437", conn=None)
    assert len(det) >= 2
    assert "RUCUE" in det[0]["NombreOpositor"]
