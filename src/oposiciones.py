"""src/oposiciones.py — Módulo de Oposiciones DGA (Reemplazo oficial BPM JSP).

Conecta directamente con BD_PAR para listas desplegables en cascada (Región -> Provincia -> Comuna)
y con BD_EXP para búsqueda de solicitudes y detalle de oposiciones (CPA_BusquedaOpExpedientes_SNIA).
Incluye fallback a datos de demostración si se ejecuta en modo demo o sin conexión SQL.
"""

from typing import Any, Dict, List, Optional
from src.db import rows
from src.governance import (
    AuditLogger,
    compute_canonical_sha256,
    default_audit_logger,
    stamp_fragments_collection,
)

def clean_name(s: Any) -> str:
    """Limpia espacios y caracteres mal codificados provenientes de SQL Server (ej: Ñuble)."""
    if not s or not isinstance(s, str):
        return ""
    val = s.strip()
    return val.replace("\ufffd", "Ñ").replace("\xd1", "Ñ")


def clean_rut(r: Any) -> str:
    """Limpia ceros a la izquierda y formatea RUT/Pasaporte para visualización institucional."""
    if not r or not isinstance(r, str):
        return "S/I"
    val = r.strip().lstrip("0")
    return val if val else "S/I"


def validate_rut(rut: Any) -> bool:
    """Valida formato y dígito verificador Módulo 11 para RUT chileno."""
    if not rut or not isinstance(rut, str):
        return False
    clean = rut.strip().replace(".", "").replace(" ", "").upper()
    if "-" not in clean:
        if len(clean) < 2:
            return False
        cuerpo, dv = clean[:-1], clean[-1]
    else:
        parts = clean.split("-")
        if len(parts) != 2:
            return False
        cuerpo, dv = parts[0], parts[1]

    cuerpo = cuerpo.lstrip("0")
    if not cuerpo.isdigit() or len(cuerpo) < 6 or len(cuerpo) > 9:
        return False

    multiplicadores = [2, 3, 4, 5, 6, 7]
    suma = 0
    for i, digito in enumerate(reversed(cuerpo)):
        suma += int(digito) * multiplicadores[i % 6]
    resto = 11 - (suma % 11)
    if resto == 11:
        dv_esperado = "0"
    elif resto == 10:
        dv_esperado = "K"
    else:
        dv_esperado = str(resto)
    return dv == dv_esperado


def normalize_fecha(dt_str: Any) -> str:
    """Normaliza centinelas SQL (1900-01-01) y valores nulos a 'S/I'."""
    if not dt_str or not isinstance(dt_str, str):
        return "S/I"
    val = dt_str.strip()
    if not val or val.startswith(("01/01/1900", "1900-01-01", "1900/01/01", "01-01-1900")):
        return "S/I"
    return val



# Catálogo oficial de las 16 Regiones de Chile (Orden Numérico 1 a 16)
DEMO_REGIONES = [
    {"RegCodigo": 1, "RegNombre": "Tarapacá", "OrdenGeo": 2},
    {"RegCodigo": 2, "RegNombre": "Antofagasta", "OrdenGeo": 3},
    {"RegCodigo": 3, "RegNombre": "Atacama", "OrdenGeo": 4},
    {"RegCodigo": 4, "RegNombre": "Coquimbo", "OrdenGeo": 5},
    {"RegCodigo": 5, "RegNombre": "Valparaíso", "OrdenGeo": 6},
    {"RegCodigo": 6, "RegNombre": "del Libertador Gral. B. O'Higgins", "OrdenGeo": 8},
    {"RegCodigo": 7, "RegNombre": "del Maule", "OrdenGeo": 9},
    {"RegCodigo": 8, "RegNombre": "del Biobío", "OrdenGeo": 11},
    {"RegCodigo": 9, "RegNombre": "de La Araucanía", "OrdenGeo": 12},
    {"RegCodigo": 10, "RegNombre": "de Los Lagos", "OrdenGeo": 14},
    {"RegCodigo": 11, "RegNombre": "de Aysén del Gral. C. Ibáñez del Campo", "OrdenGeo": 15},
    {"RegCodigo": 12, "RegNombre": "de Magallanes y de la Antártica Chilena", "OrdenGeo": 16},
    {"RegCodigo": 13, "RegNombre": "Metropolitana de Santiago", "OrdenGeo": 7},
    {"RegCodigo": 14, "RegNombre": "de Los Ríos", "OrdenGeo": 13},
    {"RegCodigo": 15, "RegNombre": "Arica y Parinacota", "OrdenGeo": 1},
    {"RegCodigo": 16, "RegNombre": "de Ñuble", "OrdenGeo": 10},
]

