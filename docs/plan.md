# TrazaBD_EXP App Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Python + Streamlit trace app for BD_PAR / BD_EXP / BD_MAP in `C:\Users\daniel.diaz\Music\TrazaBD_EXP`.

**Architecture:** Thin Streamlit UI over 5 focused modules: config (constants), db (pyodbc), trace (sp_trace batch builders + runners), loader (.trc → TrazaDB staging + registry), analysis (pure pandas: top queries, SP tree, @UsrLogin extractor, pattern hunter, baseline comparator).

**Tech Stack:** Python >= 3.11, Streamlit >= 1.32, pyodbc >= 5.0 + ODBC Driver 18 for SQL Server, pandas >= 2.0, openpyxl >= 3.1, pytest >= 8.0, SQL Server 2014–2019 sp_trace API.

## Global Constraints

- Target SQL Server is 2014–2019: use ONLY sp_trace API (10 RPC:Completed, 12 SQL:BatchCompleted, 45 SP:StmtCompleted), never Extended Events DDL.
- Duration column is in MICROSECONDS (500 ms = 500000).
- Trace files live on the SERVER (e.g. `C:\traces\legacy_mapa` + rollover); app never writes to BD_PAR / BD_EXP / BD_MAP, only reads + creates traces; all staging goes to TrazaDB.
- App login is least-privilege with ALTER TRACE; credentials ONLY in `.streamlit/secrets.toml`, never in code.
- Streamlit binds to internal IP only; TDD with pytest; one commit per task.
- Filter DBs are exactly: BD_PAR, BD_EXP, BD_MAP. App login filter is XXXX.

---

### Task 1: Scaffold + config + baseline data

**Files:**
- Create: `TrazaBD_EXP/requirements.txt`
- Create: `TrazaBD_EXP/.streamlit/secrets.toml.example`
- Create: `TrazaBD_EXP/src/__init__.py`
- Create: `TrazaBD_EXP/src/config.py`
- Create: `TrazaBD_EXP/src/baseline.py`
- Create: `TrazaBD_EXP/tests/test_config.py`
- Create: `TrazaBD_EXP/README.md`

**Interfaces:**
- Consumes: nothing.
- Produces: `src.config` (APP_DBS, APP_LOGIN, TRACE_EVENTS, BASE_COLUMNS, EXTRA_45, EXTRA_10_12, TRACE_PATH_DEFAULT, TRACE_MB, TRACE_FILES), `src.baseline.BASELINE: dict[str, list[str]]` used by Task 6.

- [ ] **Step 1: Write requirements.txt**

```text
streamlit>=1.32
pyodbc>=5.0
pandas>=2.0
openpyxl>=3.1
pytest>=8.0
```

- [ ] **Step 2: Write secrets template**

```toml
# Copiar a .streamlit/secrets.toml y completar. NUNCA commitear el real.
[sql]
server = "172.19.30.111"
database = "master"
trusted = true
username = ""
password = ""
trace_login = "traza_app"
```

- [ ] **Step 3: Write src/config.py**

```python
APP_DBS = ("BD_PAR", "BD_EXP", "BD_MAP")
APP_LOGIN = "XXXX"
TRACE_EVENTS = (10, 12, 45)
BASE_COLUMNS = (1, 10, 11, 12, 13, 14, 15, 16, 17, 18, 27, 35)
EXTRA_10_12 = (49,)
EXTRA_45 = (29, 31, 34, 49)
TRACE_PATH_DEFAULT = r"C:\traces\legacy_mapa"
TRACE_MB = 500
TRACE_FILES = 5
TRACEDB = "TrazaDB"
```

- [ ] **Step 4: Write src/baseline.py (línea base del PDF QA)**

