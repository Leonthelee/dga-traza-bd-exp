"""Inspector y Desglosador de Expedientes para searchSolicitudes.xhtml.

Analiza códigos de expedientes (ej. ND-1204-390, NR-1301-456, VP-0501-100)
y expone el mapa exacto de Stored Procedures y Lugares de Almacenamiento
(tablas en BD_EXP, BD_PAR, BD_MAP) que entrega la consulta completa en Oposiciones.
"""
import re

TIPO_EXPEDIENTE = {
    "ND": {"nombre": "Nuevos Derechos de Aprovechamiento (ND)", "codigo": 1, "tabla_objeto": "BD_EXP..Expt_ObjetoNegocioND"},
    "NR": {"nombre": "Regularización de Derechos (NR)", "codigo": 2, "tabla_objeto": "BD_EXP..Expt_ObjetoNegocioNR"},
    "VP": {"nombre": "Obras y Proyectos (VP)", "codigo": 3, "tabla_objeto": "BD_EXP..Expt_ObjetoNegocioObr"},
    "VC": {"nombre": "Obras y Proyectos (VC)", "codigo": 3, "tabla_objeto": "BD_EXP..Expt_ObjetoNegocioObr"},
    "VT": {"nombre": "Traslados de Derechos (VT)", "codigo": 4, "tabla_objeto": "BD_EXP..Expt_ObjetoNegocioTrasl"},
    "VPC": {"nombre": "Puntos de Captación (VPC)", "codigo": 4, "tabla_objeto": "BD_EXP..Expt_ObjetoNegocioTrasl"},
    "VF": {"nombre": "Fuentes (VF)", "codigo": 4, "tabla_objeto": "BD_EXP..Expt_ObjetoNegocioTrasl"},
    "FD": {"nombre": "Fiscalización Directa (FD)", "codigo": 23, "tabla_objeto": "BD_EXP..Expt_ObjetoNegocioFisc"},
    "FO": {"nombre": "Fiscalización de Oficio (FO)", "codigo": 32, "tabla_objeto": "BD_EXP..Expt_ObjetoNegocioFisc"},
    "DEN": {"nombre": "Denuncias (DEN)", "codigo": 33, "tabla_objeto": "BD_EXP..Expt_ObjetoNegocioFisc"},
}