# Catálogo oficial de las 60 Provincias de Chile por Región (BD_PAR)
DEMO_PROVINCIAS = {
    15: [{"ProCodigo": 1, "ProNombre": "Arica"}, {"ProCodigo": 2, "ProNombre": "Parinacota"}],
    1: [{"ProCodigo": 3, "ProNombre": "Iquique"}, {"ProCodigo": 4, "ProNombre": "Del Tamarugal"}],
    2: [{"ProCodigo": 3, "ProNombre": "Antofagasta"}, {"ProCodigo": 2, "ProNombre": "El Loa"}, {"ProCodigo": 1, "ProNombre": "Tocopilla"}],
    3: [{"ProCodigo": 2, "ProNombre": "Copiapó"}, {"ProCodigo": 1, "ProNombre": "Chañaral"}, {"ProCodigo": 3, "ProNombre": "Huasco"}],
    4: [{"ProCodigo": 1, "ProNombre": "Elqui"}, {"ProCodigo": 3, "ProNombre": "Choapa"}, {"ProCodigo": 2, "ProNombre": "Limarí"}],
    5: [
        {"ProCodigo": 5, "ProNombre": "Valparaíso"},
        {"ProCodigo": 7, "ProNombre": "Isla De Pascua"},
        {"ProCodigo": 2, "ProNombre": "Los Andes"},
        {"ProCodigo": 8, "ProNombre": "Marga Marga"},
        {"ProCodigo": 1, "ProNombre": "Petorca"},
        {"ProCodigo": 4, "ProNombre": "Quillota"},
        {"ProCodigo": 6, "ProNombre": "San Antonio"},
        {"ProCodigo": 3, "ProNombre": "San Felipe"},
    ],
    13: [
        {"ProCodigo": 6, "ProNombre": "Santiago"},
        {"ProCodigo": 1, "ProNombre": "Chacabuco"},
        {"ProCodigo": 2, "ProNombre": "Cordillera"},
        {"ProCodigo": 3, "ProNombre": "Maipo"},
        {"ProCodigo": 5, "ProNombre": "Melipilla"},
        {"ProCodigo": 4, "ProNombre": "Talagante"},
    ],
    6: [{"ProCodigo": 1, "ProNombre": "Cachapoal"}, {"ProCodigo": 3, "ProNombre": "Cardenal Caro"}, {"ProCodigo": 2, "ProNombre": "Colchagua"}],
    7: [{"ProCodigo": 2, "ProNombre": "Talca"}, {"ProCodigo": 4, "ProNombre": "Cauquenes"}, {"ProCodigo": 1, "ProNombre": "Curicó"}, {"ProCodigo": 3, "ProNombre": "Linares"}],
    16: [{"ProCodigo": 2, "ProNombre": "Diguillín"}, {"ProCodigo": 1, "ProNombre": "Itata"}, {"ProCodigo": 3, "ProNombre": "Punilla"}],
    8: [{"ProCodigo": 3, "ProNombre": "Concepción"}, {"ProCodigo": 4, "ProNombre": "Arauco"}, {"ProCodigo": 2, "ProNombre": "Bio-Bío"}],
    9: [{"ProCodigo": 2, "ProNombre": "Cautín"}, {"ProCodigo": 1, "ProNombre": "Malleco"}],
    14: [{"ProCodigo": 1, "ProNombre": "Valdivia"}, {"ProCodigo": 2, "ProNombre": "Ranco"}],
    10: [{"ProCodigo": 3, "ProNombre": "Llanquihue"}, {"ProCodigo": 4, "ProNombre": "Chiloé"}, {"ProCodigo": 2, "ProNombre": "Osorno"}, {"ProCodigo": 5, "ProNombre": "Palena"}],
    11: [{"ProCodigo": 2, "ProNombre": "Coyhaique"}, {"ProCodigo": 1, "ProNombre": "Aysén"}, {"ProCodigo": 4, "ProNombre": "Capitán Prat"}, {"ProCodigo": 3, "ProNombre": "General Carrera"}],
    12: [{"ProCodigo": 2, "ProNombre": "Magallanes"}, {"ProCodigo": 4, "ProNombre": "Antártica Chilena"}, {"ProCodigo": 3, "ProNombre": "Tierra Del Fuego"}, {"ProCodigo": 1, "ProNombre": "Última Esperanza"}],
}