```python
BASELINE = {
    "Buscar (grilla solicitudes)": ["CPA_BusquedaExpedientesOp", "CPA_getProvincias", "CPA_getComunas"],
    "Buscar Opositor": ["CPA_getCorrelativoPersona"],
    "Seleccionar Persona": ["CPA_getPersona"],
    "Agregar Opositor (puebla pantalla)": [
        "Exps_PerBuscaExpPorCodExpF10", "Exps_TieneResApruebaF3",
        "Exps_TieneResAprElectronicaF10", "Exps_TraerRegPro",
        "Exps_SolExpSel4F6", "Exps_CuentaSolicF3", "Exps_ValSoliciEtapasSel",
        "Exps_SolEtDatSel4F4", "Exps_ConsCaracEtapaSel", "Exps_DatFechasExpSel",
    ],
    "Guardar Oposicion": ["CPA_SaveIngresoVinculado_OP"],
    "Ver Oposiciones": ["CPA_BusquedaOpExpedientes", "CPA_BusquedaExpedientesOp"],
    "Abrir": ["CPA_BusquedaListaOpositores", "CPA_DetalleOposicion",
              "CPA_getUniDgaRegion", "MAP_getCuencasPorRegion"],
    "Guardar Traslado": ["CPA_SaveIngresoTraslado_OP"],
    "Guardar Respuesta": ["CPA_SaveIngresoRespuesta_OP"],
    "Guardar Resolucion": ["CPA_SaveResolucionVin_OP"],
}
```

- [ ] **Step 5: Write failing test tests/test_config.py**

```python
from src import config
from src.baseline import BASELINE


def test_trace_constants():
    assert config.APP_DBS == ("BD_PAR", "BD_EXP", "BD_MAP")
    assert config.APP_LOGIN == "XXXX"
    assert config.TRACE_EVENTS == (10, 12, 45)
    assert 29 in config.EXTRA_45 and 49 in config.EXTRA_45


def test_baseline_covers_agregar_opositor():
    assert len(BASELINE["Agregar Opositor (puebla pantalla)"]) == 10
    assert "Exps_SolExpSel4F6" in BASELINE["Agregar Opositor (puebla pantalla)"]
```

- [ ] **Step 6: Run tests**

Run: `pytest tests/test_config.py -v`
Expected: PASS (2 passed)

- [ ] **Step 7: Write README.md (cómo crear venv, instalar, correr, desplegar)**

```markdown
# TrazaBD_EXP
1. `py -m venv .venv` y activar
2. `pip install -r requirements.txt` (requiere ODBC Driver 18 for SQL Server)
3. Copiar `.streamlit/secrets.toml.example` a `.streamlit/secrets.toml` y completar
4. `pytest` (todo verde) y `streamlit run app.py --server.address <IP interna>`
```

- [ ] **Step 8: Init repo + commit**

```bash
git init
git add requirements.txt .streamlit/secrets.toml.example src/__init__.py src/config.py src/baseline.py tests/test_config.py README.md
git commit -m "feat: scaffold + config + baseline QA"
```

### Task 2: db.py connection helper

**Files:**
- Create: `TrazaBD_EXP/src/db.py`
- Create: `TrazaBD_EXP/tests/test_db.py`

**Interfaces:**
- Consumes: `src.config` constants for defaults.
- Produces: `src.db.get_connection(server, database="master", username="", password="", trusted=True, timeout=15) -> pyodbc.Connection` used by Tasks 3–4 and app.py.

- [ ] **Step 1: Write failing test**

```python
from unittest.mock import patch
from src import db


def test_trusted_connection_string():
    with patch.object(db.pyodbc, "connect", return_value="CNX") as c:
        assert db.get_connection("SRV", database="BD_PAR") == "CNX"
        cs = c.call_args.args[0]
        assert "SERVER=SRV" in cs and "DATABASE=BD_PAR" in cs
        assert "Trusted_Connection=yes" in cs
        assert "ODBC Driver 18 for SQL Server" in cs


def test_sql_auth_connection_string():
    with patch.object(db.pyodbc, "connect", return_value="CNX") as c:
        db.get_connection("SRV", username="u", password="p", trusted=False)
        cs = c.call_args.args[0]
        assert "UID=u" in cs and "PWD=p" in cs
        assert "Trusted_Connection" not in cs
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_db.py -v`
Expected: FAIL with "No module named 'src.db'" or "cannot import name"

- [ ] **Step 3: Write minimal implementation src/db.py**

