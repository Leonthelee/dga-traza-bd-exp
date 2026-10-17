# DGA Módulo de Oposiciones — Backend (API REST)

**Versión:** `v1.0.0`  
**Autoría Oficial:** DGA Core Tools — by Daniel Díaz L. & AI Engine Antigravity  
**Institución:** Dirección General de Aguas (DGA) — Ministerio de Obras Públicas (MOP)  

---

## 1. Ficha Técnica

* **Lenguaje:** **Python 3.11+**
* **Framework:** **FastAPI** + **Uvicorn**
* **Bases de Datos Target:** Microsoft SQL Server 2019 (`BD_EXP` y `BD_PAR`)
* **Driver ODBC:** `ODBC Driver 18 for SQL Server` / `ODBC Driver 17`
* **Puerto:** `8000` (Configurable vía entorno)
* **Validación de Datos:** Modelos Pydantic v2 + Algoritmo canónico Módulo 11 para validación de RUT chileno.

---

## 2. Endpoints de la API REST

| Método | Endpoint | Parámetros / Body | Descripción |
|---|---|---|---|
| `GET` | `/api/health` | - | Healthcheck y estado de conexión a SQL Server. |
| `GET` | `/api/catalogo/tipos-tramite` | - | Catálogo de tipos de trámite de expedientes DGA. |
| `GET` | `/api/catalogo/regiones` | - | 16 Regiones oficiales de Chile en orden numérico (1 a 16). |
| `GET` | `/api/catalogo/provincias` | `?reg_codigo={int}` | Provincias pertenecientes a la región seleccionada. |
| `GET` | `/api/catalogo/comunas` | `?pro_codigo={int}` | Comunas pertenecientes a la provincia seleccionada. |
| `GET` | `/api/oposiciones/search` | `?reg_codigo&pro_codigo&com_codigo&tipo_tramite&exp_llave&solicitante` | Búsqueda de solicitudes y expedientes con conteo de oposiciones. |
| `GET` | `/api/oposiciones/detalle` | `?exp_codigo={str}` | Detalle y trazabilidad de oposiciones para un expediente específico. |
| `POST` | `/api/oposiciones/agregar` | `{"exp_codigo", "fecha_ingreso", "doc_nro", "opositor_nombre", "opositor_rut", "observaciones"}` | Registro transaccional de oposición (ejecuta SP `CPA_SaveIngresoOposicion_Portal` + `CPA_SaveRelacionVinculadoPerPortal`). |

---

## 3. Ejecución Local (Windows)

```powershell
# En la raíz del proyecto
.\.venv\Scripts\python.exe -m uvicorn backend.server:app --host 127.0.0.1 --port 8000 --reload
```
