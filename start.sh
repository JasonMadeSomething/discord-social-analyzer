#!/bin/bash
# Discord Social Analyzer - Linux/Mac Startup Script
# Starts Docker services, waits for health checks, and launches the bot

set -e  # Exit on error

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
NC='\033[0m' # No Color

# Output functions
print_success() { echo -e "${GREEN}✓ $1${NC}"; }
print_error() { echo -e "${RED}✗ $1${NC}"; }
print_info() { echo -e "${CYAN}ℹ $1${NC}"; }
print_warning() { echo -e "${YELLOW}⚠ $1${NC}"; }

# Default values
PROVIDER="whisper"
WITH_ADMIN=false
WITH_CACHE=false
SKIP_MIGRATIONS=false
DEV_MODE=false
CLEANUP_REQUIRED=false

# Parse command-line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --provider)
            PROVIDER="$2"
            if [[ "$PROVIDER" != "whisper" && "$PROVIDER" != "vosk" ]]; then
                print_error "Invalid provider. Must be 'whisper' or 'vosk'"
                exit 1
            fi
            shift 2
            ;;
        --with-admin)
            WITH_ADMIN=true
            shift
            ;;
        --with-cache)
            WITH_CACHE=true
            shift
            ;;
        --skip-migrations)
            SKIP_MIGRATIONS=true
            shift
            ;;
        --dev)
            DEV_MODE=true
            shift
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --provider <whisper|vosk>  Transcription provider (default: whisper)"
            echo "  --with-admin               Start pgAdmin web interface"
            echo "  --with-cache               Start Redis cache service"
            echo "  --skip-migrations          Skip database migration step"
            echo "  --dev                      Development mode with verbose output"
            echo "  --help                     Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0                         Start with default settings"
            echo "  $0 --provider vosk         Start with Vosk provider"
            echo "  $0 --with-admin            Start with pgAdmin"
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Cleanup function
cleanup() {
    if [ "$CLEANUP_REQUIRED" = true ]; then
        echo ""
        print_info "Cleaning up Docker services..."
        
        PROFILES=""
        if [ "$WITH_ADMIN" = true ]; then
            PROFILES="$PROFILES --profile admin"
        fi
        if [ "$WITH_CACHE" = true ]; then
            PROFILES="$PROFILES --profile cache"
        fi
        
        docker compose $PROFILES down 2>/dev/null || true
        print_success "Services stopped"
    fi
}

# Register cleanup on exit
trap cleanup EXIT INT TERM

# Banner
echo ""
echo -e "${MAGENTA}═══════════════════════════════════════════════════════${NC}"
echo -e "${MAGENTA}    Discord Social Analyzer - Startup Script${NC}"
echo -e "${MAGENTA}═══════════════════════════════════════════════════════${NC}"
echo ""

# Check Docker installation
print_info "Checking Docker installation..."
if ! command -v docker &> /dev/null; then
    print_error "Docker is not installed"
    print_info "Please install Docker from: https://docs.docker.com/get-docker/"
    exit 1
fi
DOCKER_VERSION=$(docker --version)
print_success "Docker installed: $DOCKER_VERSION"

# Check if Docker is running
print_info "Checking if Docker is running..."
if ! docker ps &> /dev/null; then
    print_error "Docker is not running"
    print_info "Please start Docker and try again"
    exit 1
fi
print_success "Docker is running"

# Check for .env file
print_info "Checking for .env file..."
if [ ! -f ".env" ]; then
    print_warning ".env file not found"
    if [ -f ".env.example" ]; then
        print_info "Copying .env.example to .env..."
        cp .env.example .env
        print_success "Created .env file"
        print_warning "Please edit .env file with your Discord token and settings"
        
        # Try to open in default editor
        if command -v nano &> /dev/null; then
            print_info "Opening .env in nano..."
            nano .env
        elif command -v vim &> /dev/null; then
            print_info "Opening .env in vim..."
            vim .env
        else
            print_info "Please edit .env manually before continuing"
            read -p "Press Enter when you've configured .env..."
        fi
    else
        print_error ".env.example not found"
        exit 1
    fi
else
    print_success ".env file found"
fi

# Set provider environment variable
print_info "Setting transcription provider: $PROVIDER"
if [ "$PROVIDER" = "vosk" ]; then
    export USE_VOSK=true
    print_success "Using Vosk provider (fast, CPU-friendly)"
else
    export USE_VOSK=false
    print_success "Using Whisper provider (high accuracy, GPU recommended)"
fi

# Build Docker Compose command
COMPOSE_ARGS="up -d"
if [ "$WITH_ADMIN" = true ]; then
    COMPOSE_ARGS="$COMPOSE_ARGS --profile admin"
    print_info "pgAdmin will be started"