```python
import pyodbc


def get_connection(server, database="master", username="", password="",
                   trusted=True, timeout=15):
    if trusted:
        cs = (f"DRIVER={{ODBC Driver 18 for SQL Server}};SERVER={server};"
              f"DATABASE={database};Trusted_Connection=yes;"
              f"TrustServerCertificate=yes;Connection Timeout={timeout};")
    else:
        cs = (f"DRIVER={{ODBC Driver 18 for SQL Server}};SERVER={server};"
              f"DATABASE={database};UID={username};PWD={password};"
              f"TrustServerCertificate=yes;Connection Timeout={timeout};")
    return pyodbc.connect(cs, timeout=timeout)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/ -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add src/db.py tests/test_db.py
git commit -m "feat: db connection helper with trusted/sql auth"
```

### Task 3: trace.py server-side trace control

**Files:**
- Create: `TrazaBD_EXP/src/trace.py`
- Create: `TrazaBD_EXP/tests/test_trace.py`

**Interfaces:**
- Consumes: `src.config` (events, columns, DBs, login, path defaults), a DBAPI connection from `src.db`.
- Produces: `build_start_batch(dbs, login, path, max_mb, filecount, min_duration_us=0) -> str`, `run_start_batch(conn, batch) -> int`, `stop_trace(conn, traceid)`, `delete_trace(conn, traceid)`, `list_traces(conn) -> list` used by app.py Control tab.

- [ ] **Step 1: Write failing test**

```python
from src import trace
from src.config import APP_DBS


def test_start_batch_contains_events_columns_filters():
    b = trace.build_start_batch(APP_DBS, "XXXX", r"C:\traces\legacy_mapa", 500, 5)
    assert "sp_trace_create @tid OUTPUT, 2," in b
    assert "sp_trace_setevent @tid, 45, 29, 1" in b  # NestLevel
    assert "sp_trace_setevent @tid, 10, 13, 1" in b  # Duration
    assert "sp_trace_setfilter @tid, 35, 0, 0, N'BD_PAR'" in b
    assert "sp_trace_setfilter @tid, 35, 1, 0, N'BD_EXP'" in b  # OR
    assert "sp_trace_setfilter @tid, 35, 1, 0, N'BD_MAP'" in b  # OR
    assert "sp_trace_setfilter @tid, 11, 0, 0, N'XXXX'" in b
    assert "sp_trace_setstatus @tid, 1" in b


def test_run_start_batch_returns_traceid():
    from unittest.mock import MagicMock
    cur = MagicMock()
    cur.fetchone.side_effect = [None, (7,)]
    cur.nextset.side_effect = [True, False]
    conn = MagicMock()
    conn.cursor.return_value = cur
    assert trace.run_start_batch(conn, "BATCH") == 7
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_trace.py -v`
Expected: FAIL (module missing)

- [ ] **Step 3: Write minimal implementation src/trace.py**

```python
from src.config import (APP_DBS, APP_LOGIN, TRACE_EVENTS, BASE_COLUMNS,
                        EXTRA_10_12, EXTRA_45, TRACE_PATH_DEFAULT,
                        TRACE_MB, TRACE_FILES)


def _cols(ev):
    if ev == 45:
        return BASE_COLUMNS + EXTRA_45
    return BASE_COLUMNS + EXTRA_10_12


def build_start_batch(dbs=APP_DBS, login=APP_LOGIN, path=TRACE_PATH_DEFAULT,
                      max_mb=TRACE_MB, filecount=TRACE_FILES,
                      min_duration_us=0):
    L = [f"DECLARE @tid INT;",
         f"EXEC sp_trace_create @tid OUTPUT, 2, N'{path}', {max_mb}, NULL, {filecount};"]
    for ev in TRACE_EVENTS:
        for col in _cols(ev):
            L.append(f"EXEC sp_trace_setevent @tid, {ev}, {col}, 1;")
    L.append(f"EXEC sp_trace_setfilter @tid, 35, 0, 0, N'{dbs[0]}';")
    for db in dbs[1:]:
        L.append(f"EXEC sp_trace_setfilter @tid, 35, 1, 0, N'{db}';")
    L.append(f"EXEC sp_trace_setfilter @tid, 11, 0, 0, N'{login}';")
    L.append("EXEC sp_trace_setfilter @tid, 10, 0, 7, N'%SQL Server Profiler%';")
    L.append("EXEC sp_trace_setfilter @tid, 10, 0, 7, N'%Management Studio%';")
    if min_duration_us > 0:
        L.append(f"EXEC sp_trace_setfilter @tid, 13, 0, 4, {int(min_duration_us)};")
    L.append("EXEC sp_trace_setstatus @tid, 1;")
    L.append("SELECT @tid AS traceid;")
    return "\n".join(L)


def run_start_batch(conn, batch):
    cur = conn.cursor()
    cur.execute(batch)
    while True:
        try:
            row = cur.fetchone()
        except Exception:
            row = None
        if row is not None:
            return int(row[0])
        if not cur.nextset():
            raise RuntimeError("sp_trace_create no devolvio traceid")


def stop_trace(conn, traceid):
    conn.cursor().execute(f"EXEC sp_trace_setstatus {int(traceid)}, 0;")


def delete_trace(conn, traceid):
    conn.cursor().execute(f"EXEC sp_trace_setstatus {int(traceid)}, 2;")


def list_traces(conn):
    cur = conn.cursor()
    cur.execute("SELECT id, path FROM sys.traces WHERE is_default = 0;")
    return cur.fetchall()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/ -v`
