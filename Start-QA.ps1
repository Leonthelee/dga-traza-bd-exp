$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$projectPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $projectPython)) {
    throw 'Primero ejecute Setup-QA.ps1 para instalar el entorno.'
}
& $projectPython -m streamlit run app.py
