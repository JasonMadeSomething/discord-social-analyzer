# Ollama Model Initialization Script
# Pulls required models for the enrichment engine

param(
    [switch]$SkipWait
)

function Show-Success { param([string]$msg) Write-Host "[OK] $msg" -ForegroundColor Green }
function Show-Error { param([string]$msg) Write-Host "[ERROR] $msg" -ForegroundColor Red }
function Show-Info { param([string]$msg) Write-Host "[INFO] $msg" -ForegroundColor Cyan }

Write-Host ""
Write-Host "=======================================================" -ForegroundColor Magenta
Write-Host "  Ollama Model Initialization" -ForegroundColor Magenta
Write-Host "=======================================================" -ForegroundColor Magenta
Write-Host ""

# Wait for Ollama to be ready
if (-not $SkipWait) {
    Show-Info "Waiting for Ollama to start..."
    $maxAttempts = 30
    $attempt = 0
    $ready = $false

    while (-not $ready -and $attempt -lt $maxAttempts) {
        $attempt++
        try {
            $response = Invoke-WebRequest -Uri "http://localhost:11434/api/tags" -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop
            if ($response.StatusCode -eq 200) {
                $ready = $true
                Show-Success "Ollama is ready"
            }
        } catch {
            Write-Host "." -NoNewline
            Start-Sleep -Seconds 2
        }
    }

    if (-not $ready) {
        Show-Error "Ollama failed to start after $maxAttempts attempts"
        Show-Info "Check if the container is running: docker ps | grep ollama"
        exit 1
    }
    Write-Host ""
}

# Pull required models
Write-Host ""
Show-Info "Pulling required models..."
Write-Host ""

# phi3:mini for intent and keyword extraction
Show-Info "Pulling phi3:mini (~2.3GB) for intent/keyword extraction..."
try {
    docker exec discord-analyzer-ollama ollama pull phi3:mini
    if ($LASTEXITCODE -eq 0) {
        Show-Success "phi3:mini pulled successfully"
    } else {
        Show-Error "Failed to pull phi3:mini"
    }
} catch {
    Show-Error "Error pulling phi3:mini: $_"
}

Write-Host ""

# nomic-embed-text for embeddings
Show-Info "Pulling nomic-embed-text (~275MB) for embeddings..."
try {
    docker exec discord-analyzer-ollama ollama pull nomic-embed-text
    if ($LASTEXITCODE -eq 0) {
        Show-Success "nomic-embed-text pulled successfully"
    } else {
        Show-Error "Failed to pull nomic-embed-text"
    }
} catch {
    Show-Error "Error pulling nomic-embed-text: $_"
}

# Verify models
Write-Host ""
Show-Info "Verifying installed models..."
Write-Host ""

try {
    docker exec discord-analyzer-ollama ollama list
    Write-Host ""
    Show-Success "Model initialization complete"
} catch {
    Show-Error "Failed to list models: $_"
}

Write-Host ""
Write-Host "=======================================================" -ForegroundColor Cyan
Write-Host "  Models Ready" -ForegroundColor Cyan
Write-Host "=======================================================" -ForegroundColor Cyan
Write-Host "  phi3:mini         - Intent & keyword extraction" -ForegroundColor White
Write-Host "  nomic-embed-text  - Idea & exchange embeddings" -ForegroundColor White
Write-Host "=======================================================" -ForegroundColor Cyan
Write-Host ""
