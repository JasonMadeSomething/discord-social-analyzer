[CmdletBinding()]
param(
    [Parameter()]
    [ValidateSet('whisper', 'vosk')]
    [string]$Provider = 'whisper',
    
    [Parameter()]
    [switch]$WithAdmin,
    
    [Parameter()]
    [switch]$WithCache,
    
    [Parameter()]
    [switch]$SkipMigrations
)

$script:cleanupRequired = $false

function Show-Success { param([string]$msg) Write-Host "[OK] $msg" -ForegroundColor Green }
function Show-Error { param([string]$msg) Write-Host "[ERROR] $msg" -ForegroundColor Red }
function Show-Info { param([string]$msg) Write-Host "[INFO] $msg" -ForegroundColor Cyan }
function Show-Warning { param([string]$msg) Write-Host "[WARN] $msg" -ForegroundColor Yellow }

function Cleanup {
    if ($script:cleanupRequired) {
        Show-Info "Stopping Docker services..."
        docker compose down 2>$null | Out-Null
        Show-Success "Services stopped"
    }
}

Write-Host ""
Write-Host "=======================================================" -ForegroundColor Magenta
Write-Host "  Discord Social Analyzer - Startup" -ForegroundColor Magenta
Write-Host "=======================================================" -ForegroundColor Magenta
Write-Host ""

# Check Docker
Show-Info "Checking Docker..."
try {
    $null = docker --version 2>&1
    if ($LASTEXITCODE -ne 0) { throw }
    Show-Success "Docker is installed"
} catch {
    Show-Error "Docker not found. Install from: https://www.docker.com/products/docker-desktop"
    exit 1
}

try {
    $null = docker ps 2>&1
    if ($LASTEXITCODE -ne 0) { throw }
    Show-Success "Docker is running"
} catch {
    Show-Error "Docker is not running. Please start Docker Desktop"
    exit 1
}

# Check .env
Show-Info "Checking configuration..."
if (-not (Test-Path ".env")) {
    Show-Warning ".env not found"
    if (Test-Path ".env.example") {
        Copy-Item ".env.example" ".env"
        Show-Success "Created .env from example"
        Show-Warning "Please edit .env with your Discord token"
        notepad .env
        Read-Host "Press Enter after editing .env"
    } else {
        Show-Error ".env.example not found"
        exit 1
    }
} else {
    Show-Success ".env file found"
}

# Set provider
if ($Provider -eq 'vosk') {
    $env:USE_VOSK = 'true'
    Show-Info "Using Vosk provider (fast, CPU-friendly)"
} else {
    $env:USE_VOSK = 'false'
    Show-Info "Using Whisper provider (accurate, GPU recommended)"
}

# Build compose command
$profiles = @()
if ($WithAdmin) { 
    $profiles += 'admin'
    Show-Info "pgAdmin will be started"
}
if ($WithCache) { 
    $profiles += 'cache'
    Show-Info "Redis will be started"
}

# Start services
Write-Host ""
Show-Info "Starting Docker services..."

try {
    if ($profiles.Count -gt 0) {
        $profileArgs = $profiles | ForEach-Object { "--profile"; $_ }
        $output = & docker compose $profileArgs up -d 2>&1
    } else {
        $output = & docker compose up -d 2>&1
    }
    
    if ($LASTEXITCODE -ne 0) { 
        Write-Host $output -ForegroundColor Red
        throw "Docker Compose failed with exit code $LASTEXITCODE"
    }
    $script:cleanupRequired = $true
    Show-Success "Docker services started"
} catch {
    Show-Error "Failed to start services: $_"
    Write-Host ""
    Write-Host "Try running manually to see the error:" -ForegroundColor Yellow
    Write-Host "  docker compose --profile admin up -d" -ForegroundColor DarkGray
    exit 1
}

# Wait for health
Write-Host ""
Show-Info "Waiting for services to be ready..."
Start-Sleep -Seconds 15
Show-Success "Services should be ready"

# Migrations
if (-not $SkipMigrations) {
    Write-Host ""
    Show-Info "Running database migrations..."
    try {
        python -c "from src.config import settings; from src.models.database import Base, engine; Base.metadata.create_all(engine)" 2>&1 | Out-Null
        if ($LASTEXITCODE -eq 0) {
            Show-Success "Database ready"
        } else {
            Show-Warning "Migration had issues, continuing..."
        }
    } catch {
        Show-Warning "Could not run migrations, bot will create tables"
    }
}

# Show URLs
Write-Host ""
Write-Host "=======================================================" -ForegroundColor Cyan
Write-Host "  Service URLs" -ForegroundColor Cyan
Write-Host "=======================================================" -ForegroundColor Cyan
Write-Host "  PostgreSQL:  localhost:5432"
Write-Host "  Qdrant:      http://localhost:6333"
Write-Host "  Qdrant UI:   http://localhost:6333/dashboard"
if ($WithAdmin) { Write-Host "  pgAdmin:     http://localhost:5050" }
if ($WithCache) { Write-Host "  Redis:       localhost:6379" }
Write-Host "=======================================================" -ForegroundColor Cyan

# Start bot
Write-Host ""
Show-Info "Starting Discord bot (Provider: $Provider)..."
Write-Host ""

try {
    python main.py --provider $Provider
} catch {
    Show-Error "Bot crashed: $_"
} finally {
    Write-Host ""
    Cleanup
}

Write-Host ""
Show-Success "Shutdown complete"
