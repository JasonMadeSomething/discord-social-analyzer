# Discord Social Analyzer - Quick Reference

One-page reference for common commands and operations.

---

## 🚀 Starting & Stopping

### Windows (PowerShell)
```powershell
# Start (default Whisper)
.\start.ps1

# Start with Vosk
.\start.ps1 -Provider vosk

# Start with pgAdmin
.\start.ps1 -WithAdmin

# Stop
.\stop.ps1
# or press Ctrl+C
```

### Windows (Batch)
```batch
start.bat
# Press Ctrl+C to stop
```

### Linux/Mac
```bash
# Start (default Whisper)
./start.sh

# Start with Vosk
./start.sh --provider vosk

# Start with pgAdmin
./start.sh --with-admin

# Stop
# Press Ctrl+C
```

---

## 🌐 Service URLs

| Service | URL | Default Credentials |
|---------|-----|---------------------|
| **PostgreSQL** | `localhost:5432` | postgres / postgres |
| **Qdrant API** | http://localhost:6333 | None |
| **Qdrant Dashboard** | http://localhost:6333/dashboard | None |
| **pgAdmin** | http://localhost:5050 | admin@discord-analyzer.local / admin |
| **Redis** | `localhost:6379` | redis (password) |

---

## 🤖 Discord Bot Commands

### Basic Commands
```
!stats [session_number]          View session statistics
!transcript [session_number]     View conversation transcript
!search <query>                  Search utterances
!sessions [limit] [--summary]    List recent sessions
!help_analyzer                   Show all commands
```

### Analysis Commands
```
!analyze [session_number]        Full conversation analysis
!speaking [session_number]       Speaking patterns
!keywords [session_number]       Top keywords
!myactivity [session_number]     Your activity stats
```

### Advanced Analysis
```
!topics [session_number]         Conversation topics
!recap [session_number]          Session summary
!dynamics [session_number]       Social dynamics
!influence [session_number]      Influence scores
```

---

## 🐳 Docker Commands

### Service Management
```bash
# Start services
docker compose up -d

# Start with profiles
docker compose --profile admin --profile cache up -d

# Stop services
docker compose down

# Stop and remove volumes
docker compose down -v

# Restart services
docker compose restart

# View status
docker compose ps
```

### Logs
```bash
# All logs
docker compose logs

# Specific service
docker compose logs postgres
docker compose logs qdrant

# Follow logs (live)
docker compose logs -f postgres

# Bot logs
tail -f bot.log
```

### Container Management
```bash
# List containers
docker ps

# Execute command in container
docker exec -it discord-analyzer-postgres psql -U postgres

# View container health
docker inspect discord-analyzer-postgres --format='{{.State.Health.Status}}'

# Remove stopped containers
docker compose rm
```

---

## 🔧 Common Issues & Solutions

| Problem | Solution |
|---------|----------|
| **Docker not running** | Start Docker Desktop (Windows/Mac) or `sudo systemctl start docker` (Linux) |
| **Port already in use** | Change port in `.env` (e.g., `POSTGRES_PORT=5433`) |
| **Bot won't start** | Check `DISCORD_TOKEN` in `.env`, ensure no extra spaces |
| **No transcriptions** | Check microphone permissions, verify bot is in voice channel |
| **Services not healthy** | Check logs: `docker logs discord-analyzer-postgres` |
| **Database connection failed** | Verify `DATABASE_URL` in `.env` matches Docker settings |
| **Whisper too slow** | Use Vosk provider or smaller Whisper model (`WHISPER_MODEL=small`) |
| **Out of memory** | Use smaller model or reduce `AUDIO_CHUNK_DURATION` |

---

## 📁 Important File Locations

| File/Directory | Purpose |
|----------------|---------|
| `.env` | Configuration (tokens, passwords, settings) |
| `docker-compose.yml` | Docker service definitions |
| `bot.log` | Bot application logs |
| `start.ps1` / `start.sh` | Startup scripts |
| `stop.ps1` | Shutdown script |
| `STARTUP.md` | Comprehensive startup guide |
| `COMMANDS.md` | All bot commands documentation |
| `CONFIG.md` | Configuration reference |