SECUENCIA_SEARCH_SOLICITUDES = [
    {
        "fase": "1. Búsqueda y Filtros",
        "sp": "CPA_BusquedaExpedientesOp",
        "bd": "BD_EXP",
        "accion": "Botón 'Buscar' en searchSolicitudes.xhtml",
        "tablas": ["BD_EXP..Expt_ObjetoNegocioND", "BD_EXP..Expt_Solicitud", "BD_EXP..Expt_SituacionActualSolic", "BD_PAR..Part_SituacionActual", "BD_EXP..Expt_Personas"],
        "descripcion": "Consulta central del expediente, cruza estado actual con datos de solicitante."
    },
    {
        "fase": "2. Carga Titular y Organización",
        "sp": "Exps_PerBuscaExpPorCodExpF10",
        "bd": "BD_EXP",
        "accion": "Población de datos del titular",
        "tablas": ["BD_EXP..Expt_Expediente", "BD_EXP..Expt_OrganiUsr"],
        "descripcion": "Recupera código del titular, datos de la organización y usuario responsable."
    },
    {
        "fase": "3. Resoluciones DGA",
        "sp": "Exps_TieneResApruebaF3",
        "bd": "BD_EXP",
        "accion": "Verificación resolutiva",
        "tablas": ["BD_EXP..Expt_Resolucion"],
        "descripcion": "Comprueba si el expediente cuenta con resoluciones de aprobación."
    },
    {
        "fase": "4. Firma Electrónica",
        "sp": "Exps_TieneResAprElectronicaF10",
        "bd": "BD_EXP",
        "accion": "Verificación FE",
        "tablas": ["BD_EXP..Expt_ResolucionElectronica"],
        "descripcion": "Comprueba resoluciones firmadas electrónicamente."
    },
    {
        "fase": "5. Georreferencia y Jurisdicción",
        "sp": "Exps_TraerRegPro",
        "bd": "BD_EXP",
        "accion": "Nombres geográficos",
        "tablas": ["BD_PAR..Part_Regiones", "BD_PAR..Part_Provincias"],
        "descripcion": "Traduce los códigos de región y provincia a nombres oficiales."
    },
    {
        "fase": "6. Detalle de la Solicitud",
        "sp": "Exps_SolExpSel4F6",
        "bd": "BD_EXP",
        "accion": "Carga de fuente y derecho",
        "tablas": ["BD_EXP..Expt_Solicitud", "BD_PAR..Part_ClasificFuente", "BD_PAR..Part_NaturalezaAgua", "BD_PAR..Part_TiposDerecho"],
        "descripcion": "Entrega características del agua solicitada (superficial/subterránea, consuntivo/no consuntivo)."
    },
    {
        "fase": "7. Conteo de Solicitudes",
        "sp": "Exps_CuentaSolicF3",
        "bd": "BD_EXP",
        "accion": "Multi-solicitud",
        "tablas": ["BD_EXP..Expt_Solicitud"],
        "descripcion": "Cuenta cuántas solicitudes de aprovechamiento integran el expediente."
    },
    {
        "fase": "8. Validación de Etapas",
        "sp": "Exps_ValSoliciEtapasSel",
        "bd": "BD_EXP",
        "accion": "Etapas procesales",
        "tablas": ["BD_EXP..Expt_Etapas"],
        "descripcion": "Valida si el expediente se encuentra en etapa admisible para Oposición."
    },
    {
        "fase": "9. Características de Etapa",
        "sp": "Exps_ConsCaracEtapaSel",
        "bd": "BD_EXP",
        "accion": "Parámetros de etapa",
        "tablas": ["BD_EXP..Expt_CaracEtapa"],
        "descripcion": "Determina fechas límite y observaciones asociadas a la etapa actual."
    },
    {
        "fase": "10. Calendario y Fechas Legales",
        "sp": "Exps_DatFechasExpSel",
        "bd": "BD_EXP",
        "accion": "Plazos de Oposición",
        "tablas": ["BD_EXP..Expt_FechasExpediente"],
        "descripcion": "Entrega fecha de ingreso, publicación en Diario Oficial y plazo legal de vencimiento."
    }
]


def parse_expediente(raw_codigo):
    """Desglosa un código como ND-1204-390 en sus parámetros relacionales."""
    raw = (raw_codigo or "").strip().upper()
    match = re.match(r"^([A-Z]+)\s*[-_ ]\s*(\d{1,2})(\d{2})\s*[-_ ]\s*(\d+)$", raw)
    if not match:
        alt = re.match(r"^([A-Z]+)\s*[-_ ]\s*(\d{1,2})\s*[-_ ]\s*(\d{1,2})\s*[-_ ]\s*(\d+)$", raw)
        if alt:
            pref, reg, pro, exp = alt.groups()
        else:
            return None
    else:
        pref, reg, pro, exp = match.groups()

    info_tipo = TIPO_EXPEDIENTE.get(pref, {
        "nombre": f"Trámite Especial ({pref})",
        "codigo": 0,
        "tabla_objeto": "BD_EXP..Expt_ObjetoNegocio" + pref
    })

    return {
        "codigo_completo": f"{pref}-{int(reg):02d}{int(pro):02d}-{int(exp)}",
        "prefijo": pref,
        "tipo_nombre": info_tipo["nombre"],
        "tex_codigo": info_tipo["codigo"],
        "reg_codigo": int(reg),
        "pro_codigo": int(pro),
        "exp_codigo": int(exp),
        "tabla_objeto_principal": info_tipo["tabla_objeto"],
    }
