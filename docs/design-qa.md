# Diseño implementado para QA — 2026-10-09

Este documento complementa el diseño original de Muse Spark; no altera su texto ni transforma afirmaciones anteriores en verificaciones.

## Cambios decididos

1. Extended Events reemplaza `sp_trace_*` para nuevo desarrollo.
2. Almacenamiento SQLite en el PC/servidor de la herramienta, separado de las bases de negocio. No se requiere TrazaDB ni escritura de tablas en QA.
3. Captura por login y opcional SPID; sin filtro de base para no cortar llamadas entre bases. Los nombres configurados se verifican antes de iniciar.
4. Perfil detalle y perfil rendimiento separados. Detalle no filtra duración.
5. Worker Python separado y persistencia de estado. Plazo máximo 15 minutos, parada best effort, recuperación manual visible. No hay garantía de parada si muere el host.
6. Importación por bloques con deduplicación; relectura de XEL retenidos. No se pretende reanudación exacta por file_offset.
7. Métricas separadas por nivel; árbol conservador con relaciones inferidas. No hay atribución automática a pantalla ni reconstrucción causal entre sesiones.
8. Parámetros UsrLogin/TabIdSesion son evidencia de texto, no identidad autenticada.
9. PDF: diez SPs documentados al Agregar Opositor; consultas de metadatos observadas en algunas acciones. Los bloques EXEC + SELECT no prueban doble round-trip.
10. Interfaz local con modo sintético, sin conexión inicial ni credenciales copiadas de otros proyectos.

## Reutilización de conocimiento

Consulta realizada a `E:\ClaudeCosas\cerebro-local\rag_ask.py` sin generación de borrador: resultados no pertinentes a SQL, descartados. El índice del Cerebro en Obsidian permitió encontrar `expedientes-app/db.py` y `dga-bpm-orchestrator/backend/main.py`; se tomó el patrón Python/pyodbc/ODBC 18, no sus credenciales, ni las consultas interpoladas.

## Pendientes verificables

Instancia real QA, nombre BD CPA, login legacy, permisos/carpeta XEL, catálogo XE de la versión instalada, pruebas de integración y medición de overhead. Ver `qa-checklist.md`.
