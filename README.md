# DGA Core Tools — TrazaBD_EXP (Profiler & Trazador QA)

> **Firma Oficial:** `DGA Core Tools - by Daniel Díaz L. & AI Engine Antigravity`  
> **Plataforma:** Python 3.11 + Streamlit (Kit Digital Gob.cl) + SQL Server Extended Events (XE) + SQLite

Herramienta satélite y autónoma de diagnóstico forense para capturar trazas del sistema de Oposiciones y Expedientes sobre `BD_EXP`, `BD_PAR` y `BD_MAP`. Reconstruye el árbol de procedimientos almacenados (`Exps_*`, `CPA_*`), detecta patrones anti-rendimiento (`SELECT *`, `NOLOCK`, reflexión en caliente) y genera la base de conocimiento estructurada para el Centinela RAG de `dga-bpm-orchestrator`.

---

## 🚀 Arranque Rápido

1. **Configuración del entorno:**
   ```powershell
   .\Setup-QA.ps1
   ```
2. **Credenciales (Solo QA):**
   Copiar `.streamlit/secrets.example.toml` a `.streamlit/secrets.toml` y configurar la instancia de QA (servidor, XEL, login y bases).
3. **Ejecutar UI Local (Streamlit):**
   ```powershell
   .\Start-QA.ps1
   ```
   Abre automáticamente en `http://localhost:8501`. Cuenta con **Modo Demo Sintética** (sin necesidad de conexión a BD) y **Modo SQL Server QA**.
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

---

## 📁 Estructura del Proyecto

```text
dga-traza-bd-exp/
├── app.py                      # UI Streamlit (Kit Digital Gob.cl + Exportador RAG)
├── Setup-QA.ps1                # Instalador autónomo de entorno virtual (.venv)
├── Start-QA.ps1                # Lanzador de la aplicación Streamlit
├── qa_cli.py                   # CLI para listar y detener sesiones XE en caso de emergencia
├── requirements.txt            # Dependencias base (streamlit, pyodbc, pandas, openpyxl)
├── requirements-dev.txt        # Dependencias de testing (pytest, etc.)
├── .streamlit/
│   ├── config.toml             # Tema corporativo Kit Digital Gob.cl (#006FB3)
│   └── secrets.example.toml    # Plantilla de credenciales QA
├── src/
│   ├── analysis.py             # Reconstrucción de árbol SPs, métricas, baseline y patrones
│   ├── config.py               # Configuración tipada y validación de seguridad (solo QA)
│   ├── db.py                   # Conexión pyodbc y preflight checks
│   ├── demo.py                 # Datos de prueba sintéticos para modo offline
│   ├── events.py               # Parser de eventos XEL
│   ├── export.py               # Generador de CSV, Excel anti-fórmulas y Markdown RAG
│   ├── loader.py               # Carga idempotente de archivos .xel a SQLite
│   ├── service.py              # Orquestación de capturas y verificación de parada
│   ├── store.py                # Persistencia local en SQLite (data/qa.sqlite3)
│   ├── worker.py               # Worker asíncrono con timeout de 15 min y heartbeat
│   └── xe.py                   # Constructor de sesiones Extended Events
├── tests/                      # Suite de pruebas automatizadas (20 pruebas unitarias)
└── docs/                       # Especificaciones técnicas, planes y bitácora QA
```
