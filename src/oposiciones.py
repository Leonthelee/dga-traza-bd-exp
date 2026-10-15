"""src/oposiciones.py — Módulo de Oposiciones DGA (Reemplazo oficial BPM JSP).

Conecta directamente con BD_PAR para listas desplegables en cascada (Región -> Provincia -> Comuna)
y con BD_EXP para búsqueda de solicitudes y detalle de oposiciones (CPA_BusquedaOpExpedientes_SNIA).
Incluye fallback a datos de demostración si se ejecuta en modo demo o sin conexión SQL.
"""

from typing import Any, Dict, List, Optional
from src.db import rows

# Datos estáticos de respaldo para Modo Demo sintético
DEMO_REGIONES = [
    {"RegCodigo": 13, "RegNombre": "Metropolitana de Santiago", "OrdenGeo": 7},
    {"RegCodigo": 8, "RegNombre": "del Biobío", "OrdenGeo": 11},
    {"RegCodigo": 5, "RegNombre": "de Valparaíso", "OrdenGeo": 6},
    {"RegCodigo": 7, "RegNombre": "del Maule", "OrdenGeo": 9},
    {"RegCodigo": 6, "RegNombre": "del Libertador Gral. B. O'Higgins", "OrdenGeo": 8},
]

DEMO_PROVINCIAS = {
    13: [
        {"ProCodigo": 1, "ProNombre": "Santiago"},
        {"ProCodigo": 2, "ProNombre": "Cordillera"},
        {"ProCodigo": 3, "ProNombre": "Chacabuco"},
        {"ProCodigo": 4, "ProNombre": "Maipo"},
        {"ProCodigo": 5, "ProNombre": "Melipilla"},
        {"ProCodigo": 6, "ProNombre": "Talagante"},
    ],
    8: [
        {"ProCodigo": 1, "ProNombre": "Concepción"},
        {"ProCodigo": 2, "ProNombre": "Bio-Bio"},
        {"ProCodigo": 3, "ProNombre": "Arauco"},
    ],
}

DEMO_COMUNAS = {
    (13, 2): [
        {"ComCodigo": 1, "ComNombre": "Puente Alto"},
        {"ComCodigo": 2, "ComNombre": "Pirque"},
        {"ComCodigo": 3, "ComNombre": "San José de Maipo"},
    ],
    (8, 2): [
        {"ComCodigo": 1, "ComNombre": "Los Ángeles"},
        {"ComCodigo": 2, "ComNombre": "Antuco"},
        {"ComCodigo": 3, "ComNombre": "Santa Bárbara"},
        {"ComCodigo": 4, "ComNombre": "Tucapel"},
    ],
}

DEMO_TIPOS_EXPEDIENTE = [
    {"TexCodigo": 0, "Sigla": "TODOS", "Descripcion": "Todos los Tipos de Trámite"},
    {"TexCodigo": 1, "Sigla": "ND", "Descripcion": "Derechos de Aprovechamiento"},
    {"TexCodigo": 2, "Sigla": "NR", "Descripcion": "Regularización de Derechos"},
    {"TexCodigo": 3, "Sigla": "VT", "Descripcion": "Traslado de Ejercicio de Derechos"},
    {"TexCodigo": 4, "Sigla": "VC", "Descripcion": "Cambio de Punto de Captación"},
    {"TexCodigo": 5, "Sigla": "VP", "Descripcion": "Perfeccionamiento de Título"},
    {"TexCodigo": 6, "Sigla": "OBR", "Descripcion": "Aprobación de Obras"},
    {"TexCodigo": 7, "Sigla": "FD", "Descripcion": "Fiscalización Denuncia"},
]

