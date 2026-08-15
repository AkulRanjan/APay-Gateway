param(
    [int]$Port = 8000
)

$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot

Write-Host "Starting Custos live demo at http://127.0.0.1:$Port/demo"
python -m uvicorn gateway.server:app --host 127.0.0.1 --port $Port
