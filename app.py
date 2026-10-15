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
from src.demo import demo_events
from src.export import csv_bytes, excel_bytes, markdown_rag_summary
from src.inspector import parse_expediente, SECUENCIA_SEARCH_SOLICITUDES
from src.service import error_text, launch, prepare, recover
from src.store import Store

st.set_page_config(page_title="TrazaBD_EXP — DGA Core Tools (Gob.cl)", layout="wide")

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
        <div class="header-subtitle">Gobierno de Chile • Ministerio de Obras Públicas</div>
        <div class="header-title">Dirección General de Aguas — Trazador & Profiler Institucional (BD_EXP / BD_PAR / BD_MAP)</div>
    </div>
    <div class="badge-mop">
        🏛️ DGA Core Tools • Kit Digital Gob.cl
    </div>
</div>
""", unsafe_allow_html=True)

mode = st.radio("Modo", ["Demo sintética", "SQL Server QA"], key="mode",
                horizontal=True)

events, raws, store, cap_id, settings = [], {}, None, None, None
if mode == "Demo sintética":
    events, raws = demo_events()
else:
    try:
        settings = load_settings()
    except Exception as exc:
        settings = None
        settings_error = str(exc)
    if settings is not None:
        store = Store()
        ids = [c["id"] for c in store.list()]
        if ids:
            cap_id = st.selectbox("Captura", ids, key="qa_cap")
            events = store.events(cap_id)

st.metric("Eventos", str(len(events)))

section = st.radio("Sección",
                   ["Secuencia y árbol", "Inspector searchSolicitudes", "Patrones", "Línea base",
                    "Evidencia", "Control QA"],
                   key="section")

if section == "Secuencia y árbol":
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