DEMO_RESULTADOS_BUSQUEDA = [
    {
        "ExpConcatLlave": "ND-0802-4437",
        "NumSolicitudes": 12,
        "Solicitante": "ASESORIAS E INVERSIONES D&P DOS LIMITADA.",
        "GLRegion": "del Biobío",
        "GLProvincia": "Bio-Bio",
        "GLComuna": "Tucapel",
        "GLTipoDerecho": "No Consuntivo",
        "FechaInicio": "30/05/2012",
        "TexCodigo": 1,
        "RegCodigo": 8,
        "ProCodigo": 2,
        "ExpCodigo": 4437,
        "NumOposiciones": 98,
        "Estado": "CON OPOSICIÓN",
    },
    {
        "ExpConcatLlave": "ND-0802-4396",
        "NumSolicitudes": 12,
        "Solicitante": "SOCIEDAD DE INVERSIONES EMILUX LIMITADA",
        "GLRegion": "del Biobío",
        "GLProvincia": "Bio-Bio",
        "GLComuna": "Santa Bárbara",
        "GLTipoDerecho": "No Consuntivo",
        "FechaInicio": "14/03/2011",
        "TexCodigo": 1,
        "RegCodigo": 8,
        "ProCodigo": 2,
        "ExpCodigo": 4396,
        "NumOposiciones": 49,
        "Estado": "CON OPOSICIÓN",
    },
    {
        "ExpConcatLlave": "ND-1302-413",
        "NumSolicitudes": 1,
        "Solicitante": "ILUSTRE MUNICIPALIDAD DE PUENTE ALTO",
        "GLRegion": "Metropolitana de Santiago",
        "GLProvincia": "Cordillera",
        "GLComuna": "Puente Alto",
        "GLTipoDerecho": "Consuntivo",
        "FechaInicio": "18/11/2009",
        "TexCodigo": 1,
        "RegCodigo": 13,
        "ProCodigo": 2,
        "ExpCodigo": 413,
        "NumOposiciones": 2,
        "Estado": "CON OPOSICIÓN",
    },
    {
        "ExpConcatLlave": "NR-0601-1318",
        "NumSolicitudes": 1,
        "Solicitante": "AGRICOLA EL ARRAYAN S.A.",
        "GLRegion": "del Libertador Gral. B. O'Higgins",
        "GLProvincia": "Cachapoal",
        "GLComuna": "Rancagua",
        "GLTipoDerecho": "Consuntivo",
        "FechaInicio": "30/09/1999",
        "TexCodigo": 2,
        "RegCodigo": 6,
        "ProCodigo": 1,
        "ExpCodigo": 1318,
        "NumOposiciones": 1,
        "Estado": "CON OPOSICIÓN",
    },
]


def fetch_tipos_tramite(conn=None) -> List[Dict[str, Any]]:
    """Obtiene los tipos de trámites/expedientes desde BD_PAR."""
    if conn is None:
        return DEMO_TIPOS_EXPEDIENTE
    try:
        data = rows(
            conn,
            "SELECT TexCodigo, RTRIM(TexDesc) as Sigla, RTRIM(TexDescLargo) as Descripcion "
            "FROM BD_PAR.dbo.Part_TiposExpediente ORDER BY TexDesc"
        )
        return [{"TexCodigo": 0, "Sigla": "TODOS", "Descripcion": "Todos los Tipos de Trámite"}] + data
    except Exception:
        return DEMO_TIPOS_EXPEDIENTE


def fetch_regiones(conn=None) -> List[Dict[str, Any]]:
    """Obtiene las regiones de Chile ordenadas geográficamente desde BD_PAR."""
    if conn is None:
        return DEMO_REGIONES
    try:
        return rows(
            conn,
            "SELECT RegCodigo, RTRIM(RegNombre) as RegNombre, OrdenGeo "
            "FROM BD_PAR.dbo.Part_Region ORDER BY OrdenGeo, RegCodigo"
        )
    except Exception:
        return DEMO_REGIONES


