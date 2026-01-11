# Discord Social Analyzer - Startup Guide

Complete guide for starting and managing the Discord Social Analyzer with Docker.

## Table of Contents
- [Overview](#overview)
- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Script Options](#script-options)
- [Services](#services)
- [First-Time Setup](#first-time-setup)
- [Choosing a Transcription Provider](#choosing-a-transcription-provider)
- [Stopping Services](#stopping-services)
- [Troubleshooting](#troubleshooting)
- [Advanced Usage](#advanced-usage)
- [Environment Variables](#environment-variables)

---

## Overview

The startup scripts automate the entire process of:
1. Starting Docker services (PostgreSQL, Qdrant, optional pgAdmin/Redis)
2. Waiting for services to become healthy
3. Running database migrations
4. Starting the Discord bot with your chosen transcription provider

All data persists in Docker volumes, so stopping and restarting is safe.

---

## Prerequisites

### Required
- **Docker Desktop** (Windows/Mac) or **Docker Engine** (Linux)
  - Windows: https://www.docker.com/products/docker-desktop
  - Mac: https://www.docker.com/products/docker-desktop
  - Linux: https://docs.docker.com/engine/install/
- **Python 3.10+** with dependencies installed (`pip install -r requirements.txt`)
- **Discord Bot Token** (see [First-Time Setup](#first-time-setup))

### Optional
- **CUDA-capable GPU** for Whisper transcription (recommended)
- **Vosk model** if using Vosk provider (see VOSK_SETUP.md)

---

## Quick Start

### Windows (PowerShell - Recommended)

```powershell
# Basic start with Whisper (default)
.\start.ps1

# Start with Vosk provider
.\start.ps1 -Provider vosk

# Start with pgAdmin web interface
.\start.ps1 -WithAdmin

# Start with all options
.\start.ps1 -Provider vosk -WithAdmin -WithCache
```

### Windows (Batch File - Simple)

```batch
# Double-click start.bat or run:
start.bat
```

### Linux/Mac

```bash
# Make executable (first time only)
chmod +x start.sh

# Basic start with Whisper (default)
./start.sh

# Start with Vosk provider
./start.sh --provider vosk

# Start with pgAdmin
./start.sh --with-admin

# Start with all options
./start.sh --provider vosk --with-admin --with-cache
```

### Manual Start (Any Platform)

```bash
# 1. Start Docker services
docker compose up -d

# 2. Wait for services (check health)
docker ps

# 3. Start the bot
python main.py --provider whisper
```

---

## Script Options

### PowerShell (start.ps1)

| Parameter | Values | Default | Description |
|-----------|--------|---------|-------------|
| `-Provider` | `whisper`, `vosk` | `whisper` | Transcription provider to use |
| `-WithAdmin` | switch | off | Start pgAdmin web interface |
| `-WithCache` | switch | off | Start Redis cache service |
| `-SkipMigrations` | switch | off | Skip database migration step |
| `-DevMode` | switch | off | Show verbose output |

**Examples:**
```powershell
.\start.ps1 -Provider whisper
.\start.ps1 -Provider vosk -WithAdmin
.\start.ps1 -WithAdmin -WithCache -DevMode
```

### Bash (start.sh)

| Argument | Values | Default | Description |
|----------|--------|---------|-------------|
| `--provider` | `whisper`, `vosk` | `whisper` | Transcription provider to use |
| `--with-admin` | flag | off | Start pgAdmin web interface |
| `--with-cache` | flag | off | Start Redis cache service |
| `--skip-migrations` | flag | off | Skip database migration step |
| `--dev` | flag | off | Show verbose output |

**Examples:**
```bash
./start.sh --provider whisper
./start.sh --provider vosk --with-admin
./start.sh --with-admin --with-cache --dev
```

---

## Services

### PostgreSQL Database
- **Purpose:** Stores sessions, utterances, messages, and participants
- **Port:** 5432
- **Connection:** `postgresql://postgres:postgres@localhost:5432/discord_analyzer`
- **Volume:** `discord-analyzer-postgres-data`

### Qdrant Vector Database
- **Purpose:** Vector storage for semantic search and embeddings (future feature)
- **HTTP Port:** 6333
- **gRPC Port:** 6334
- **Dashboard:** http://localhost:6333/dashboard
- **Volume:** `discord-analyzer-qdrant-data`

### pgAdmin (Optional)
- **Purpose:** Web-based PostgreSQL administration
- **Port:** 5050
- **URL:** http://localhost:5050
- **Default Login:** admin@discord-analyzer.local / admin
- **Volume:** `discord-analyzer-pgadmin-data`
- **Start with:** `-WithAdmin` or `--with-admin`

### Redis Cache (Optional)
- **Purpose:** Caching layer for future features
- **Port:** 6379
- **Password:** Set in .env as `REDIS_PASSWORD`
- **Volume:** `discord-analyzer-redis-data`
- **Start with:** `-WithCache` or `--with-cache`

---

## First-Time Setup

### 1. Get Discord Bot Token

1. Go to https://discord.com/developers/applications
2. Click "New Application"
3. Give it a name (e.g., "Social Analyzer")
4. Go to "Bot" section
5. Click "Add Bot"
6. Under "Token", click "Copy" to copy your bot token
7. **Important:** Enable these Privileged Gateway Intents:
   - ✅ Presence Intent
   - ✅ Server Members Intent
   - ✅ Message Content Intent

### 2. Invite Bot to Server

1. Go to "OAuth2" → "URL Generator"
2. Select scopes:
   - ✅ `bot`
   - ✅ `applications.commands`
3. Select bot permissions:
   - ✅ Read Messages/View Channels
   - ✅ Send Messages
   - ✅ Connect (Voice)
   - ✅ Speak (Voice)
   - ✅ Use Voice Activity
4. Copy the generated URL and open it in your browser
5. Select your server and authorize

### 3. Configure .env File

The startup script will create `.env` from `.env.example` if it doesn't exist.

**Required settings:**
```env
# Discord Configuration
DISCORD_TOKEN=your_bot_token_here

# Database (default values work with Docker)
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/discord_analyzer

# Whisper Settings (if using Whisper)
WHISPER_MODEL=medium
WHISPER_DEVICE=cuda  # or 'cpu'
WHISPER_COMPUTE_TYPE=float16

# Vosk Settings (if using Vosk)
VOSK_MODEL_PATH=models/vosk-model-en-us-0.22
```

### 4. First Run

```powershell
# Windows PowerShell
.\start.ps1

# Linux/Mac
./start.sh
```

The script will:
- ✅ Check Docker is installed and running
- ✅ Start all required services
- ✅ Wait for services to be healthy
- ✅ Create database tables
- ✅ Start the bot

---

## Choosing a Transcription Provider

### Whisper (OpenAI)
**Best for:** Accuracy, multiple languages, production quality

**Pros:**
- Higher transcription accuracy
- Better handling of accents and noise
- Multiple language support
- Well-tested and mature

**Cons:**
- Slower processing (especially on CPU)
- Requires GPU for good performance
- Higher resource usage

**Requirements:**
- CUDA-capable GPU recommended
- ~2GB VRAM for medium model
- ~5GB VRAM for large model

**Usage:**
```powershell
.\start.ps1 -Provider whisper
```

### Vosk
**Best for:** Real-time, CPU-only systems, development

**Pros:**
- Very fast processing
- Works well on CPU
- Lower resource usage
- Good for real-time transcription

**Cons:**
- Slightly lower accuracy
- English-only (with standard model)
- Less robust with background noise

**Requirements:**
- Download Vosk model (see VOSK_SETUP.md)
- ~1GB disk space for model

**Usage:**
```powershell
.\start.ps1 -Provider vosk
```

---

## Stopping Services

### Windows PowerShell
```powershell
# Stop all services
.\stop.ps1

# Or press Ctrl+C in the bot window
```

### Linux/Mac
```bash
# Press Ctrl+C in the bot window
# Services will auto-cleanup

# Or manually:
docker compose --profile admin --profile cache down
```

### Remove All Data (Reset)
```bash
# Stop and remove volumes
docker compose --profile admin --profile cache down -v

# This will delete:
# - All database data
# - All Qdrant vectors
# - All pgAdmin settings
# - All Redis cache
```

---

## Troubleshooting

### Docker Not Running
**Error:** `Docker is not running`

**Solution:**
- Windows/Mac: Start Docker Desktop
- Linux: `sudo systemctl start docker`

### Port Already in Use
**Error:** `port is already allocated`

**Solution:**
```bash
# Check what's using the port
netstat -ano | findstr :5432  # Windows
lsof -i :5432                 # Linux/Mac

# Change port in .env
POSTGRES_PORT=5433
```

### Services Not Healthy
**Error:** `PostgreSQL failed to become healthy`

**Solution:**
```bash
# Check logs
docker logs discord-analyzer-postgres

# Restart service
docker compose restart postgres

# Full reset
docker compose down
docker volume rm discord-analyzer-postgres-data
docker compose up -d
```

### Bot Won't Start
**Error:** `discord.errors.LoginFailure: Improper token has been passed`

**Solution:**
- Check `DISCORD_TOKEN` in `.env`
- Make sure there are no extra spaces or quotes
- Regenerate token in Discord Developer Portal if needed

### Transcription Not Working
**Whisper Issues:**
- Check GPU availability: `nvidia-smi` (Windows/Linux)
- Try CPU mode: Set `WHISPER_DEVICE=cpu` in `.env`
- Use smaller model: Set `WHISPER_MODEL=small` in `.env`

**Vosk Issues:**
- Verify model path: Check `VOSK_MODEL_PATH` in `.env`
- Download model: See VOSK_SETUP.md
- Check model files exist in the specified directory

### Database Connection Failed
**Error:** `could not connect to server`

**Solution:**
```bash
# Wait for PostgreSQL to be ready
docker logs discord-analyzer-postgres

# Check if port is accessible
telnet localhost 5432

# Verify DATABASE_URL in .env matches Docker settings
```

---

## Advanced Usage

### View Logs

```bash
# All services
docker compose logs

# Specific service
docker compose logs postgres
docker compose logs qdrant

# Follow logs (live)
docker compose logs -f

# Bot logs
tail -f bot.log
```

### Restart Services

```bash
# Restart all
docker compose restart

# Restart specific service
docker compose restart postgres
docker compose restart qdrant
```

### Access PostgreSQL Directly

```bash
# Using Docker
docker exec -it discord-analyzer-postgres psql -U postgres -d discord_analyzer

# Using local psql
psql -h localhost -U postgres -d discord_analyzer
```

### Backup Database

```bash
# Backup
docker exec discord-analyzer-postgres pg_dump -U postgres discord_analyzer > backup.sql

# Restore
docker exec -i discord-analyzer-postgres psql -U postgres discord_analyzer < backup.sql
```

### Update Docker Images

```bash
# Pull latest images
docker compose pull

# Restart with new images
docker compose up -d
```

### Development Workflow

```bash
# 1. Start services only (no bot)
docker compose up -d

# 2. Run bot manually with hot reload
python main.py --provider whisper

# 3. Make code changes (bot auto-restarts if using watchdog)

# 4. Stop services when done
docker compose down
```

---

## Environment Variables

### Core Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `DISCORD_TOKEN` | *required* | Your Discord bot token |
| `DATABASE_URL` | postgres://... | PostgreSQL connection string |
| `COMMAND_PREFIX` | `!` | Bot command prefix |

### PostgreSQL

| Variable | Default | Description |
|----------|---------|-------------|
| `POSTGRES_DB` | `discord_analyzer` | Database name |
| `POSTGRES_USER` | `postgres` | Database user |
| `POSTGRES_PASSWORD` | `postgres` | Database password |
| `POSTGRES_PORT` | `5432` | PostgreSQL port |

### Qdrant

| Variable | Default | Description |
|----------|---------|-------------|
| `QDRANT_HTTP_PORT` | `6333` | Qdrant HTTP API port |
| `QDRANT_GRPC_PORT` | `6334` | Qdrant gRPC port |

### pgAdmin

| Variable | Default | Description |
|----------|---------|-------------|
| `PGADMIN_EMAIL` | admin@... | pgAdmin login email |
| `PGADMIN_PASSWORD` | `admin` | pgAdmin login password |
| `PGADMIN_PORT` | `5050` | pgAdmin web port |

### Redis

| Variable | Default | Description |
|----------|---------|-------------|
| `REDIS_PASSWORD` | `redis` | Redis password |
| `REDIS_PORT` | `6379` | Redis port |

### Whisper

| Variable | Default | Description |
|----------|---------|-------------|
| `WHISPER_MODEL` | `medium` | Model size (tiny/base/small/medium/large) |
| `WHISPER_DEVICE` | `cuda` | Device (cuda/cpu) |
| `WHISPER_COMPUTE_TYPE` | `float16` | Compute type |

### Vosk

| Variable | Default | Description |
|----------|---------|-------------|
| `VOSK_MODEL_PATH` | models/vosk-... | Path to Vosk model directory |

### Audio Processing

| Variable | Default | Description |
|----------|---------|-------------|
| `AUDIO_CHUNK_DURATION` | `5` | Seconds of audio before transcription |
| `AUDIO_SILENCE_THRESHOLD` | `2.0` | Seconds of silence to trigger transcription |
| `AUDIO_SAMPLE_RATE` | `48000` | Audio sample rate (Hz) |

---

## Service URLs Reference

| Service | URL | Credentials |
|---------|-----|-------------|
| PostgreSQL | `localhost:5432` | postgres / postgres |
| Qdrant API | http://localhost:6333 | None |
| Qdrant Dashboard | http://localhost:6333/dashboard | None |
| pgAdmin | http://localhost:5050 | admin@discord-analyzer.local / admin |
| Redis | `localhost:6379` | Password from .env |

---

## Getting Help

- **Documentation:** See README.md, COMMANDS.md, CONFIG.md
- **Quick Reference:** See QUICKREF.md
- **Vosk Setup:** See VOSK_SETUP.md
- **Issues:** Check logs with `docker compose logs`
- **Discord API:** https://discord.com/developers/docs

---

## Next Steps

1. ✅ Start the bot with `.\start.ps1` or `./start.sh`
2. ✅ Join a voice channel in Discord
3. ✅ Bot will auto-join and start recording
4. ✅ Use `!help_analyzer` to see available commands
5. ✅ Use `!sessions --summary` to see recorded sessions
6. ✅ Use `!analyze` for detailed conversation analysis

Happy analyzing! 🎤📊