fi
if [ "$WITH_CACHE" = true ]; then
    COMPOSE_ARGS="$COMPOSE_ARGS --profile cache"
    print_info "Redis cache will be started"
fi

# Start Docker services
echo ""
print_info "Starting Docker services..."
if [ "$DEV_MODE" = true ]; then
    echo -e "${BLUE}Running: docker compose $COMPOSE_ARGS${NC}"
fi

if docker compose $COMPOSE_ARGS; then
    CLEANUP_REQUIRED=true
    print_success "Docker services started"
else
    print_error "Failed to start Docker services"
    exit 1
fi

# Wait for services to be healthy
echo ""
print_info "Waiting for services to become healthy..."

wait_for_service() {
    local SERVICE_NAME=$1
    local CONTAINER_NAME=$2
    local MAX_RETRIES=${3:-30}
    local RETRY_INTERVAL=${4:-2}
    
    print_info "Checking $SERVICE_NAME..."
    local retries=0
    
    while [ $retries -lt $MAX_RETRIES ]; do
        HEALTH=$(docker inspect --format='{{.State.Health.Status}}' "$CONTAINER_NAME" 2>/dev/null || echo "unknown")
        
        if [ "$HEALTH" = "healthy" ]; then
            print_success "$SERVICE_NAME is healthy"
            return 0
        fi
        
        retries=$((retries + 1))
        if [ "$DEV_MODE" = true ]; then
            echo -e "${BLUE}  Attempt $retries/$MAX_RETRIES - Status: $HEALTH${NC}"
        else
            echo -n "."
        fi
        sleep $RETRY_INTERVAL
    done
    
    echo ""
    print_error "$SERVICE_NAME failed to become healthy after $((MAX_RETRIES * RETRY_INTERVAL)) seconds"
    return 1
}

# Check PostgreSQL
if ! wait_for_service "PostgreSQL" "discord-analyzer-postgres"; then
    print_error "PostgreSQL failed to start. Check logs with: docker logs discord-analyzer-postgres"
    exit 1
fi

# Check Qdrant
if ! wait_for_service "Qdrant" "discord-analyzer-qdrant"; then
    print_error "Qdrant failed to start. Check logs with: docker logs discord-analyzer-qdrant"
    exit 1
fi

# Check pgAdmin if enabled
if [ "$WITH_ADMIN" = true ]; then
    if ! wait_for_service "pgAdmin" "discord-analyzer-pgadmin" 20; then
        print_warning "pgAdmin failed to start, but continuing anyway"
    fi
fi

# Check Redis if enabled
if [ "$WITH_CACHE" = true ]; then
    if ! wait_for_service "Redis" "discord-analyzer-redis"; then
        print_warning "Redis failed to start, but continuing anyway"
    fi
fi

echo ""
print_success "All required services are healthy!"

# Run database migrations
if [ "$SKIP_MIGRATIONS" = false ]; then
    echo ""
    print_info "Running database migrations..."
    
    if command -v python3 &> /dev/null; then
        PYTHON_CMD=python3
    elif command -v python &> /dev/null; then
        PYTHON_CMD=python
    else
        print_error "Python not found in PATH"
        exit 1
    fi
    
    if $PYTHON_CMD -c "from src.config import settings; from src.models.database import Base, engine; Base.metadata.create_all(engine); print('Database tables created')" 2>&1; then
        print_success "Database migrations completed"
    else
        print_warning "Database migration had issues, but continuing..."
    fi
else
    print_info "Skipping database migrations (--skip-migrations flag set)"
fi

# Display service URLs
echo ""
echo -e "${CYAN}═══════════════════════════════════════════════════════${NC}"
echo -e "${CYAN}    Service URLs${NC}"
echo -e "${CYAN}═══════════════════════════════════════════════════════${NC}"
echo "  PostgreSQL:  localhost:5432"
echo "  Qdrant:      http://localhost:6333"
echo "  Qdrant UI:   http://localhost:6333/dashboard"
if [ "$WITH_ADMIN" = true ]; then
    echo "  pgAdmin:     http://localhost:5050"
fi
if [ "$WITH_CACHE" = true ]; then
    echo "  Redis:       localhost:6379"
fi
echo -e "${CYAN}═══════════════════════════════════════════════════════${NC}"

# Start the bot
echo ""
print_info "Starting Discord bot..."
if [ "$DEV_MODE" = true ]; then
    echo -e "${BLUE}Provider: $PROVIDER${NC}"
fi
echo ""

# Determine Python command
if command -v python3 &> /dev/null; then
    PYTHON_CMD=python3
else
    PYTHON_CMD=python
fi

# Start the bot with provider argument
$PYTHON_CMD main.py --provider "$PROVIDER"

echo ""
print_success "Shutdown complete"
