Write-Host ""
Write-Host "=======================================================" -ForegroundColor Magenta
Write-Host "  Discord Social Analyzer - Shutdown" -ForegroundColor Magenta
Write-Host "=======================================================" -ForegroundColor Magenta
Write-Host ""

Write-Host "[INFO] Stopping all Docker services..." -ForegroundColor Cyan
Write-Host ""

docker compose --profile admin --profile cache down

if ($LASTEXITCODE -eq 0) {
    Write-Host "[OK] All services stopped successfully" -ForegroundColor Green
} else {
    Write-Host "[WARN] Some services may not have stopped cleanly" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "[INFO] To remove volumes as well, run:" -ForegroundColor Cyan
Write-Host "  docker compose --profile admin --profile cache down -v" -ForegroundColor DarkGray
Write-Host ""