DEMO_COMUNAS = {
    (13, 2): [
        {"ComCodigo": 1, "ComNombre": "Puente Alto"},
        {"ComCodigo": 2, "ComNombre": "Pirque"},
        {"ComCodigo": 3, "ComNombre": "San José de Maipo"},
    ],
    (13, 6): [
        {"ComCodigo": 1, "ComNombre": "Santiago Centro"},
        {"ComCodigo": 2, "ComNombre": "Providencia"},
        {"ComCodigo": 3, "ComNombre": "Las Condes"},
    ],
    (8, 2): [
        {"ComCodigo": 1, "ComNombre": "Los Ángeles"},
        {"ComCodigo": 2, "ComNombre": "Antuco"},
        {"ComCodigo": 3, "ComNombre": "Santa Bárbara"},
        {"ComCodigo": 4, "ComNombre": "Tucapel"},
    ],
    (5, 5): [
        {"ComCodigo": 1, "ComNombre": "Valparaíso"},
        {"ComCodigo": 2, "ComNombre": "Viña del Mar"},
        {"ComCodigo": 3, "ComNombre": "Concón"},
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
        "RutSolicitante": "76122587-1",
        "Solicitante": "ASESORIAS E INVERSIONES D&P DOS LIMITADA.",
        "GLRegion": "del Biobío",
        "GLProvincia": "Bio-Bio",
        "GLComuna": "Tucapel",
        "GLTipoDerecho": "No Consuntivo",
        "FechaSolicitud": "30/05/2012",
        "FechaInicio": "30/05/2012",
        "TexCodigo": 1,
        "RegCodigo": 8,
        "ProCodigo": 2,
        "ExpCodigo": 4437,
        "NumOposicionesRaw": 98,
        "NumOposiciones": "98 - Sí",
        "Estado": "CON OPOSICIÓN",
    },
    {
        "ExpConcatLlave": "ND-0802-4396",
        "NumSolicitudes": 12,
        "RutSolicitante": "76012345-5",
        "Solicitante": "SOCIEDAD DE INVERSIONES EMILUX LIMITADA",
        "GLRegion": "del Biobío",
        "GLProvincia": "Bio-Bio",
        "GLComuna": "Santa Bárbara",
        "GLTipoDerecho": "No Consuntivo",
        "FechaSolicitud": "14/03/2011",
        "FechaInicio": "14/03/2011",
        "TexCodigo": 1,
        "RegCodigo": 8,
        "ProCodigo": 2,
        "ExpCodigo": 4396,
        "NumOposicionesRaw": 49,
        "NumOposiciones": "49 - Sí",
        "Estado": "CON OPOSICIÓN",
    },
    {
        "ExpConcatLlave": "ND-1302-413",
        "NumSolicitudes": 1,
        "RutSolicitante": "69070100-6",
        "Solicitante": "ILUSTRE MUNICIPALIDAD DE PUENTE ALTO",
        "GLRegion": "Metropolitana de Santiago",
        "GLProvincia": "Cordillera",
        "GLComuna": "Puente Alto",
        "GLTipoDerecho": "Consuntivo",
        "FechaSolicitud": "18/11/2009",
        "FechaInicio": "18/11/2009",
        "TexCodigo": 1,
        "RegCodigo": 13,
        "ProCodigo": 2,
        "ExpCodigo": 413,
        "NumOposicionesRaw": 2,
        "NumOposiciones": "2 - Sí",
        "Estado": "CON OPOSICIÓN",
    },
    {
        "ExpConcatLlave": "NR-0601-1318",
        "NumSolicitudes": 1,
        "RutSolicitante": "96543210-8",
        "Solicitante": "AGRICOLA EL ARRAYAN S.A.",
        "GLRegion": "del Libertador Gral. B. O'Higgins",
        "GLProvincia": "Cachapoal",
        "GLComuna": "Rancagua",
        "GLTipoDerecho": "Consuntivo",
        "FechaSolicitud": "30/09/1999",
        "FechaInicio": "30/09/1999",
        "TexCodigo": 2,
        "RegCodigo": 6,
        "ProCodigo": 1,
        "ExpCodigo": 1318,
        "NumOposicionesRaw": 1,
        "NumOposiciones": "1 - Sí",
        "Estado": "CON OPOSICIÓN",
    },
    {
        "ExpConcatLlave": "ND-1301-5020",
        "NumSolicitudes": 1,
        "RutSolicitante": "12345678-5",
        "Solicitante": "AGROCOMERCIAL LOS ANDES LTDA.",
        "GLRegion": "Metropolitana de Santiago",
        "GLProvincia": "Santiago",
        "GLComuna": "Santiago Centro",
        "GLTipoDerecho": "Consuntivo",
        "FechaSolicitud": "15/01/2020",
        "FechaInicio": "15/01/2020",
        "TexCodigo": 1,
        "RegCodigo": 13,
        "ProCodigo": 6,
        "ExpCodigo": 5020,
        "NumOposicionesRaw": 0,
        "NumOposiciones": "0 - No",
        "Estado": "EN TRÁMITE",
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
    """Obtiene las regiones de Chile ordenadas numéricamente de 1 a 16 desde BD_PAR."""
    if conn is None:
        return DEMO_REGIONES
    try:
        data = rows(
            conn,
            "SELECT RegCodigo, RTRIM(RegNombre) as RegNombre, OrdenGeo "
            "FROM BD_PAR.dbo.Part_Region ORDER BY RegCodigo ASC"
        )
        for r in data:
            r["RegNombre"] = clean_name(r.get("RegNombre"))
        return data
    except Exception:
        return DEMO_REGIONES


def fetch_provincias(reg_codigo: int, conn=None) -> List[Dict[str, Any]]:
    """Obtiene provincias de una región desde BD_PAR (cascada)."""
    if reg_codigo <= 0:
        return []
    if conn is None:
        return DEMO_PROVINCIAS.get(reg_codigo, [{"ProCodigo": 1, "ProNombre": "Provincia Central"}])
    try:
        data = rows(
            conn,
            "SELECT ProCodigo, RTRIM(ProNombre) as ProNombre "
            "FROM BD_PAR.dbo.Part_Provincia WHERE RegCodigo = ? ORDER BY ProNombre",
            reg_codigo,
        )
        for p in data:
            p["ProNombre"] = clean_name(p.get("ProNombre"))
        return data
    except Exception:
        return DEMO_PROVINCIAS.get(reg_codigo, [])


def fetch_comunas(reg_codigo: int, pro_codigo: int, conn=None) -> List[Dict[str, Any]]:
    """Obtiene comunas de una provincia/región desde BD_PAR (cascada)."""
    if reg_codigo <= 0 or pro_codigo <= 0:
        return []
    if conn is None:
        return DEMO_COMUNAS.get((reg_codigo, pro_codigo), [{"ComCodigo": 1, "ComNombre": "Comuna Local"}])
    try:
        data = rows(
            conn,
            "SELECT ComCodigo, RTRIM(ComNombre) as ComNombre "
            "FROM BD_PAR.dbo.Part_Comuna WHERE RegCodigo = ? AND ProCodigo = ? ORDER BY ComNombre",
            reg_codigo,
            pro_codigo,
        )
        for c in data:
            c["ComNombre"] = clean_name(c.get("ComNombre"))
        return data
    except Exception:
        return DEMO_COMUNAS.get((reg_codigo, pro_codigo), [])


DEMO_OPOSICIONES_STORE: Dict[str, List[Dict[str, Any]]] = {
    "ND-0802-4437": [
        {
            "Correlativo": 1,
            "NombreOpositor": "EMPRESA ELECTRICA RUCUE S.A.",
            "RutOpositor": "96.852.140-5",
            "FechaIngreso": "18/06/2012",
            "NumeroSSDIngreso": "SSD-2012-00891",
            "NumeroResolucion": "-1",
            "NumeroSSDRes": None,
            "FechaResolucion": None,
            "Estado": "PENDIENTE",
            "IdOposicion": 8101,
            "Observaciones": "Oposición deducida dentro de plazo legal.",
        },
        {
            "Correlativo": 2,
            "NombreOpositor": "ASOCIACION DE CANALISTAS DEL LAJA",
            "RutOpositor": "70.123.456-7",
            "FechaIngreso": "25/06/2012",
            "NumeroSSDIngreso": "SSD-2012-00945",
            "NumeroResolucion": "-1",
            "NumeroSSDRes": None,
            "FechaResolucion": None,
            "Estado": "PENDIENTE",
            "IdOposicion": 8102,
            "Observaciones": "Afectación eventual a derechos de terceros constituidos.",
        },
    ],
    "NR-0601-1318": [
        {
            "Correlativo": 1,
            "NombreOpositor": "ENDESA CHILE S.A.",
            "RutOpositor": "90.001.000-K",
            "FechaIngreso": "30/09/1999",
            "NumeroSSDIngreso": "ENDESA, deduce oposi",
            "NumeroResolucion": "-1",
            "NumeroSSDRes": None,
            "FechaResolucion": None,
            "Estado": "PENDIENTE",
            "IdOposicion": 7459,
            "Observaciones": "Presentada en oficina de partes regional.",
        }
    ],
}


def search_expedientes(
    tipo_tramite: Optional[int] = None,
    reg_codigo: Optional[int] = None,
    pro_codigo: Optional[int] = None,
    com_codigo: Optional[int] = None,
    exp_llave: Optional[str] = None,
    solicitante: Optional[str] = None,
    limit: int = 50,
    conn=None,
    audit_logger: Optional[AuditLogger] = None,
) -> List[Dict[str, Any]]:
    """Busca solicitudes y expedientes en BD_EXP con conteo de oposiciones en vivo, SHA-256 por fragmento y auditoría JSONL."""
    logger = audit_logger or default_audit_logger
    query_meta = {
        "tipo_tramite": tipo_tramite,
        "reg_codigo": reg_codigo,
        "pro_codigo": pro_codigo,
        "com_codigo": com_codigo,
        "exp_llave": exp_llave,
        "solicitante": solicitante,
        "limit": limit,
    }
    env_label = "SQL" if conn is not None else "DEMO"

    if conn is None:
        res = [dict(r) for r in DEMO_RESULTADOS_BUSQUEDA]
        if tipo_tramite and tipo_tramite > 0:
            res = [r for r in res if r.get("TexCodigo") == tipo_tramite]
        if reg_codigo and reg_codigo > 0:
            res = [r for r in res if r.get("RegCodigo") == reg_codigo]
        if pro_codigo and pro_codigo > 0:
            res = [r for r in res if r.get("ProCodigo") == pro_codigo]
        if com_codigo and com_codigo > 0:
            res = [r for r in res if r.get("ComCodigo") == com_codigo]
        if exp_llave and exp_llave.strip():
            res = [r for r in res if exp_llave.strip().upper() in r.get("ExpConcatLlave", "").upper()]
        if solicitante and solicitante.strip():
            res = [r for r in res if solicitante.strip().upper() in r.get("Solicitante", "").upper()]
        for r in res:
            r["FechaSolicitud"] = normalize_fecha(r.get("FechaSolicitud"))
            r["FechaInicio"] = r["FechaSolicitud"]
        stamped, _, _ = stamp_fragments_collection(res, field_name="sha256")
        abstained = len(stamped) == 0
        logger.log_query(
            operation="search_expedientes",
            query_params=query_meta,
            fragments=stamped,
            environment=env_label,
            abstained=abstained,
            abstention_reason="ABSTENCIÓN: Cero expedientes coinciden con los filtros consultados." if abstained else None,
        )
        return stamped

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
        COALESCE(RTRIM(MAX(s.RutPasSolicitante)), '') AS RutSolicitante,
        COALESCE(RTRIM(s.Solicitante), 'Sin Titular Registrado') AS Solicitante, 
        COALESCE(RTRIM(s.GLRegion), '') AS GLRegion, 
        COALESCE(RTRIM(s.GLProvincia), '') AS GLProvincia, 
        COALESCE(RTRIM(s.GLComuna), '') AS GLComuna, 
        COALESCE(RTRIM(s.GLTipoDerecho), 'Consuntivo') AS GLTipoDerecho, 
        CASE WHEN MIN(s.FCInicioTramite) <= '1900-01-02' THEN 'S/I' 
             ELSE CONVERT(VARCHAR(10), MIN(s.FCInicioTramite), 103) END AS FechaSolicitud,
        CASE WHEN MIN(s.FCInicioTramite) <= '1900-01-02' THEN 'S/I' 
             ELSE CONVERT(VARCHAR(10), MIN(s.FCInicioTramite), 103) END AS FechaInicio,
        s.TexCodigo, s.RegCodigo, s.ProCodigo, s.ExpCodigo,
        (SELECT COUNT(DISTINCT o.CorrOpoRec) FROM BD_EXP.dbo.Expt_EtapasSolDocOpoRec o 
         WHERE o.TexCodigo = s.TexCodigo AND o.RegCodigo = s.RegCodigo 
           AND o.ProCodigo = s.ProCodigo AND o.ExpCodigo = s.ExpCodigo) AS NumOposicionesRaw
    FROM BD_EXP.dbo.SolicitudEnTramite s
    WHERE {where_clause}
    GROUP BY s.ExpConcatLlave, s.Solicitante, s.GLRegion, s.GLProvincia, s.GLComuna, s.GLTipoDerecho,
             s.TexCodigo, s.RegCodigo, s.ProCodigo, s.ExpCodigo
    ORDER BY NumOposicionesRaw DESC, s.ExpCodigo DESC
    """

    try:
        records = rows(conn, sql, *params)
        for r in records:
            raw_count = int(r.get("NumOposicionesRaw") or 0)
            r["NumOposicionesRaw"] = raw_count
            r["NumOposiciones"] = f"{raw_count} - Sí" if raw_count > 0 else "0 - No"
            r["Estado"] = "CON OPOSICIÓN" if raw_count > 0 else "EN TRÁMITE"
            r["RutSolicitante"] = clean_rut(r.get("RutSolicitante"))
            r["FechaSolicitud"] = normalize_fecha(r.get("FechaSolicitud"))
            r["FechaInicio"] = r["FechaSolicitud"]
        stamped, _, _ = stamp_fragments_collection(records, field_name="sha256")
        abstained = len(stamped) == 0
        logger.log_query(
            operation="search_expedientes",
            query_params=query_meta,
            fragments=stamped,
            environment=env_label,
            abstained=abstained,
            abstention_reason="ABSTENCIÓN: Cero expedientes coinciden en BD_EXP." if abstained else None,
        )
        return stamped
    except Exception as exc:
        logger.log_query(
            operation="search_expedientes",
            query_params=query_meta,
            fragments=[],
            environment=env_label,
            abstained=True,
            abstention_reason=f"Error SQL: {exc}",
            status="ERROR",
        )
        return [{"error": str(exc)}]


def fetch_oposiciones_detalle(
    exp_llave: str,
    conn=None,
    audit_logger: Optional[AuditLogger] = None,
) -> List[Dict[str, Any]]:
    """Ejecuta CPA_BusquedaOpExpedientes_SNIA con hash SHA-256 por fragmento y auditoría JSONL."""
    logger = audit_logger or default_audit_logger
    env_label = "SQL" if conn is not None else "DEMO"
    if not exp_llave or not exp_llave.strip():
        logger.log_query(
            operation="fetch_oposiciones_detalle",
            query_params={"exp_llave": exp_llave},
            fragments=[],
            environment=env_label,
            abstained=True,
            abstention_reason="ABSTENCIÓN: Código de expediente vacío.",
        )
        return []
    clean_llave = exp_llave.strip().upper()

    if conn is None:
        raw_res: List[Dict[str, Any]] = []
        if clean_llave in DEMO_OPOSICIONES_STORE:
            raw_res = list(DEMO_OPOSICIONES_STORE[clean_llave])
        else:
            for k, v in DEMO_OPOSICIONES_STORE.items():
                if k in clean_llave or clean_llave in k:
                    raw_res = list(v)
                    break
        stamped, _, _ = stamp_fragments_collection(raw_res, field_name="sha256")
        logger.log_query(
            operation="fetch_oposiciones_detalle",
            query_params={"exp_llave": clean_llave},
            fragments=stamped,
            environment=env_label,
            abstained=len(stamped) == 0,
            abstention_reason="Sin oposiciones registradas para el expediente." if not stamped else None,
        )
        return stamped

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
        stamped, _, _ = stamp_fragments_collection(res, field_name="sha256")
        logger.log_query(
            operation="fetch_oposiciones_detalle",
            query_params={"exp_llave": clean_llave},
            fragments=stamped,
            environment=env_label,
            abstained=len(stamped) == 0,
            abstention_reason="Sin oposiciones registradas en SNIA para el expediente." if not stamped else None,
        )
        return stamped
    except Exception as exc:
        logger.log_query(
            operation="fetch_oposiciones_detalle",
            query_params={"exp_llave": clean_llave},
            fragments=[],
            environment=env_label,
            abstained=True,
            abstention_reason=f"Error SQL: {exc}",
            status="ERROR",
        )
        return [{"error": str(exc)}]


def agregar_oposicion(
    exp_codigo: str,
    fecha_ingreso: str,
    doc_nro: str,
    opositor_nombre: str,
    opositor_rut: str,
    observaciones: str = "",
    conn=None,
    audit_logger: Optional[AuditLogger] = None,
) -> Dict[str, Any]:
    """Registra una nueva oposición formal para el expediente en BD_EXP (o en sesión de memoria).
    
    Llama a BD_EXP.dbo.CPA_SaveIngresoOposicion_Portal y vincula la persona opositora
    mediante BD_EXP.dbo.CPA_SaveRelacionVinculadoPerPortal.
    Registra auditoría estructurada JSONL y hash SHA-256 (ISO/IEC 42001).
    """
    logger = audit_logger or default_audit_logger
    env_label = "SQL" if conn is not None else "DEMO"
    tx_params = {
        "exp_codigo": exp_codigo,
        "fecha_ingreso": fecha_ingreso,
        "doc_nro": doc_nro,
        "opositor_nombre": opositor_nombre,
        "opositor_rut": opositor_rut,
    }

    def _reject(msg: str) -> Dict[str, Any]:
        res = {"success": False, "message": msg}
        res["sha256"] = compute_canonical_sha256(res)
        logger.log_query(
            operation="agregar_oposicion",
            query_params=tx_params,
            fragments=[res],
            environment=env_label,
            abstained=True,
            abstention_reason=msg,
            status="REJECTED",
        )
        return res

    if not exp_codigo or not exp_codigo.strip():
        return _reject("El código de expediente es obligatorio.")
    if len(exp_codigo.strip()) > 15:
        return _reject("El código de expediente excede el largo máximo (15 caracteres).")
    if not opositor_nombre or not opositor_nombre.strip():
        return _reject("Debe especificar el nombre o razón social del opositor.")
    if doc_nro and len(doc_nro.strip()) > 20:
        return _reject("El número de documento / SSD excede el largo máximo (20 caracteres).")
    if not opositor_rut or not validate_rut(opositor_rut):
        return _reject(f"El RUT del opositor '{opositor_rut}' no es válido (verifique formato y dígito verificador Módulo 11).")

    # Validar formato de fecha
    import datetime
    try:
        if "/" in fecha_ingreso:
            d, m, y = map(int, fecha_ingreso.split("/"))
            datetime.date(y, m, d)
        elif "-" in fecha_ingreso:
            y, m, d = map(int, fecha_ingreso.split("-"))
            datetime.date(y, m, d)
        else:
            raise ValueError()
    except Exception:
        return _reject(f"La fecha de ingreso '{fecha_ingreso}' no tiene un formato válido (DD/MM/YYYY).")

    clean_exp = exp_codigo.strip().upper()
    clean_rut_opo = clean_rut(opositor_rut)
    clean_nombre = opositor_nombre.strip()
    clean_doc = doc_nro.strip() if doc_nro else f"SSD-{fecha_ingreso.replace('/', '')}-01"

    if conn is not None:
        try:
            sql = """
            DECLARE @status INT, @statusDesc VARCHAR(200), @IdInstancia_O INT, @NumeroOposicion_O INT;
            EXEC BD_EXP.dbo.CPA_SaveIngresoOposicion_Portal
                @CodigoExpediente = ?,
                @EsdFech = ?,
                @DocNro = ?,
                @IdInstancia = NULL,
                @IdDocumentoSHP = NULL,
                @UniCodigo = 1,
                @status = @status OUTPUT,
                @statusDesc = @statusDesc OUTPUT,
                @IdInstancia_O = @IdInstancia_O OUTPUT,
                @NumeroOposicion_O = @NumeroOposicion_O OUTPUT;

            IF @IdInstancia_O IS NOT NULL AND @IdInstancia_O > 0
            BEGIN
                DECLARE @st2 INT, @stDesc2 VARCHAR(200);
                EXEC BD_EXP.dbo.CPA_SaveRelacionVinculadoPerPortal
                    @IdInstancia = @IdInstancia_O,
                    @PerRut = ?,
                    @PerCorrRut = 1,
                    @PerCorrDir = 1,
                    @EtaCodigo = 1,
                    @orden = 1,
                    @status = @st2 OUTPUT,
                    @statusDesc = @stDesc2 OUTPUT;
            END

            SELECT @status AS status, @statusDesc AS statusDesc, @IdInstancia_O AS IdInstancia, @NumeroOposicion_O AS NumeroOposicion;
            """
            cur = conn.cursor()
            cur.execute(sql, (clean_exp, fecha_ingreso, clean_doc, clean_rut_opo))
            row = cur.fetchone()
            cur.close()
            conn.commit()

            if row:
                st_code, st_desc, id_inst, num_opo = row[0], row[1], row[2], row[3]
                if st_code == 0 or (id_inst and id_inst > 0):
                    out = {
                        "success": True,
                        "message": f"Oposición registrada exitosamente en BD_EXP. Instancia N° {id_inst}, N° Oposición: {num_opo}",
                        "id_instancia": id_inst,
                        "numero_oposicion": num_opo,
                        "expediente": clean_exp,
                    }
                    out["sha256"] = compute_canonical_sha256(out)
                    logger.log_query(
                        operation="agregar_oposicion",
                        query_params=tx_params,
                        fragments=[out],
                        environment=env_label,
                        abstained=False,
                    )
                    return out
                else:
                    return _reject(f"Error retornado por CPA_SaveIngresoOposicion_Portal: {st_desc} (código {st_code})")
            out = {
                "success": True,
                "message": "Oposición registrada en BD_EXP.",
                "expediente": clean_exp,
            }
            out["sha256"] = compute_canonical_sha256(out)
            logger.log_query(
                operation="agregar_oposicion",
                query_params=tx_params,
                fragments=[out],
                environment=env_label,
                abstained=False,
            )
            return out
        except Exception as exc:
            return _reject(f"Error SQL al registrar oposición: {str(exc)}")

    # Modo Demostración / Memoria Local
    import random
    new_id = random.randint(8200, 9999)
    existing_list = DEMO_OPOSICIONES_STORE.setdefault(clean_exp, [])
    new_correlativo = len(existing_list) + 1

    new_entry = {
        "Correlativo": new_correlativo,
        "NombreOpositor": clean_nombre,
        "RutOpositor": clean_rut_opo,
        "FechaIngreso": fecha_ingreso,
        "NumeroSSDIngreso": clean_doc,
        "NumeroResolucion": "-1",
        "NumeroSSDRes": None,
        "FechaResolucion": None,
        "Estado": "PENDIENTE",
        "IdOposicion": new_id,
        "Observaciones": observaciones.strip() if observaciones else "Ingreso manual desde Portal DGA Gob.cl",
    }
    new_entry["sha256"] = compute_canonical_sha256(new_entry)
    existing_list.append(new_entry)

    for item in DEMO_RESULTADOS_BUSQUEDA:
        if item["ExpConcatLlave"].upper() == clean_exp:
            item["NumOposicionesRaw"] = item.get("NumOposicionesRaw", 0) + 1
            item["NumOposiciones"] = f"{item['NumOposicionesRaw']} - Sí"
            item["Estado"] = "CON OPOSICIÓN"
            break

    out = {
        "success": True,
        "message": f"Oposición registrada exitosamente en BD_EXP (Modo Simulación). Instancia N° {new_id}, N° Oposición: {new_correlativo}",
        "id_instancia": new_id,
        "numero_oposicion": new_correlativo,
        "expediente": clean_exp,
    }
    out["sha256"] = compute_canonical_sha256(out)
    logger.log_query(
        operation="agregar_oposicion",
        query_params=tx_params,
        fragments=[new_entry, out],
        environment=env_label,
        abstained=False,
    )
    return out