Expected: PASS (6 passed)

- [ ] **Step 5: Commit**

```bash
git add src/trace.py tests/test_trace.py
git commit -m "feat: server-side trace control (3 DBs OR filter, nest cols)"
```

### Task 4: loader.py .trc to TrazaDB

**Files:**
- Create: `TrazaBD_EXP/src/loader.py`
- Create: `TrazaBD_EXP/tests/test_loader.py`

**Interfaces:**
- Consumes: DBAPI connection; trace path from Task 3 run.
- Produces: `table_name_for(label) -> str`, `build_load_sql(trace_path, table, run_id) -> str`, `load_trace(conn, trace_path, label) -> str (table)`, `register_run(conn, table, label)` used by app.py.

- [ ] **Step 1: Write failing test**

```python
from src import loader


def test_table_name_format():
    assert loader.table_name_for("20261014_0830") == "TraceLog_20261014_0830"


def test_load_sql_uses_all_rollovers_and_registry():
    sql = loader.build_load_sql(r"C:\traces\legacy_mapa", "TraceLog_X", "RID")
    assert "fn_trace_gettable(N'C:\\traces\\legacy_mapa.trc', DEFAULT)" in sql
    assert "INTO TrazaDB.dbo.TraceLog_X" in sql
    assert "ExecutionID" in sql


def test_load_trace_executes_and_registers():
    from unittest.mock import MagicMock
    conn = MagicMock()
    t = loader.load_trace(conn, r"C:\traces\legacy_mapa", "20261014_0830")
    assert t == "TraceLog_20261014_0830"
    executed = " ".join(c.args[0] for c in conn.cursor().execute.call_args_list)
    assert "fn_trace_gettable" in executed and "TraceRuns" in executed
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_loader.py -v`
Expected: FAIL (module missing)

- [ ] **Step 3: Write minimal implementation src/loader.py**

```python
import uuid
from src.config import TRACEDB


def table_name_for(label):
    safe = "".join(c if (c.isalnum() or c == "_") else "_" for c in label)
    return f"TraceLog_{safe}"


def build_load_sql(trace_path, table, run_id):
    return (
        f"IF OBJECT_ID(N'{TRACEDB}.dbo.{table}', 'U') IS NOT NULL "
        f"DROP TABLE {TRACEDB}.dbo.{table};\n"
        f"SELECT t.*, CAST('{run_id}' AS UNIQUEIDENTIFIER) AS ExecutionID, "
        f"SYSDATETIME() AS LoadedAt\n"
        f"INTO {TRACEDB}.dbo.{table}\n"
        f"FROM fn_trace_gettable(N'{trace_path}.trc', DEFAULT) AS t;\n"
        f"IF OBJECT_ID(N'{TRACEDB}.dbo.TraceRuns', 'U') IS NULL "
        f"CREATE TABLE {TRACEDB}.dbo.TraceRuns "
        f"(RunID UNIQUEIDENTIFIER PRIMARY KEY, [Table] SYSNAME, LoadedAt DATETIME2);\n"
        f"INSERT INTO {TRACEDB}.dbo.TraceRuns (RunID, [Table], LoadedAt) "
        f"VALUES (CAST('{run_id}' AS UNIQUEIDENTIFIER), N'{table}', SYSDATETIME());"
    )


def register_run(conn, table, label):
    return table


def load_trace(conn, trace_path, label):
    table = table_name_for(label)
    run_id = str(uuid.uuid4())
    cur = conn.cursor()
    for stmt in build_load_sql(trace_path, table, run_id).split(";\n"):
        if stmt.strip():
            cur.execute(stmt + ";")
    register_run(conn, table, label)
    return table
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/ -v`
Expected: PASS (9 passed)

