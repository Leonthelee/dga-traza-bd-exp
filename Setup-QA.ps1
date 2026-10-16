$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$projectPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $projectPython)) {
    try {
        py -3.11 -m venv .venv 2>$null
    } catch {}
    if (-not (Test-Path -LiteralPath $projectPython)) {
        try {
            py -V:Astral/CPython3.11.15 -m venv .venv 2>$null
        } catch {}
    }
    if (-not (Test-Path -LiteralPath $projectPython)) {
        python -m venv .venv
    }
    if (-not (Test-Path -LiteralPath $projectPython)) { throw 'Instale Python 3.11+ y vuelva a ejecutar.' }
}
& $projectPython -m pip install -r requirements-dev.txt
if ($LASTEXITCODE -ne 0) { throw 'No se pudieron instalar las dependencias.' }
Write-Host 'Entorno listo. Ejecute Start-QA.ps1 para abrir la aplicacion.'
