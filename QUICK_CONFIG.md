# Quick Configuration Reference

Copy-paste configurations for common scenarios.

## Minimal Setup (Get Started Fast)

```bash
# Just set your Discord token - everything else has sensible defaults
DISCORD_TOKEN=your_token_here
```

That's it! The bot will use:
- `base` Whisper model
- CUDA GPU
- Local PostgreSQL with default credentials
- 5-second audio chunks

---

## Your System (RTX 4090 Optimized)

```bash
DISCORD_TOKEN=your_token_here
DATABASE_URL=postgresql://postgres:YOUR_PASSWORD@localhost:5432/discord_analyzer

# Optimize for your powerful hardware
WHISPER_MODEL=small
WHISPER_DEVICE=cuda
WHISPER_COMPUTE_TYPE=float16
TRANSCRIPTION_MAX_CONCURRENT=10
```

---

## High Quality Mode

```bash
DISCORD_TOKEN=your_token_here
DATABASE_URL=postgresql://postgres:YOUR_PASSWORD@localhost:5432/discord_analyzer

# Maximum transcription quality
WHISPER_MODEL=large-v3
WHISPER_DEVICE=cuda
WHISPER_COMPUTE_TYPE=float16
AUDIO_CHUNK_DURATION=3
AUDIO_MIN_DURATION=0.3
WHISPER_VAD_ENABLED=true
```

---

## Fast & Efficient Mode

```bash
DISCORD_TOKEN=your_token_here
DATABASE_URL=postgresql://postgres:YOUR_PASSWORD@localhost:5432/discord_analyzer

# Prioritize speed
WHISPER_MODEL=small
WHISPER_DEVICE=cuda
WHISPER_COMPUTE_TYPE=int8
AUDIO_CHUNK_DURATION=8
TRANSCRIPTION_MAX_CONCURRENT=15
```

---

## CPU-Only Mode (No GPU)

```bash
DISCORD_TOKEN=your_token_here
DATABASE_URL=postgresql://postgres:YOUR_PASSWORD@localhost:5432/discord_analyzer

# For systems without CUDA
WHISPER_MODEL=tiny
WHISPER_DEVICE=cpu
AUDIO_CHUNK_DURATION=10
TRANSCRIPTION_WORKERS=2
TRANSCRIPTION_MAX_CONCURRENT=2
```

---

## Development Mode

```bash
DISCORD_TOKEN=your_token_here
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/discord_analyzer_dev

# More logging, faster iteration
LOG_LEVEL=DEBUG
WHISPER_MODEL=base
AUDIO_CHUNK_DURATION=5
SESSION_TIMEOUT=120
LOG_TO_CONSOLE=true
LOG_TO_FILE=true
```

---

## Production Mode

```bash
DISCORD_TOKEN=your_token_here
DATABASE_URL=postgresql://prod_user:STRONG_PASSWORD@localhost:5432/discord_analyzer

# Optimized for production
WHISPER_MODEL=small
WHISPER_DEVICE=cuda
WHISPER_COMPUTE_TYPE=float16
LOG_LEVEL=INFO
SESSION_TIMEOUT=300
SESSION_AUTO_CLEANUP=true
FEATURE_TRANSCRIPTION=true
FEATURE_MESSAGE_LOGGING=true
FEATURE_SESSION_TRACKING=true
```

---

## Restricted/Private Server

```bash
DISCORD_TOKEN=your_token_here
DATABASE_URL=postgresql://postgres:YOUR_PASSWORD@localhost:5432/discord_analyzer

# Limit to specific users/channels
ALLOWED_USER_IDS=123456789,987654321
ALLOWED_CHANNEL_IDS=111222333444555666
ADMIN_USER_IDS=123456789

# Standard settings
WHISPER_MODEL=small
WHISPER_DEVICE=cuda
```

---

## Testing/Debugging

```bash
DISCORD_TOKEN=your_token_here
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/discord_analyzer_test

# Maximum visibility
LOG_LEVEL=DEBUG
WHISPER_MODEL=tiny
AUDIO_CHUNK_DURATION=3
LOG_TO_CONSOLE=true
LOG_TO_FILE=true

# Can disable features to test specific components
FEATURE_TRANSCRIPTION=true
FEATURE_MESSAGE_LOGGING=false
FEATURE_SESSION_TRACKING=true
```

---

## Quiet/Minimal Logging

```bash
DISCORD_TOKEN=your_token_here
DATABASE_URL=postgresql://postgres:YOUR_PASSWORD@localhost:5432/discord_analyzer

# Only log warnings and errors
LOG_LEVEL=WARNING
LOG_TO_CONSOLE=false
LOG_TO_FILE=true

# Standard transcription
WHISPER_MODEL=small
WHISPER_DEVICE=cuda
```

---

## Remote Database

```bash
DISCORD_TOKEN=your_token_here

# Cloud database (Railway, Heroku, etc.)
DATABASE_URL=postgresql://user:pass@hostname.provider.com:5432/dbname

# Standard settings
WHISPER_MODEL=small
WHISPER_DEVICE=cuda
WHISPER_COMPUTE_TYPE=float16
```

---

## Multiple Configurations (Use Different .env Files)

**Development (.env.dev):**
```bash
DISCORD_TOKEN=dev_bot_token
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/discord_dev
LOG_LEVEL=DEBUG
WHISPER_MODEL=base
```

**Production (.env.prod):**
```bash
DISCORD_TOKEN=prod_bot_token
DATABASE_URL=postgresql://prod_user:password@db.prod.com:5432/discord_prod
LOG_LEVEL=INFO
WHISPER_MODEL=small
```

**Load different configs:**
```bash
# Development
cp .env.dev .env
python main.py

# Production
cp .env.prod .env
python main.py
```

---

## Quick Checks

**Verify config loads:**
```bash
python -c "from src.config import settings; print('✓ Config OK')"
```

**Check Discord token:**
```bash
python -c "from src.config import settings; print('Token:', settings.discord_token[:20] + '...')"
```

**Check database URL (safe - hides password):**
```bash
python -c "from src.config import settings; url = settings.get_database_url(); print('DB:', url.split('@')[1] if '@' in url else 'localhost')"
```

**Test database connection:**
```bash
python -c "from sqlalchemy import create_engine; from src.config import settings; create_engine(settings.get_database_url()).connect(); print('✓ Database OK')"
```

**Check GPU availability:**
```bash
python -c "import torch; print('CUDA:', '✓' if torch.cuda.is_available() else '✗'); print('GPU:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'N/A')"
```

---

## Troubleshooting

**Bot won't start:**
```bash
# Check what's missing
python -c "from src.config import settings"
# If error, it will tell you which required field is missing
```

**Slow transcription:**
```bash
# Try these settings
WHISPER_MODEL=small  # or tiny for testing
AUDIO_CHUNK_DURATION=8
WHISPER_COMPUTE_TYPE=int8
```

**Out of memory:**
```bash
# Reduce model size
WHISPER_MODEL=base  # or small
TRANSCRIPTION_MAX_CONCURRENT=3
```

**High CPU usage:**
```bash
# Reduce workers
TRANSCRIPTION_WORKERS=1
TRANSCRIPTION_MAX_CONCURRENT=2
```

---

## Remember

1. **Never commit .env** - It's already in .gitignore
2. **Copy .env.example first** - `cp .env.example .env`
3. **Only DISCORD_TOKEN is required** - Everything else has defaults
4. **Start simple** - Add complexity as needed
5. **One change at a time** - Easier to debug

For complete details, see **CONFIG.md**.