- [ ] **Step 5: Commit**

```bash
git add src/loader.py tests/test_loader.py
git commit -m "feat: load trc rollovers into TrazaDB staging + registry"
```

### Task 5: analysis.py pure-pandas maps

**Files:**
- Create: `TrazaBD_EXP/src/analysis.py`
- Create: `TrazaBD_EXP/tests/test_analysis.py`

**Interfaces:**
- Consumes: DataFrame with trace columns (TextData, EventClass, SPID, RequestID, NestLevel, StartTime, Duration, Reads, ObjectName).
- Produces: `fingerprint(sql)`, `top_queries(df, n=20)`, `top_procs(df, n=20)`, `build_tree(df)`, `extract_usrlogin(df)`, `find_patterns(df)`, `compare_baseline(df, baseline)` used by Tasks 6–7 and app.py.

- [ ] **Step 1: Write failing test**

```python
import pandas as pd
from src import analysis as A

DF = pd.DataFrame([
    {"EventClass": 10, "TextData": "exec dbo.CPA_getProvincias 12,@p2 output,@p3 output",
     "SPID": 51, "RequestID": 0, "NestLevel": 1, "StartTime": "2026-10-14 08:00:00",
     "Duration": 2000000, "Reads": 100, "ObjectName": None},
    {"EventClass": 45, "TextData": "SELECT * FROM Detalle WHERE id=5",
     "SPID": 51, "RequestID": 0, "NestLevel": 2, "StartTime": "2026-10-14 08:00:01",
     "Duration": 1900000, "Reads": 9000, "ObjectName": "CPA_BusquedaExpedientesOp"},
    {"EventClass": 12, "TextData": "exec BD_EXP.dbo.Exps_SolExpSel4F6 @TexCodigo=1,@UsrLogin='cpa_admin '",
     "SPID": 52, "RequestID": 0, "NestLevel": 1, "StartTime": "2026-10-14 08:00:02",
     "Duration": 500000, "Reads": 50, "ObjectName": None},
])


def test_fingerprint_normalizes_literals():
    assert A.fingerprint("exec dbo.P 12,N'ND-1204-390'") == "EXEC DBO.P ?,?"


def test_top_queries_orders_by_total_seconds():
    top = A.top_queries(DF)
    assert top.iloc[0]["TotalSeg"] == 2.0


def test_tree_nests_by_nestlevel():
    tree = A.build_tree(DF)
    assert len(tree) == 2
    kids = tree[0]["children"]
    assert len(kids) == 1 and kids[0]["object"] == "CPA_BusquedaExpedientesOp"


def test_usrlogin_extracted_only_from_exps():
    s = A.extract_usrlogin(DF)
    assert s.iloc[2] == "cpa_admin"


def test_patterns_catch_select_star():
    p = A.find_patterns(DF)
    assert "SELECT *" in set(p["Patron"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_analysis.py -v`
Expected: FAIL (module missing)

- [ ] **Step 3: Write minimal implementation src/analysis.py**

