@echo off
title DGA Modulo de Oposiciones - Frontend Kit Digital Gob.cl
echo ============================================================
echo   DGA - Frontend Kit Digital Gob.cl 2026 : Puerto 8080
echo   Direccion General de Aguas - Ministerio de Obras Publicas
echo ============================================================
cd /d "%~dp0\frontend"
start http://127.0.0.1:8080/
if exist "..\.venv\Scripts\python.exe" (
    "..\.venv\Scripts\python.exe" -m http.server 8080 --bind 127.0.0.1
) else (
    python -m http.server 8080 --bind 127.0.0.1
)
pause
