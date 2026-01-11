#Requires -Version 5.1
<#
.SYNOPSIS
    Stop Discord Social Analyzer Docker services
.DESCRIPTION
    Stops all Docker Compose services including optional profiles
.EXAMPLE
    .\stop.ps1
    Stop all services
#>

# Color functions
function Write-ColorOutput {
    param([string]$Message, [string]$Color = 'White')
    Write-Host $Message -ForegroundColor $Color
}

function Write-Success { param([string]$Message) Write-ColorOutput "✓ $Message" 'Green' }
function Write-Info { param([string]$Message) Write-ColorOutput "ℹ $Message" 'Cyan' }

Write-Host ""
Write-ColorOutput "═══════════════════════════════════════════════════════" 'Magenta'
Write-ColorOutput "    Discord Social Analyzer - Shutdown" 'Magenta'
Write-ColorOutput "═══════════════════════════════════════════════════════" 'Magenta'
Write-Host ""

Write-Info "Stopping all Docker services..."
Write-ColorOutput "Running: docker compose --profile admin --profile cache down" 'DarkGray'
Write-Host ""

docker compose --profile admin --profile cache down

if ($LASTEXITCODE -eq 0) {
    Write-Success "All services stopped successfully"
} else {
    Write-ColorOutput "⚠ Some services may not have stopped cleanly" 'Yellow'
}

Write-Host ""
Write-Info "To remove volumes as well, run:"
Write-ColorOutput "  docker compose --profile admin --profile cache down -v" 'DarkGray'
Write-Host ""