```python
import re
import pandas as pd

_STR = re.compile(r"N?'([^']|'')*'")
_NUM = re.compile(r"\b\d+(\.\d+)?\b")
_WS = re.compile(r"\s+")
_PROC = re.compile(r"exec\s+(?:\[[^\]]+\]\.)?(?:dbo\.)?\[?([A-Za-z_][\w$#]*)\]?",
                   re.IGNORECASE)
_USR = re.compile(r"@UsrLogin\s*=\s*N?'([^']*)'", re.IGNORECASE)
PATTERNS = [
    ("SELECT *", re.compile(r"SELECT\s+\*", re.IGNORECASE)),
    ("NOLOCK", re.compile(r"NOLOCK", re.IGNORECASE)),
    ("CONVERT no sargable", re.compile(r"CONVERT\s*\(", re.IGNORECASE)),
    ("Cursor", re.compile(r"\bCURSOR\b", re.IGNORECASE)),
    ("Reflection DAL", re.compile(r"sp_sproc_columns|sp_stored_procedures",
                                  re.IGNORECASE)),
    ("Solo outputs", re.compile(r"^\s*select\s+@p\d[\s,@\w]*$",
                                re.IGNORECASE | re.MULTILINE)),
]


def fingerprint(sql):
    s = _STR.sub("?", sql or "")
    s = _NUM.sub("?", s)
    return _WS.sub(" ", s).strip().upper()[:400]


def _with_fp(df):
    df = df.copy()
    df["fp"] = df["TextData"].map(fingerprint)
    return df


def top_queries(df, n=20):
    g = _with_fp(df).groupby(["EventClass", "fp"], dropna=False)
    out = g.agg(Ejecuciones=("Duration", "size"),
                TotalUs=("Duration", "sum"),
                PromReads=("Reads", "mean")).reset_index()
    out["TotalSeg"] = (out["TotalUs"] / 1e6).round(1)
    return out.sort_values("TotalSeg", ascending=False).head(n)


def proc_of(text, obj):
    if isinstance(obj, str) and obj:
        return obj
    m = _PROC.search(text or "")
    return m.group(1) if m else "(ad-hoc)"


def top_procs(df, n=20):
    d = df.copy()
    d["proc"] = [proc_of(t, o) for t, o in zip(d["TextData"], d["ObjectName"])]
    g = d.groupby("proc")
    out = g.agg(Ejecuciones=("Duration", "size"),
                TotalUs=("Duration", "sum"),
                AvgReads=("Reads", "mean")).reset_index()
    out["TotalSeg"] = (out["TotalUs"] / 1e6).round(1)
    return out.sort_values("TotalSeg", ascending=False).head(n)


def build_tree(df):
    stmts = df[df["EventClass"] == 45].copy()
    roots = df[df["EventClass"].isin((10, 12))].copy()
    trees = []
    for _, r in roots.sort_values("StartTime").iterrows():
        kids = stmts[(stmts["SPID"] == r["SPID"])
                     & (stmts["RequestID"] == r["RequestID"])]
        kids = kids.sort_values("StartTime")
        node = {"object": proc_of(r["TextData"], r["ObjectName"]),
                "ms": round(r["Duration"] / 1000.0, 1), "children": []}
        stack = [(1, node)]
        for _, k in kids.iterrows():
            lvl = int(k["NestLevel"] or 2)
            while stack and stack[-1][0] >= lvl:
                stack.pop()
            child = {"object": proc_of(k["TextData"], k["ObjectName"]),
                     "text": (k["TextData"] or "")[:300],
                     "ms": round(k["Duration"] / 1000.0, 1), "children": []}
            (stack[-1][1] if stack else node)["children"].append(child)
            stack.append((lvl, child))
        trees.append(node)
    return trees


def extract_usrlogin(df):
    def one(t):
        m = _USR.search(t or "")
        return m.group(1).strip() if m else None
    return df["TextData"].map(one)


def find_patterns(df):
    rows = []
    for name, rx in PATTERNS:
        hit = df[df["TextData"].str.contains(rx, na=False)]
        if len(hit):
            rows.append({"Patron": name, "Ocurrencias": len(hit),
                         "Ejemplo": hit.iloc[0]["TextData"][:300]})
    return pd.DataFrame(rows, columns=["Patron", "Ocurrencias", "Ejemplo"])


def compare_baseline(df, baseline):
    traced = set()
    for t, o in zip(df["TextData"], df["ObjectName"]):
        traced.add(proc_of(t, o))
    rows = []
    for button, expected in baseline.items():
        for proc in expected:
            rows.append({"Boton": button, "Procedimiento": proc,
                         "EnTraza": proc in traced})
    extra = sorted(p for p in traced
                   if p != "(ad-hoc)" and not any(p in v for v in baseline.values()))
    for proc in extra:
        rows.append({"Boton": "(ninguno)", "Procedimiento": proc,
                     "EnTraza": True})
    return pd.DataFrame(rows)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/ -v`