---

## 🗄️ Database Operations

### Backup
```bash
# Backup database
docker exec discord-analyzer-postgres pg_dump -U postgres discord_analyzer > backup.sql

# Backup with timestamp
docker exec discord-analyzer-postgres pg_dump -U postgres discord_analyzer > backup_$(date +%Y%m%d_%H%M%S).sql
```

### Restore
```bash
# Restore from backup
docker exec -i discord-analyzer-postgres psql -U postgres discord_analyzer < backup.sql
```

### Reset
```bash
# Stop services and remove all data
docker compose down -v

# Start fresh
docker compose up -d
```

### Access PostgreSQL
```bash
# Via Docker
docker exec -it discord-analyzer-postgres psql -U postgres -d discord_analyzer

# Via local psql
psql -h localhost -U postgres -d discord_analyzer
```

---

## ⚙️ Configuration Quick Reference

### Transcription Providers

**Whisper** (High Accuracy)
```env
WHISPER_MODEL=medium          # tiny, base, small, medium, large
WHISPER_DEVICE=cuda           # cuda or cpu
WHISPER_COMPUTE_TYPE=float16  # float16, int8
```

**Vosk** (Fast, CPU-friendly)
```env
VOSK_MODEL_PATH=models/vosk-model-en-us-0.22
```

### Audio Settings
```env
AUDIO_CHUNK_DURATION=5        # Seconds before transcription
AUDIO_SILENCE_THRESHOLD=2.0   # Silence detection (seconds)
AUDIO_SAMPLE_RATE=48000       # Sample rate (Hz)
```

### Database
```env
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/discord_analyzer
```

---

## 🎯 Quick Workflows

### First-Time Setup
1. Install Docker Desktop
2. Clone repository
3. Run `.\start.ps1` (creates `.env` from example)
4. Edit `.env` with Discord token
5. Run `.\start.ps1` again

### Daily Usage
1. `.\start.ps1` or `./start.sh`
2. Join voice channel in Discord
3. Bot auto-joins and records
4. Use `!sessions --summary` to see sessions
5. Use `!analyze` for insights
6. Press Ctrl+C to stop

### Development
1. `docker compose up -d` (services only)
2. `python main.py --provider whisper` (manual bot start)
3. Make code changes
4. Restart bot manually
5. `docker compose down` when done

### Troubleshooting
1. Check logs: `docker compose logs`
2. Check bot log: `tail -f bot.log`
3. Restart services: `docker compose restart`
4. Full reset: `docker compose down -v && docker compose up -d`

---

## 📚 Documentation Links

- **Comprehensive Guide:** [STARTUP.md](STARTUP.md)
- **Bot Commands:** [COMMANDS.md](COMMANDS.md)
- **Configuration:** [CONFIG.md](CONFIG.md)
- **Vosk Setup:** [VOSK_SETUP.md](VOSK_SETUP.md)
- **Architecture:** [ARCHITECTURE.md](ARCHITECTURE.md)
- **Project Summary:** [PROJECT_SUMMARY.md](PROJECT_SUMMARY.md)

---

## 🆘 Getting Help

1. **Check logs:** `docker compose logs` and `bot.log`
2. **Read docs:** Start with [STARTUP.md](STARTUP.md)
3. **Common issues:** See troubleshooting section above
4. **Discord API:** https://discord.com/developers/docs
5. **Docker docs:** https://docs.docker.com

---

## 💡 Pro Tips

- Use `--summary` flag with `!sessions` to see what each session was about
- Start with Vosk for testing, switch to Whisper for production
- Use pgAdmin (`-WithAdmin`) for database inspection
- Enable `DEV_MODE` in `.env` for detailed logging
- Backup database regularly with `pg_dump`
- Use smaller Whisper models (`small` or `base`) for faster processing
- Check Qdrant dashboard at http://localhost:6333/dashboard for vector data

---

**Quick Start:** `.\start.ps1` or `./start.sh` → Join voice channel → `!help_analyzer`
