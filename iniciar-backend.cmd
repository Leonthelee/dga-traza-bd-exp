@echo off
title DGA Modulo de Oposiciones - Backend API REST
echo ============================================================
echo   DGA - Backend API REST (FastAPI / Uvicorn) : Puerto 8000
echo   Direccion General de Aguas - Ministerio de Obras Publicas
echo ============================================================
cd /d "%~dp0"
if exist ".\.venv\Scripts\python.exe" (
    ".\.venv\Scripts\python.exe" -m uvicorn backend.server:app --host 127.0.0.1 --port 8000 --reload
) else (
    python -m uvicorn backend.server:app --host 127.0.0.1 --port 8000 --reload
)
pause