Expected: PASS (14 passed)

- [ ] **Step 5: Commit**

```bash
git add src/analysis.py tests/test_analysis.py
git commit -m "feat: maps, SP tree, usrlogin extractor, pattern hunter"
```

### Task 6: app.py Streamlit UI

**Files:**
- Create: `TrazaBD_EXP/app.py`

**Interfaces:**
- Consumes: `src.config/dB/trace/loader/analysis/baseline` + `st.secrets["sql"]`.
- Produces: running UI with tabs Control, Mapa, Arbol, Patrones, Baseline + CSV/Excel download.

- [ ] **Step 1: Write app.py**

```python
import io
import pandas as pd
import streamlit as st
from src import db
from src.config import APP_DBS, APP_LOGIN, TRACE_PATH_DEFAULT
from src.trace import (build_start_batch, run_start_batch, stop_trace,
                       delete_trace, list_traces)
from src.loader import load_trace
from src.analysis import (top_queries, top_procs, build_tree,
                          find_patterns, compare_baseline)
from src.baseline import BASELINE

st.set_page_config(page_title="TrazaBD_EXP", layout="wide")
st.title("TrazaBD_EXP — trazabilidad BD_PAR / BD_EXP / BD_MAP")

S = st.secrets["sql"]
conn = db.get_connection(S["server"], S.get("database", "master"),
                         S.get("username", ""), S.get("password", ""),
                         S.get("trusted", True))

tab1, tab2, tab3, tab4, tab5 = st.tabs(
    ["Control", "Mapa", "Arbol SPs", "Patrones", "Baseline"])

with tab1:
    path = st.text_input("Ruta traza (servidor)", TRACE_PATH_DEFAULT)
    login = st.text_input("Login app", APP_LOGIN)
    umbral = st.number_input("Umbral ms (0 = todo)", 0, 60000, 0) * 1000
    c1, c2, c3 = st.columns(3)
    if c1.button("Arrancar"):
        tid = run_start_batch(conn, build_start_batch(
            APP_DBS, login, path, min_duration_us=int(umbral)))
        st.session_state["tid"] = tid
        st.success(f"Traza {tid} corriendo (sobrevive a cerrar el navegador)")
    if c2.button("Parar"):
        stop_trace(conn, st.session_state.get("tid", 0))
        st.warning("Traza detenida, archivos conservados")
    if c3.button("Borrar definicion"):
        delete_trace(conn, st.session_state.get("tid", 0))
    st.subheader("Trazas en el servidor")
    st.dataframe(pd.DataFrame(list_traces(conn), columns=["id", "path"]))
    if st.button("Cargar .trc a TrazaDB"):
        tabla = load_trace(conn, path, pd.Timestamp.now().strftime("%Y%m%d_%H%M"))
        st.session_state["tabla"] = tabla
        st.success(f"Cargado en TrazaDB.dbo.{tabla}")


def _df():
    t = st.session_state.get("tabla")
    if not t:
        st.info("Primero cargue una ventana en la pestana Control")
        st.stop()
    return pd.read_sql(f"SELECT * FROM TrazaDB.dbo.{t}", conn)


def _dl(df, name):
    st.download_button(f"CSV {name}", df.to_csv(index=False), f"{name}.csv")
    buf = io.BytesIO()
    df.to_excel(buf, index=False)
    st.download_button(f"Excel {name}", buf.getvalue(), f"{name}.xlsx")


with tab2:
    df = _df()
    st.subheader("Top por tiempo total")
    tq = top_queries(df)
    st.dataframe(tq)
    _dl(tq, "top_queries")
    st.subheader("Top procedures")
    tp = top_procs(df)
    st.dataframe(tp)
    _dl(tp, "top_procs")

with tab3:
    df = _df()
    for root in build_tree(df)[:50]:
        with st.expander(f"{root['object']} — {root['ms']} ms"):
            st.json(root["children"])

with tab4:
    df = _df()
    p = find_patterns(df)
    st.dataframe(p)
    if len(p):
        _dl(p, "patrones")

with tab5:
    df = _df()
    c = compare_baseline(df, BASELINE)
    st.dataframe(c)
    faltan = c[(c["Boton"] != "(ninguno)") & (~c["EnTraza"])]
    st.subheader(f"Esperados no vistos en ventana: {len(faltan)}")
    st.dataframe(faltan)
```

