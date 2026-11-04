# Windows-friendly contract test runner for DataMoat Phase 0
$ErrorActionPreference = "Stop"

Write-Host "Running DataMoat Phase 0 Contract Test Suite..." -ForegroundColor Cyan
python -m pytest contracts/tests -v -rs
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
Write-Host "All executed contract tests passed!" -ForegroundColor Green