def fetch_provincias(reg_codigo: int, conn=None) -> List[Dict[str, Any]]:
    """Obtiene provincias de una región desde BD_PAR (cascada)."""
    if reg_codigo <= 0:
        return []
    if conn is None:
        return DEMO_PROVINCIAS.get(reg_codigo, [{"ProCodigo": 1, "ProNombre": "Provincia Central"}])
    try:
        return rows(
            conn,
            "SELECT ProCodigo, RTRIM(ProNombre) as ProNombre "
            "FROM BD_PAR.dbo.Part_Provincia WHERE RegCodigo = ? ORDER BY ProNombre",
            reg_codigo,
        )
    except Exception:
        return DEMO_PROVINCIAS.get(reg_codigo, [])


def fetch_comunas(reg_codigo: int, pro_codigo: int, conn=None) -> List[Dict[str, Any]]:
    """Obtiene comunas de una provincia/región desde BD_PAR (cascada)."""
    if reg_codigo <= 0 or pro_codigo <= 0:
        return []
    if conn is None:
        return DEMO_COMUNAS.get((reg_codigo, pro_codigo), [{"ComCodigo": 1, "ComNombre": "Comuna Local"}])
    try:
        return rows(
            conn,
            "SELECT ComCodigo, RTRIM(ComNombre) as ComNombre "
            "FROM BD_PAR.dbo.Part_Comuna WHERE RegCodigo = ? AND ProCodigo = ? ORDER BY ComNombre",
            reg_codigo,
            pro_codigo,
        )
    except Exception:
        return DEMO_COMUNAS.get((reg_codigo, pro_codigo), [])


def search_expedientes(
    tipo_tramite: Optional[int] = None,
    reg_codigo: Optional[int] = None,
    pro_codigo: Optional[int] = None,
    com_codigo: Optional[int] = None,
    exp_llave: Optional[str] = None,
    solicitante: Optional[str] = None,
    limit: int = 50,
    conn=None,
) -> List[Dict[str, Any]]:
    """Busca solicitudes y expedientes en BD_EXP con conteo de oposiciones en vivo."""
    if conn is None:
        res = DEMO_RESULTADOS_BUSQUEDA
        if reg_codigo:
            res = [r for r in res if r["RegCodigo"] == reg_codigo]
        if exp_llave:
            res = [r for r in res if exp_llave.upper() in r["ExpConcatLlave"].upper()]
        return res

    conditions = ["1=1"]
    params: List[Any] = []

    if tipo_tramite and tipo_tramite > 0:
        conditions.append("s.TexCodigo = ?")
        params.append(tipo_tramite)

    if reg_codigo and reg_codigo > 0:
        conditions.append("s.RegCodigo = ?")
        params.append(reg_codigo)

    if pro_codigo and pro_codigo > 0:
        conditions.append("s.ProCodigo = ?")
        params.append(pro_codigo)

    if com_codigo and com_codigo > 0:
        conditions.append("s.ComCodigo = ?")
        params.append(com_codigo)

    if exp_llave and exp_llave.strip():
        clean_exp = exp_llave.strip()
        conditions.append("s.ExpConcatLlave LIKE ?")
        params.append(f"%{clean_exp}%")

    if solicitante and solicitante.strip():
        clean_sol = solicitante.strip()
        conditions.append("s.Solicitante LIKE ?")
        params.append(f"%{clean_sol}%")

    where_clause = " AND ".join(conditions)

    sql = f"""
    SELECT TOP {int(limit)}
        RTRIM(s.ExpConcatLlave) AS ExpConcatLlave, 
        COUNT(DISTINCT s.SolCodigo) AS NumSolicitudes,
        COALESCE(RTRIM(s.Solicitante), 'Sin Titular Registrado') AS Solicitante, 
        COALESCE(RTRIM(s.GLRegion), '') AS GLRegion, 
        COALESCE(RTRIM(s.GLProvincia), '') AS GLProvincia, 
        COALESCE(RTRIM(s.GLComuna), '') AS GLComuna, 
        COALESCE(RTRIM(s.GLTipoDerecho), 'Consuntivo') AS GLTipoDerecho, 
        CONVERT(VARCHAR(10), MIN(s.FCInicioTramite), 103) AS FechaInicio,
        s.TexCodigo, s.RegCodigo, s.ProCodigo, s.ExpCodigo,
        (SELECT COUNT(*) FROM BD_EXP.dbo.Expt_EtapasSolDocOpoRec o 
         WHERE o.TexCodigo = s.TexCodigo AND o.RegCodigo = s.RegCodigo 
           AND o.ProCodigo = s.ProCodigo AND o.ExpCodigo = s.ExpCodigo) AS NumOposiciones
    FROM BD_EXP.dbo.SolicitudEnTramite s
    WHERE {where_clause}
    GROUP BY s.ExpConcatLlave, s.Solicitante, s.GLRegion, s.GLProvincia, s.GLComuna, s.GLTipoDerecho,
             s.TexCodigo, s.RegCodigo, s.ProCodigo, s.ExpCodigo
    ORDER BY NumOposiciones DESC, s.ExpCodigo DESC
    """

    try:
        records = rows(conn, sql, *params)
        for r in records:
            r["Estado"] = "CON OPOSICIÓN" if r.get("NumOposiciones", 0) > 0 else "EN TRÁMITE"
        return records
    except Exception as exc:
        return [{"error": str(exc)}]