- [ ] **Step 2: Compile check**

Run: `python -m py_compile app.py src/*.py`
Expected: no output (success)

- [ ] **Step 3: Full test suite still green**

Run: `pytest tests/ -v`
Expected: PASS (14 passed)

- [ ] **Step 4: Commit**

```bash
git add app.py
git commit -m "feat: streamlit UI 5 tabs + csv/excel export"
```

### Task 7: Deploy runbook + prod checklist

**Files:**
- Create: `TrazaBD_EXP/DEPLOY.md`

**Interfaces:**
- Consumes: everything above.
- Produces: repeatable path to production on the internal server.

- [ ] **Step 1: Write DEPLOY.md**

```markdown
# Puesta en producción (servidor interno, red DGA)
1. Python 3.11 + `pip install -r requirements.txt`; verificar
   `python -c "import pyodbc; print([d for d in pyodbc.drivers()])"`
   incluye `ODBC Driver 18 for SQL Server`.
2. Crear login `traza_app` con `GRANT ALTER TRACE TO traza_app;`
   + lectura sobre BD_PAR/BD_EXP/BD_MAP + db_owner de TrazaDB (crear TrazaDB).
3. `.streamlit/secrets.toml` con server/datos (nunca en git).
4. `streamlit run app.py --server.address <IP interna> --server.port 8501`
   como tarea programada al inicio (o servicio NSSM).
5. Ventana 1: fuera de pico, 15 min, umbral 0 → verificar .trc + carga + mapas.
6. Ventana 2: peak 30–60 min. Si el rollover rota muy rápido, subir umbral a 500 ms.
7. Exportar Excel y archivar por fecha (ExecutionID/tabla TraceLog_*).
```

- [ ] **Step 2: Verify driver present (where Streamlit will run)**

Run: `python -c "import pyodbc; print(pyodbc.drivers())"`
Expected: list containing ODBC Driver 18 (or 17) for SQL Server

- [ ] **Step 3: Commit**

```bash
git add DEPLOY.md
git commit -m "docs: deploy runbook + prod checklist"
```

## Self-Review

**1. Spec coverage:** Sec 3 arquitectura → Tasks 1–6 file map ✔; Sec 4 traza (eventos/columnas/filtros 3 BDs OR) → Task 3 ✔; Sec 5 flujo + ExecutionID → Tasks 3–4 ✔ (ExecutionID column + TraceRuns registry + per-run tables); árbol (NestLevel+RequestID) → Task 5 build_tree ✔; Sec 6 análisis 1–5 → Task 5 ✔; Sec 7 seguridad (ALTER TRACE, secrets, IP interna, cero escrituras prod) → Tasks 2, 7, DEPLOY ✔; Sec 8 errores (retomar traza, carpeta, rollover, bloques, µs) → Tasks 3 (list_traces), 6 (retomar vía lista), DEPLOY ✔; Sec 9 pruebas (local, pytest, cruce Profiler, ventana corta) → Tasks 1–5 tests + Task 7 pasos 5–6 ✔; Sec 10 YAGNI respetado (sin auth, sin realtime) ✔; Sec 11 éxito (mapas + Excel) → Tasks 5–6 ✔; Sec 12 BD_PAR ✔ en config y filtros.

**2. Placeholder scan:** no TBD/TODO; every code step shows full code; commands exact with expected output; no "similar to Task N".

**3. Type consistency:** `build_start_batch(dbs, login, path, max_mb, filecount, min_duration_us) -> str` used identically in Task 3 test + Task 6 call ✔; `load_trace(conn, trace_path, label) -> str` same in Task 4 test + Task 6 ✔; analysis signatures (`top_queries(df, n=20)`, `build_tree(df)`, `find_patterns(df)`, `compare_baseline(df, baseline)`) identical in Task 5 tests + Task 6 UI ✔; `BASELINE: dict[str, list[str]]` ✔.
