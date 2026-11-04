# PowerShell test runner for Agent E (GenAI verified bilingual parent reports)
$ErrorActionPreference = "Stop"
$env:PYTHONUTF8 = "1"

Write-Host "Running Agent E (backend/app/genai/tests) test suite..." -ForegroundColor Cyan
python -X utf8 -m pytest backend/app/genai/tests -v -rs
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
