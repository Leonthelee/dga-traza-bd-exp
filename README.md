# DGA Core Tools — TrazaBD_EXP (Profiler & Trazador QA / PROD)

> **Firma Oficial:** `DGA Core Tools - by Daniel Díaz L. & AI Engine Antigravity`  
> **Plataforma:** Python 3.11 + Streamlit (Kit Digital Gob.cl) + SQL Server Extended Events (XE) + SQLite

Herramienta satélite y autónoma de diagnóstico forense para capturar trazas del sistema de Oposiciones y Expedientes sobre `BD_EXP`, `BD_PAR` y `BD_MAP`. Reconstruye el árbol de procedimientos almacenados (`Exps_*`, `CPA_*`), detecta patrones anti-rendimiento (`SELECT *`, `NOLOCK`, reflexión en caliente) y genera la base de conocimiento estructurada para el Centinela RAG de `dga-bpm-orchestrator`.

---

## 🎯 Objetivo Principal: Trazabilidad de `searchSolicitudes.xhtml`

El objetivo central es auditar y mapear los **lugares de almacenamiento (tablas de `BD_EXP` y `BD_PAR`)** y la cadena de Stored Procedures que se ejecutan cuando un usuario consulta un expediente en el portal de Oposiciones:
👉 **URL:** [http://dga-snia.mop.gov.cl/oposiciones/site/solicitud/searchSolicitudes.xhtml](http://dga-snia.mop.gov.cl/oposiciones/site/solicitud/searchSolicitudes.xhtml)

### Cadena de Entrega de Información:
1. **Botón «Buscar»:** Dispara `[BD_EXP].[dbo].[CPA_BusquedaExpedientesOp]` consultando:
   - `BD_EXP..Expt_ObjetoNegocioND` (o `Trasl`, `NR`, `Obr`, `Fisc`)
   - `BD_EXP..Expt_Solicitud`
   - `BD_EXP..Expt_SituacionActualSolic`
   - `BD_PAR..Part_SituacionActual`
   - `BD_EXP..Expt_Personas`
2. **Población de Ficha:** Ejecuta 10 Stored Procedures secuenciales (`Exps_PerBuscaExpPorCodExpF10`, `Exps_SolExpSel4F6`, `Exps_TieneResApruebaF3`, `Exps_TraerRegPro`, etc.) recuperando resoluciones, titulares, fechas legales y etapas.

---

## 🔑 Configuración de Servidores: QA vs. Producción

El repositorio viene preparado con las plantillas en `.streamlit/secrets.example.toml`. El usuario/tester que ejecute la herramienta debe configurar su `.streamlit/secrets.toml` local:

### 1. Ambiente QA (Por Defecto)
- **Servidor:** `172.19.30.111`
- **Instancia:** `pro-dga-sql2019`
- **Ambiente:** `environment = "QA"`
- **Usuario QA:** `sql.soaint`

### 2. Ambiente PRODUCCIÓN (Requiere Key / Llave del Operador)
Para desplegar la traza en el clúster productivo institucional:
- **Servidor:** `172.16.71.41`
- **Instancia:** `PRO-SQLWSPCLU`
- **Ambiente:** `environment = "PROD"`
- **Usuario:** Ingresar credencial institucional autorizada (`login_filter` obligatorio para no generar overhead).
- **Seguridad:** La herramienta realiza **CERO escrituras** en las bases de datos de negocio (`BD_EXP`, `BD_PAR`, `BD_MAP`).

---

## 🚀 Arranque Rápido

1. **Configuración del entorno:**
   ```powershell
   .\Setup-QA.ps1
   ```
2. **Credenciales:**
   Copiar `.streamlit/secrets.example.toml` a `.streamlit/secrets.toml` e ingresar la clave/key correspondiente (QA o Producción).
3. **Ejecutar UI Local (Streamlit):**
   ```powershell
   .\Start-QA.ps1
   ```
   Abre en `http://localhost:8501`.
4. **Ejecutar Suite de Pruebas:**
   ```powershell
   $env:PYTHONPATH="."; .\.venv\Scripts\python.exe -m pytest -v
   ```
5. **CLI de Emergencia / Control:**
   ```powershell
   .\.venv\Scripts\python.exe qa_cli.py list
   .\.venv\Scripts\python.exe qa_cli.py stop <id_captura>
   ```

---

## 🏛️ Integración con dga-bpm-orchestrator (RAG Knowledge)

La herramienta genera automáticamente resúmenes ejecutivos en Markdown con diagramas Mermaid del árbol de llamadas y tablas de procedimientos para inyectar en el Centinela RAG:
- **Ruta de exportación:** `dga-bpm-orchestrator/backend/knowledge/05_trazabilidad_sp_bd_exp.md`
- **Uso en RAG:** Protege la generación de consultas y valida el ciclo de vida de expedientes contrastando los SPs esperados vs reales.
