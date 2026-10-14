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