def fetch_oposiciones_detalle(exp_llave: str, conn=None) -> List[Dict[str, Any]]:
    """Ejecuta CPA_BusquedaOpExpedientes_SNIA para obtener la lista formal de oposiciones."""
    if not exp_llave or not exp_llave.strip():
        return []
    clean_llave = exp_llave.strip().upper()

    if conn is None:
        if "4437" in clean_llave:
            return [
                {
                    "Correlativo": 1,
                    "NombreOpositor": "EMPRESA ELECTRICA RUCUE S.A.",
                    "FechaIngreso": "18/06/2012",
                    "NumeroSSDIngreso": "SSD-2012-00891",
                    "NumeroResolucion": "-1",
                    "NumeroSSDRes": None,
                    "FechaResolucion": None,
                    "Estado": "PENDIENTE",
                    "IdOposicion": 8101,
                },
                {
                    "Correlativo": 2,
                    "NombreOpositor": "ASOCIACION DE CANALISTAS DEL LAJA",
                    "FechaIngreso": "25/06/2012",
                    "NumeroSSDIngreso": "SSD-2012-00945",
                    "NumeroResolucion": "-1",
                    "NumeroSSDRes": None,
                    "FechaResolucion": None,
                    "Estado": "PENDIENTE",
                    "IdOposicion": 8102,
                },
            ]
        elif "1318" in clean_llave:
            return [
                {
                    "Correlativo": 1,
                    "NombreOpositor": "ENDESA CHILE S.A.",
                    "FechaIngreso": "30/09/1999",
                    "NumeroSSDIngreso": "ENDESA, deduce oposi",
                    "NumeroResolucion": "-1",
                    "NumeroSSDRes": None,
                    "FechaResolucion": None,
                    "Estado": "PENDIENTE",
                    "IdOposicion": 7459,
                }
            ]
        return []

    sql = """
    DECLARE @status INT, @statusDesc VARCHAR(200);
    EXEC BD_EXP.dbo.CPA_BusquedaOpExpedientes_SNIA 
        @CodigoExpediente = ?,
        @status = @status OUTPUT,
        @statusDesc = @statusDesc OUTPUT;
    """
    try:
        cur = conn.cursor()
        cur.execute(sql, (clean_llave,))
        cols = [c[0] for c in cur.description] if cur.description else []
        res = [dict(zip(cols, row)) for row in cur.fetchall()]
        cur.close()
        return res
    except Exception as exc:
        return [{"error": str(exc)}]
