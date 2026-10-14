# App de Trazabilidad BD_EXP — Spec de diseño

Fecha: 2026-10-09 | Estado: aprobado por el usuario | Plataforma: Python + Streamlit
Ubicación del proyecto: `C:\Users\daniel.diaz\Music\TrazaBD_EXP`

## 1. Objetivo

App interna (red DGA) que genera trazas server-side de todo lo que ejecuta el
sistema legacy de Oposiciones (600 usuarios, login compartido `XXXX`), reconstruye
el árbol de SPs anidados y produce los mapas para migrar a buenas prácticas.
Reemplaza el uso manual de SQL Server Profiler (obsoleto según Microsoft).

## 2. Contexto (verificado)

- Front legacy: Oposiciones QA (`172.16.71.16:9080/oposiciones`), pantallas
  Ingreso / Traslado-Respuesta / Resolución / Documentos.
- **3 bases involucradas**: `BD_PAR` (`dbo.CPA_*`), `BD_EXP` (`dbo.Exps_*`),
  `BD_MAP` (`dbo.MAP_*` vía `sp_executesql`). El filtro de traza cubre las 3.
- Solo se puede modificar SQL Server (sysadmin en prod, 2014–2019). La app
  legacy NO se toca.
- Objetivo del análisis: optimizar consultas, NO auditoría por usuario.
- Hallazgo PDF QA: `@UsrLogin` y `@TabIdSesion` viajan como parámetros en los
  `Exps_*` → el usuario lógico se extrae del TextData con regex (los `CPA_*`
  siguen ciegos).
- Hallazgo PDF QA: "Agregar Opositor" = 10 SPs secuenciales a BD_EXP (chatty);
  cada Guardar invoca `sp_stored_procedures` + `sp_sproc_columns` (reflection
  en caliente); batches con `select @p` de outputs (doble round-trip).

## 3. Arquitectura

```
TrazaBD_EXP/
├── app.py                  # UI Streamlit (Control, Mapa, Árbol, Patrones)
├── requirements.txt        # streamlit, pyodbc, pandas, openpyxl
├── .streamlit/secrets.toml # credenciales (fuera de git)
├── src/
│   ├── db.py               # conexión, login dedicado con ALTER TRACE
│   ├── trace.py            # sp_trace_create/setevent/setfilter/setstatus
│   ├── loader.py           # fn_trace_gettable → TrazaDB.dbo.TraceLog (+ExecutionID)
│   └── analysis.py         # top queries, árbol SPs, extractor @UsrLogin, patrones
├── tests/test_analysis.py  # pytest con .trc de ejemplo
├── docs/                   # PDF QA (línea base) + este spec
└── README.md
```

BD de análisis `TrazaDB` separada: la app solo LEE las 3 BDs productivas,
escribe únicamente en `TrazaDB`.

## 4. Definición de la traza server-side

- Eventos: 10 RPC:Completed, 12 SQL:BatchCompleted, 45 SP:StmtCompleted.
- Columnas: 1 TextData, 10 ApplicationName, 11 LoginName, 12 SPID, 13 Duration
  (µs), 14 StartTime, 15 EndTime, 16 Reads, 17 Writes, 18 CPU, 27 EventClass,
  29 NestLevel, 31 Error, 34 ObjectName, 35 DatabaseName, 49 RequestID.
- Filtros: DatabaseName = `BD_PAR` OR `BD_EXP` OR `BD_MAP` (OR lógico en
  sp_trace_setfilter); LoginName = `XXXX`; ApplicationName NOT LIKE
  `%Profiler/%Management Studio%`; Duration >= umbral opcional (µs, solo si el
  volumen lo exige).
- Archivo en el SERVIDOR con rollover (500 MB x5). Sobrevive a cerrar el
  navegador; se para solo con `sp_trace_setstatus 0`.

## 5. Flujo de datos

Configurar → Arrancar (traza viva) → Parar → Cargar (.trc → TraceLog con
ExecutionID) → Analizar/Exportar (CSV/Excel).

Árbol de SPs: agrupar por (SPID, RequestID), ordenar por StartTime, profundidad
por NestLevel → `RPC usp_X → SP:Stmt ... → SP usp_Y → ...`.

## 6. Análisis (analysis.py)

1. Top 20 por tiempo total (LEFT(TextData,300) + EventClass).
2. Top SPs por ObjectName (tiempo total, reads prom.).
3. Caza de patrones: `SELECT *`, `NOLOCK`, `CONVERT(`, `CURSOR`,
   `sp_sproc_columns`/`sp_stored_procedures`, batches solo-`select @p`.
4. Extractor `@UsrLogin=` / `@TabIdSesion=` desde TextData (solo Exps_*).
5. Comparador contra línea base del PDF: llamadas esperadas por botón vs
   llamadas reales (detector de drift).

## 7. Seguridad

Login dedicado con `ALTER TRACE` (nunca sa/sysadmin en secrets); Streamlit solo
en IP interna (p. ej. `172.16.x.x:8501`); secrets fuera de git; cero escrituras
en BDs productivas.

## 8. Errores manejados

Traza ya corriendo (retomar, no duplicar); carpeta sin permiso de la cuenta de
servicio; rollover a mitad de carga (reintento + DEFAULT); ventanas gigantes
(carga por bloques + progreso); Duration siempre en microsegundos.

## 9. Pruebas y puesta en producción

1. SQL Developer local + carga que imite las 3 pantallas.
2. pytest de analysis.py con .trc de ejemplo (árbol verificado a mano).
3. Cruce Profiler GUI vs app (conteos iguales).
4. Ventana corta en prod fuera de pico → luego horario peak.
5. Despliegue: servidor interno siempre encendido, `streamlit run app.py
   --server.address <IP interna>` como servicio/tarea programada.

## 10. Fuera de alcance (YAGNI)

Autenticación de usuarios de la app; alertas en tiempo real; reescritura de los
SPs legacy (fase 2 con los mapas); soporte Azure SQL.

## 11. Criterio de éxito

Con una ventana de 30–60 min en peak, la app entrega: top queries, árbol de SPs
por pantalla, lista de malas prácticas con evidencia y Excel exportable — sin
instalar nada en prod salvo la traza temporal.

## 12. Pendiente del usuario — RESUELTO 2026-10-14

- ~~Nombre exacto de la BD de la app~~ → es **`BD_PAR`**
  (verificado con `OBJECT_ID` + `HAS_DBACCESS` en 172.19.30.111).
- SPEC cerrado. Siguiente paso: plan de implementación.
