"""TrazaBD_EXP — piloto QA (reconstrucción conductual fiel a tests/test_app.py).

Modo Demo sintética (50 eventos) o SQL Server QA (capturas reales vía
service.prepare/launch + worker). Sin secretos configurados, el modo QA
advierte y no conecta.
"""
import pandas as pd
import streamlit as st

from src.analysis import (BASELINE, LAYERS, baseline, parameters, patterns,
                          summary, tree, tree_diagram)
from src.config import ROOT, load_settings
from src.db import connect
from src.demo import demo_events
from src.export import csv_bytes, excel_bytes, markdown_rag_summary
from src.inspector import parse_expediente, SECUENCIA_SEARCH_SOLICITUDES
from src.oposiciones import (
    agregar_oposicion,
    clean_rut,
    fetch_comunas,
    fetch_oposiciones_detalle,
    fetch_provincias,
    fetch_regiones,
    fetch_tipos_tramite,
    search_expedientes,
)
from src.service import error_text, launch, prepare, recover
from src.store import Store

st.set_page_config(
    page_title="Módulo de Oposiciones — DGA Gob.cl",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Roboto:wght@300;400;500;700;900&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Roboto', -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }
    
    /* Franja Bicolor Oficial Gob.cl */
    .gob-bicolor {
        width: 100%;
        height: 6px;
        display: flex;
        margin-bottom: 14px;
        border-radius: 2px;
        overflow: hidden;
    }
    .gob-blue-bar { width: 50%; background-color: #006fb3; }
    .gob-red-bar { width: 50%; background-color: #e53f40; }
    
    /* Cabecera Institucional MOP / DGA */
    .header-container {
        background-color: #ffffff;
        border-bottom: 2px solid #e2e8f0;
        padding: 16px 22px;
        border-radius: 8px;
        box-shadow: 0 1px 4px rgba(0,0,0,0.06);
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 20px;
    }
    .header-title {
        color: #0f172a;
        font-size: 22px;
        font-weight: 800;
        line-height: 1.25;
    }
    .header-subtitle {
        color: #006fb3;
        font-size: 13px;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .badge-mop {
        background-color: #f1f5f9;
        color: #1e293b;
        font-size: 11px;
        font-weight: 600;
        padding: 6px 12px;
        border-radius: 6px;
        border: 1px solid #cbd5e1;
    }
    
    /* Pie de página Oficial Gob.cl */
    .gob-footer {
        background-color: #ffffff;
        border-top: 1px solid #e2e8f0;
        padding: 14px 20px;
        margin-top: 40px;
        border-radius: 6px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        font-size: 12px;
        color: #64748b;
    }
    .dga-signature {
        color: #006fb3;
        font-size: 11px;
        font-weight: 600;
    }
</style>

<!-- Franja Oficial Bicolor Kit Digital Gob.cl -->
<div class="gob-bicolor">
    <div class="gob-blue-bar"></div>
    <div class="gob-red-bar"></div>
</div>

<!-- Cabecera Oficial MOP / DGA -->
<div class="header-container">
    <div>
        <div class="header-subtitle">Gobierno de Chile • Ministerio de Obras Públicas • SNIA</div>
        <div class="header-title">Dirección General de Aguas — Módulo de Oposiciones</div>
    </div>
    <div class="badge-mop">
        🏛️ Sistema Oficial • Kit Digital Gob.cl
    </div>
</div>
""", unsafe_allow_html=True)

# Panel de Telemetría y Configuración (Colapsado por defecto para mantener limpio el front institucional)
st.sidebar.markdown("### ⚙️ Telemetría & Entorno DGA")
mode = st.sidebar.radio(
    "Ambiente / Modo",
    ["Demo sintética", "Producción (172.16.71.41)", "SQL Server QA"],
    key="mode",
)

events, raws, store, cap_id, settings, settings_error = [], {}, None, None, None, None
is_db_mode = mode != "Demo sintética"
target_env = "PROD" if "Producción" in mode else "QA"

if is_db_mode:
    try:
        settings = load_settings(env=target_env)
    except Exception as exc:
        settings = None
        settings_error = str(exc)
    if settings is not None:
        store = Store()
        ids = [c["id"] for c in store.list()]
        if ids:
            cap_id = st.sidebar.selectbox("Captura", ids, key="qa_cap")
            events = store.events(cap_id)
else:
    events, raws = demo_events()

st.sidebar.metric("Eventos Telemetría", str(len(events)))

section = st.sidebar.radio(
    "Módulo / Vista",
    [
        "Módulo Oposiciones (Gob.cl)",
        "Secuencia y árbol",
        "Inspector searchSolicitudes",
        "Patrones",
        "Línea base",
        "Evidencia",
        "Control QA",
    ],
    key="section",
)

if section == "Módulo Oposiciones (Gob.cl)":
    st.subheader("Búsqueda y Consulta de Oposiciones a Solicitudes de Derechos de Aguas")
    st.caption("Módulo de consulta institucional. Reemplazo del servicio IBM BPM (Mis proyectos : Módulo de Oposiciones).")
    st.markdown("Portal Web: [dga-snia.mop.gov.cl/oposiciones/...](http://dga-snia.mop.gov.cl/oposiciones/site/solicitud/searchSolicitudes.xhtml)")

    if is_db_mode and settings is not None:
        st.info(f"🟢 **Conectado a:** `{settings.environment}` — Servidor `{settings.server}` (`{settings.expected_server_name}`) • Bases: `{', '.join(settings.databases)}`")
    elif is_db_mode and settings_error:
        st.warning(f"⚠️ **Atención:** {settings_error}. Operando en modo demostración.")

    _conn_check = {"attempted": False, "ok": False}

    def _safe_connect():
        if not is_db_mode or settings is None:
            return None
        if _conn_check["attempted"] and not _conn_check["ok"]:
            return None
        try:
            ctx = connect(settings)
            _conn_check["attempted"] = True
            _conn_check["ok"] = True
            return ctx
        except Exception:
            _conn_check["attempted"] = True
            _conn_check["ok"] = False
            return None

    def _get_tipos():
        ctx = _safe_connect()
        if ctx:
            try:
                with ctx as c:
                    return fetch_tipos_tramite(c)
            except Exception:
                pass
        return fetch_tipos_tramite(None)

    def _get_regiones():
        ctx = _safe_connect()
        if ctx:
            try:
                with ctx as c:
                    return fetch_regiones(c)
            except Exception:
                pass
        return fetch_regiones(None)

    def _get_provincias(reg: int):
        ctx = _safe_connect()
        if ctx:
            try:
                with ctx as c:
                    return fetch_provincias(reg, c)
            except Exception:
                pass
        return fetch_provincias(reg, None)

    def _get_comunas(reg: int, pro: int):
        ctx = _safe_connect()
        if ctx:
            try:
                with ctx as c:
                    return fetch_comunas(reg, pro, c)
            except Exception:
                pass
        return fetch_comunas(reg, pro, None)

    tipos_list = _get_tipos()
    regiones_list = [{"RegCodigo": 0, "RegNombre": "Todas las Regiones", "OrdenGeo": 0}] + _get_regiones()

    # 1. Filtros en Cascada
    st.markdown("##### 📍 Filtros Institucionales en Cascada (BD_PAR)")
    c_f1, c_f2, c_f3, c_f4 = st.columns(4)

    with c_f1:
        tipo_map = {f"{t['Sigla']} - {t['Descripcion']}": t["TexCodigo"] for t in tipos_list}
        tipo_labels = list(tipo_map.keys())
        tipo_sel_label = st.selectbox("Tipo de Trámite / Proceso", tipo_labels, key="opo_tipo_sel")
        selected_tex = tipo_map[tipo_sel_label]

    with c_f2:
        reg_map = {f"Región {r['RegCodigo']} - {r['RegNombre']}" if r["RegCodigo"] > 0 else r["RegNombre"]: r["RegCodigo"] for r in regiones_list}
        reg_labels = list(reg_map.keys())
        reg_sel_label = st.selectbox("Región", reg_labels, key="opo_reg_sel")
        selected_reg = reg_map[reg_sel_label]

    with c_f3:
        if selected_reg > 0:
            provs = [{"ProCodigo": 0, "ProNombre": "Todas las Provincias"}] + _get_provincias(selected_reg)
        else:
            provs = [{"ProCodigo": 0, "ProNombre": "Seleccione Región primero"}]
        pro_map = {p["ProNombre"]: p["ProCodigo"] for p in provs}
        pro_sel_label = st.selectbox("Provincia", list(pro_map.keys()), key="opo_pro_sel")
        selected_pro = pro_map[pro_sel_label]

    with c_f4:
        if selected_reg > 0 and selected_pro > 0:
            coms = [{"ComCodigo": 0, "ComNombre": "Todas las Comunas"}] + _get_comunas(selected_reg, selected_pro)
        else:
            coms = [{"ComCodigo": 0, "ComNombre": "Seleccione Provincia primero"}]
        com_map = {c["ComNombre"]: c["ComCodigo"] for c in coms}
        com_sel_label = st.selectbox("Comuna", list(com_map.keys()), key="opo_com_sel")
        selected_com = com_map[com_sel_label]

    # Filtros adicionales
    c_in1, c_in2, c_btn = st.columns([2, 2, 1])
    with c_in1:
        filtro_exp = st.text_input("Código de Expediente", placeholder="Ej: ND-0802-4437, NR-0601-1318", key="opo_exp_in")
    with c_in2:
        filtro_sol = st.text_input("Titular / Solicitante", placeholder="Ej: ASESORIAS, ENDESA, MUNICIPALIDAD", key="opo_sol_in")
    with c_btn:
        st.write("")
        st.write("")
        btn_buscar = st.button("🔍 Buscar Oposiciones", key="btn_buscar_oposiciones", type="primary")

    if btn_buscar or "opo_cached_results" not in st.session_state:
        ctx = _safe_connect()
        results = None
        if ctx:
            try:
                with ctx as c:
                    results = search_expedientes(
                        tipo_tramite=selected_tex if selected_tex > 0 else None,
                        reg_codigo=selected_reg if selected_reg > 0 else None,
                        pro_codigo=selected_pro if selected_pro > 0 else None,
                        com_codigo=selected_com if selected_com > 0 else None,
                        exp_llave=filtro_exp if filtro_exp.strip() else None,
                        solicitante=filtro_sol if filtro_sol.strip() else None,
                        limit=50,
                        conn=c,
                    )
            except Exception:
                results = None
        if not results or (results and "error" in results[0]):
            results = search_expedientes(
                tipo_tramite=selected_tex if selected_tex > 0 else None,
                reg_codigo=selected_reg if selected_reg > 0 else None,
                pro_codigo=selected_pro if selected_pro > 0 else None,
                com_codigo=selected_com if selected_com > 0 else None,
                exp_llave=filtro_exp if filtro_exp.strip() else None,
                solicitante=filtro_sol if filtro_sol.strip() else None,
                limit=50,
                conn=None,
            )
        st.session_state["opo_cached_results"] = results

    results = st.session_state.get("opo_cached_results", [])

    st.markdown("---")
    
    # Formulario Oficial de Ingreso de Oposiciones (CPA_SaveIngresoOposicion_Portal)
    with st.expander("➕ Formulario Oficial: Agregar Oposición a Expediente (CPA_SaveIngresoOposicion_Portal)", expanded=False):
        st.markdown(
            "**Procedimiento Oficial de Oposición DGA:** Registra formalmente la deducción de una oposición en "
            "`BD_EXP.dbo.CPA_SaveIngresoOposicion_Portal` vinculada al expediente correspondiente."
        )
        c_op_a1, c_op_a2 = st.columns(2)
        with c_op_a1:
            all_exp_codes = [r["ExpConcatLlave"] for r in results] if results and "ExpConcatLlave" in results[0] else ["ND-0802-4437", "ND-0802-4396", "ND-1302-413", "NR-0601-1318"]
            add_exp_choice = st.selectbox("Seleccione Expediente (o elija escribir abajo)", ["(Ingresar manualmente)"] + all_exp_codes, key="add_exp_choice")
            if add_exp_choice == "(Ingresar manualmente)":
                add_exp_codigo = st.text_input("Código de Expediente", placeholder="Ej: ND-0802-4437", key="add_exp_codigo_manual")
            else:
                add_exp_codigo = add_exp_choice
            
            import datetime
            add_fecha = st.date_input("Fecha de Ingreso de Oposición", value=datetime.date.today(), key="add_opo_fecha")
            add_doc_nro = st.text_input("N° Documento / N° SSD / Carta", placeholder="Ej: SSD-2026-00412 o CARTA-01", key="add_opo_doc")

        with c_op_a2:
            add_rut = st.text_input("RUT del Opositor", placeholder="Ej: 12345678-9", key="add_opo_rut")
            add_nombre = st.text_input("Nombre / Razón Social Opositor", placeholder="Ej: COMUNIDAD DE AGUAS CANAL EL CARMEN", key="add_opo_nombre")
            add_obs = st.text_area("Observaciones / Fundamento Legal", placeholder="Deduce oposición por eventual afectación de caudales y derechos constituidos...", key="add_opo_obs", height=100)

        btn_guardar_opo = st.button("💾 Ejecutar: Registrar Oposición en BD_EXP", type="primary", key="btn_guardar_opo")
        if btn_guardar_opo:
            if not add_exp_codigo or not add_exp_codigo.strip():
                st.error("Debe especificar un Código de Expediente válido.")
            else:
                fecha_formatted = add_fecha.strftime("%d/%m/%Y")
                ctx = _safe_connect()
                conn_to_use = None
                if ctx:
                    try:
                        conn_to_use = ctx.__enter__()
                    except Exception:
                        conn_to_use = None
                
                resp = agregar_oposicion(
                    exp_codigo=add_exp_codigo,
                    fecha_ingreso=fecha_formatted,
                    doc_nro=add_doc_nro,
                    opositor_nombre=add_nombre,
                    opositor_rut=add_rut,
                    observaciones=add_obs,
                    conn=conn_to_use,
                )
                if ctx and conn_to_use:
                    try:
                        ctx.__exit__(None, None, None)
                    except Exception:
                        pass
                
                if resp.get("success"):
                    st.success(resp.get("message"))
                    st.session_state.pop("opo_cached_results", None)
                    st.rerun()
                else:
                    st.error(resp.get("message"))

    st.markdown("##### 📋 Resultados de Solicitudes y Expedientes")

    if results and "error" in results[0]:
        st.error(f"Error al consultar base de datos: {results[0]['error']}")
    elif not results:
        st.info("No se encontraron solicitudes con los criterios indicados.")
    else:
        con_opo = sum(1 for r in results if (r.get("NumOposicionesRaw", 0) > 0) or (" - Sí" in str(r.get("NumOposiciones", ""))))
        c_m1, c_m2, c_m3 = st.columns(3)
        c_m1.metric("Expedientes Listados", len(results))
        c_m2.metric("Con Oposiciones Activas", con_opo)
        c_m3.metric("En Trámite Regular", len(results) - con_opo)

        df_res = pd.DataFrame(results)
        if "RutSolicitante" not in df_res.columns:
            df_res["RutSolicitante"] = [clean_rut(r.get("RutPasSolicitante", "")) for r in results]
        if "FechaSolicitud" not in df_res.columns:
            df_res["FechaSolicitud"] = df_res.get("FechaInicio", "S/I")

        cols_show = [
            "ExpConcatLlave",
            "RutSolicitante",
            "FechaSolicitud",
            "NumOposiciones",
            "Solicitante",
            "GLRegion",
            "GLProvincia",
            "GLComuna",
            "GLTipoDerecho",
            "Estado",
        ]
        cols_present = [c for c in cols_show if c in df_res.columns]
        rename_map = {
            "ExpConcatLlave": "Código Expediente",
            "RutSolicitante": "RUT Solicitante",
            "FechaSolicitud": "Fecha Solicitud",
            "NumOposiciones": "N° Oposiciones",
            "Solicitante": "Titular / Solicitante",
            "GLRegion": "Región",
            "GLProvincia": "Provincia",
            "GLComuna": "Comuna",
            "GLTipoDerecho": "Tipo Derecho",
            "Estado": "Estado",
        }
        df_display = df_res[cols_present].rename(columns=rename_map)
        df_display["Agregar Oposicion"] = "Agregar Oposicion"

        def on_agregar_col_click():
            click_info = st.session_state.get("btn_col_agregar_opo")
            if click_info:
                row_idx = click_info.row if hasattr(click_info, "row") else click_info.get("row")
                if row_idx is not None and 0 <= row_idx < len(results):
                    st.session_state["opo_target_exp"] = results[row_idx]["ExpConcatLlave"]
                    st.session_state["show_agregar_modal"] = True

        st.dataframe(
            df_display,
            width="stretch",
            hide_index=True,
            column_config={
                "Agregar Oposicion": st.column_config.ButtonColumn(
                    label="Agregar Oposicion",
                    help="Registrar formalmente una nueva oposición para este expediente.",
                    type="primary",
                    key="btn_col_agregar_opo",
                    on_click=on_agregar_col_click,
                ),
            },
        )

        @st.dialog("➕ Formulario Oficial: Agregar Oposición a Expediente")
        def modal_agregar_oposicion_dialog(exp_codigo: str):
            st.markdown(f"**Expediente Seleccionado:** `{exp_codigo}`")
            st.caption("Deducción formal de oposición ante la Dirección General de Aguas (`BD_EXP.dbo.CPA_SaveIngresoOposicion_Portal`).")
            
            import datetime
            c_m_1, c_m_2 = st.columns(2)
            with c_m_1:
                dlg_fecha = st.date_input("Fecha de Ingreso de Oposición", value=datetime.date.today(), key="dlg_opo_fecha")
                dlg_doc = st.text_input("N° Documento / N° SSD / Carta", placeholder="Ej: SSD-2026-00412 o CARTA-01", key="dlg_opo_doc")
            with c_m_2:
                dlg_rut = st.text_input("RUT del Opositor", placeholder="Ej: 12345678-9", key="dlg_opo_rut")
                dlg_nombre = st.text_input("Nombre / Razón Social Opositor", placeholder="Ej: COMUNIDAD DE AGUAS CANAL EL CARMEN", key="dlg_opo_nombre")
                
            dlg_obs = st.text_area("Observaciones / Fundamento Legal", placeholder="Deduce oposición por eventual afectación de caudales y derechos constituidos...", key="dlg_opo_obs", height=90)
            
            c_b1, c_b2 = st.columns([2, 1])
            with c_b1:
                btn_dlg_exec = st.button("💾 Registrar en BD_EXP", type="primary", key="btn_dlg_exec")
            with c_b2:
                btn_dlg_cancel = st.button("Cancelar", key="btn_dlg_cancel")
                
            if btn_dlg_cancel:
                st.session_state["show_agregar_modal"] = False
                st.rerun()
                
            if btn_dlg_exec:
                fecha_str = dlg_fecha.strftime("%d/%m/%Y")
                ctx = _safe_connect()
                conn_to_use = None
                if ctx:
                    try:
                        conn_to_use = ctx.__enter__()
                    except Exception:
                        conn_to_use = None
                
                resp = agregar_oposicion(
                    exp_codigo=exp_codigo,
                    fecha_ingreso=fecha_str,
                    doc_nro=dlg_doc,
                    opositor_nombre=dlg_nombre,
                    opositor_rut=dlg_rut,
                    observaciones=dlg_obs,
                    conn=conn_to_use,
                )
                if ctx and conn_to_use:
                    try:
                        ctx.__exit__(None, None, None)
                    except Exception:
                        pass
                        
                if resp.get("success"):
                    st.success(resp.get("message"))
                    st.session_state["show_agregar_modal"] = False
                    st.session_state.pop("opo_cached_results", None)
                    st.rerun()
                else:
                    st.error(resp.get("message"))

        if st.session_state.get("show_agregar_modal") and st.session_state.get("opo_target_exp"):
            modal_agregar_oposicion_dialog(st.session_state["opo_target_exp"])

        st.markdown("##### 🔎 Ficha Técnica y Detalle de Oposiciones del Expediente")
        exp_options = [r["ExpConcatLlave"] for r in results]
        selected_exp = st.selectbox("Seleccione expediente para inspeccionar:", exp_options, key="opo_selected_exp")

        if selected_exp:
            exp_row = next((r for r in results if r["ExpConcatLlave"] == selected_exp), None)
            if exp_row:
                c_d1, c_d2, c_d3, c_d4 = st.columns(4)
                c_d1.metric("Expediente", selected_exp)
                c_d2.metric("RUT Solicitante", exp_row.get("RutSolicitante", "S/I"))
                c_d3.metric("Fecha Solicitud", exp_row.get("FechaSolicitud", exp_row.get("FechaInicio", "S/I")))
                c_d4.metric("N° Oposiciones", str(exp_row.get("NumOposiciones", "0 - No")))

            t_op1, t_op2, t_op3 = st.tabs(["📑 Oposiciones Formales (SNIA)", "🗄️ Lugares de Almacenamiento (BD_EXP)", "💾 Exportar Datos"])
            with t_op1:
                st.caption(f"Detalle formal de oposiciones para `{selected_exp}` vía `BD_EXP.dbo.CPA_BusquedaOpExpedientes_SNIA`.")
                ctx = _safe_connect()
                detalle_op = None
                if ctx:
                    try:
                        with ctx as c:
                            detalle_op = fetch_oposiciones_detalle(selected_exp, conn=c)
                    except Exception:
                        detalle_op = None
                if not detalle_op or (detalle_op and "error" in detalle_op[0]):
                    detalle_op = fetch_oposiciones_detalle(selected_exp, conn=None)

                if detalle_op and "error" in detalle_op[0]:
                    st.error(f"Error al consultar oposiciones: {detalle_op[0]['error']}")
                elif not detalle_op:
                    st.info("Este expediente no registra oposiciones formales ingresadas en SNIA.")
                else:
                    st.dataframe(pd.DataFrame(detalle_op), width="stretch")

            with t_op2:
                st.caption("Tablas de almacenamiento y mapeo relacional en BD_EXP / BD_PAR:")
                st.dataframe(pd.DataFrame(SECUENCIA_SEARCH_SOLICITUDES), width="stretch")

            with t_op3:
                c_x1, c_x2 = st.columns(2)
                with c_x1:
                    st.download_button(
                        "Descargar Resultados (CSV)",
                        csv_bytes(df_res),
                        f"oposiciones_{selected_exp}.csv",
                        key="btn_dl_opo_csv"
                    )
                with c_x2:
                    st.download_button(
                        "Descargar Resultados (Excel)",
                        excel_bytes({"Resultados": df_res}),
                        f"oposiciones_{selected_exp}.xlsx",
                        key="btn_dl_opo_xlsx"
                    )

elif section == "Secuencia y árbol":
    for layer in LAYERS:
        with st.expander(layer):
            st.dataframe(summary(events, layer))
    nodes = tree(events)
    st.dataframe(pd.DataFrame(nodes))
    roots = [n["id"] for n in nodes if n["parent"] is None]
    if roots:
        root = st.selectbox("Raíz", roots, key="tree_root")
        st.code(tree_diagram(nodes, root))

elif section == "Inspector searchSolicitudes":
    st.subheader("🔍 Inspector de Expedientes (searchSolicitudes.xhtml)")
    st.caption("Visualiza los Stored Procedures y Lugares de Almacenamiento (tablas) que entrega la consulta en Oposiciones.")
    st.markdown("Portal Web: [dga-snia.mop.gov.cl/oposiciones/...](http://dga-snia.mop.gov.cl/oposiciones/site/solicitud/searchSolicitudes.xhtml)")

    col_in1, col_in2 = st.columns([2, 1])
    with col_in1:
        exp_input = st.text_input("Código de Expediente", value="ND-1204-390", key="exp_query_input")
    with col_in2:
        st.write("")
        st.write("")
        st.info("Ejemplos: `ND-1204-390`, `NR-1301-456`, `VP-0501-100`")

    exp_data = parse_expediente(exp_input)
    if exp_data:
        st.success(f"**Expediente Identificado:** `{exp_data['codigo_completo']}` — {exp_data['tipo_nombre']}")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Tipo Código (@TexCodigo)", str(exp_data["tex_codigo"]))
        c2.metric("Región (@RegCodigo)", str(exp_data["reg_codigo"]))
        c3.metric("Provincia (@ProCodigo)", str(exp_data["pro_codigo"]))
        c4.metric("Correlativo (@ExpCodigo)", str(exp_data["exp_codigo"]))

        st.subheader("📂 Lugares de Almacenamiento (Tablas) y Secuencia de SPs")
        st.dataframe(pd.DataFrame(SECUENCIA_SEARCH_SOLICITUDES))

        with st.expander("Ver Diagrama de Flujo de Datos (Mermaid)"):
            st.code(
                f'''flowchart TD
Web["searchSolicitudes.xhtml ({exp_data['codigo_completo']})"] --> SP1["1. CPA_BusquedaExpedientesOp"]
SP1 --> T1[("{exp_data['tabla_objeto_principal']}")]
SP1 --> T2[("BD_EXP..Expt_Solicitud")]
SP1 --> T3[("BD_EXP..Expt_SituacionActualSolic")]
Web --> SP2["2. 10 SPs Secuenciales (Exps_*)"]
SP2 --> T4[("BD_EXP..Expt_Expediente")]
SP2 --> T5[("BD_EXP..Expt_Resolucion")]
SP2 --> T6[("BD_PAR..Part_ClasificFuente")]
SP2 --> T7[("BD_EXP..Expt_Etapas")]
SP2 --> T8[("BD_EXP..Expt_FechasExpediente")]''',
                language="mermaid"
            )
    else:
        st.warning("Formato no reconocido. Ingrese el código con formato PREFIJO-REGIONPROVINCIA-NUMERO (ej: ND-1204-390).")

elif section == "Patrones":
    st.dataframe(patterns(events))

elif section == "Línea base":
    st.dataframe(baseline(events))
    if events:
        with st.expander("Parámetros de negocio (primera llamada)"):
            st.json(parameters(events[0].get("text", "")))

elif section == "Evidencia":
    frame = pd.DataFrame(events)
    st.dataframe(frame)
    if len(frame):
        col_dl1, col_dl2, col_dl3 = st.columns(3)
        with col_dl1:
            st.download_button("Descargar CSV", csv_bytes(frame), "evidencia.csv")
        with col_dl2:
            st.download_button("Descargar Excel",
                               excel_bytes({"Eventos": frame}), "evidencia.xlsx")
        with col_dl3:
            st.download_button("Exportar RAG Markdown (BPM)",
                               markdown_rag_summary(events),
                               "05_trazabilidad_sp_bd_exp.md",
                               mime="text/markdown", key="dl_rag_md")
    ids = [e.get("event_id", "") for e in events]
    sel = st.selectbox("Evento", ids, key="ev_sel") if ids else None
    if st.button("Ver XML crudo", key="ev_xml") and sel:
        if mode == "Demo sintética":
            st.code(raws.get(sel, ""), language="xml")
        else:
            st.code(store.raw(cap_id, sel), language="xml")

    if len(events):
        with st.expander("Sincronización directa con dga-bpm-orchestrator (RAG Knowledge)"):
            bpm_knowledge = ROOT.parent / "dga-bpm-orchestrator" / "backend" / "knowledge" / "05_trazabilidad_sp_bd_exp.md"
            st.write(f"Destino: `{bpm_knowledge}`")
            if st.button("Inyectar traza en dga-bpm-orchestrator", key="btn_sync_rag"):
                try:
                    bpm_knowledge.parent.mkdir(parents=True, exist_ok=True)
                    bpm_knowledge.write_text(markdown_rag_summary(events), encoding="utf-8")
                    st.success(f"Reglas y mapa de SPs inyectados correctamente en: {bpm_knowledge.name}")
                except Exception as ex:
                    st.error(f"Error al sincronizar: {ex}")

elif section == "Control QA":
    if mode != "SQL Server QA":
        st.info("Cambie a modo SQL Server QA para preparar capturas.")
    elif settings is None:
        st.warning(f"Sin configurar: {settings_error}")
    else:
        store = store or Store()
        label = st.text_input("Acción a probar", key="qa_label")
        profile = st.selectbox("Perfil", ["rendimiento", "detalle"],
                               key="qa_profile")
        minutes = st.number_input("Minutos (1-15)", 1, 15, 5, key="qa_minutes")
        spid = st.number_input("SPID (0 = sin filtro)", 0, 32767, 0,
                               key="qa_spid")
        threshold = st.number_input("Umbral ms (0 = sin filtro)", 0, 60000, 0,
                                    key="qa_threshold")
        if st.button("Preparar y lanzar", key="qa_launch"):
            try:
                cap = prepare(settings, label, profile, int(minutes),
                              int(spid), int(threshold))
                launch(store, cap)
                st.success(f"Captura {cap['id']} lanzada.")
            except Exception as exc:
                st.error(error_text(exc, settings))
        st.subheader("Capturas")
        st.dataframe(pd.DataFrame(store.list()))
        if st.button("Solicitar parada verificada", key="qa_stop") and cap_id:
            try:
                recover(settings, store, cap_id)
                st.success("Parada verificada en SQL Server.")
            except Exception as exc:
                st.error(error_text(exc, settings))

# Pie de Página Oficial Kit Digital Gob.cl & DGA
st.markdown("""
<footer class="gob-footer">
    <div style="display: flex; align-items: center; gap: 8px;">
        <div style="display: flex; width: 10px; height: 16px; border-radius: 2px; overflow: hidden;">
            <div style="width: 50%; background-color: #006fb3;"></div>
            <div style="width: 50%; background-color: #e53f40;"></div>
        </div>
        <span>Gobierno de Chile • Ministerio de Obras Públicas • Dirección General de Aguas</span>
    </div>
    <div class="dga-signature">
        DGA Core Tools — by Daniel Díaz L. & AI Engine Antigravity
    </div>
</footer>
""", unsafe_allow_html=True)

