# Configuration Guide

This guide explains all configuration options and how to set them up.

## Quick Setup

1. **Copy the example file:**
   ```bash
   cp .env.example .env
   ```

2. **Edit .env with your values:**
   ```bash
   # Windows
   notepad .env
   
   # Mac/Linux
   nano .env
   # or
   vim .env
   ```

3. **Set required values (minimum to run):**
   - `DISCORD_TOKEN` - Your bot token
   - `DATABASE_URL` - Your database connection (or use default for local PostgreSQL)

## Required Configuration

### DISCORD_TOKEN
**Required: Yes**

Your Discord bot token from the Discord Developer Portal.

**How to get:**
1. Go to https://discord.com/developers/applications
2. Select your application (or create one)
3. Go to "Bot" section
4. Click "Reset Token" or "Copy" to get your token
5. Paste it in .env as: `DISCORD_TOKEN=your_token_here`

**⚠️ Security Warning:** Never share this token or commit it to git!

### DATABASE_URL
**Required: Yes (but has default)**

PostgreSQL connection string.

**Default:** `postgresql://postgres:postgres@localhost:5432/discord_analyzer`

**Format:** `postgresql://[user]:[password]@[host]:[port]/[database_name]`

**Examples:**
```bash
# Local PostgreSQL with default user
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/discord_analyzer

# Local PostgreSQL with custom user
DATABASE_URL=postgresql://myuser:mypassword@localhost:5432/discord_analyzer

# Remote PostgreSQL
DATABASE_URL=postgresql://user:pass@db.example.com:5432/dbname

# PostgreSQL on Railway/Heroku/etc
DATABASE_URL=postgresql://user:pass@host.provider.com:5432/dbname
```

**Alternative:** You can also set individual components:
```bash
DB_HOST=localhost
DB_PORT=5432
DB_USER=postgres
DB_PASSWORD=your_password
DB_NAME=discord_analyzer
```

## Optional But Recommended

### WHISPER_MODEL
**Default:** `base`

Model size affects transcription quality and speed.

**Options:**
- `tiny` - Fastest, lowest quality (39M params, ~1GB VRAM)
- `base` - Good balance (74M params, ~1GB VRAM) ⭐ **Recommended for testing**
- `small` - Better quality (244M params, ~2GB VRAM) ⭐ **Recommended for production**
- `medium` - High quality (769M params, ~5GB VRAM)
- `large-v3` - Best quality (1550M params, ~10GB VRAM)

**Your RTX 4090 can handle any of these easily!**

### WHISPER_DEVICE
**Default:** `cuda`

**Options:**
- `cuda` - Use GPU (much faster) ⭐ **Recommended**
- `cpu` - Use CPU only (very slow, only if no GPU)

**Note:** Your system has a powerful RTX 4090 - definitely use `cuda`!

### LOG_LEVEL
**Default:** `INFO`

Controls how verbose the logs are.

**Options:**
- `DEBUG` - Everything (very verbose, for troubleshooting)
- `INFO` - General information ⭐ **Recommended for normal use**
- `WARNING` - Only warnings and errors
- `ERROR` - Only errors
- `CRITICAL` - Only critical errors

## Performance Tuning

### For Maximum Speed
```bash
WHISPER_MODEL=small
WHISPER_DEVICE=cuda
WHISPER_COMPUTE_TYPE=int8
AUDIO_CHUNK_DURATION=8
TRANSCRIPTION_MAX_CONCURRENT=10
```

### For Maximum Quality
```bash
WHISPER_MODEL=large-v3
WHISPER_DEVICE=cuda
WHISPER_COMPUTE_TYPE=float16
AUDIO_CHUNK_DURATION=3
AUDIO_MIN_DURATION=0.3
```

### For Balanced Production Use (Recommended)
```bash
WHISPER_MODEL=small
WHISPER_DEVICE=cuda
WHISPER_COMPUTE_TYPE=float16
AUDIO_CHUNK_DURATION=5
SESSION_TIMEOUT=300
```

### For Low Resource Systems (CPU only)
```bash
WHISPER_MODEL=tiny
WHISPER_DEVICE=cpu
AUDIO_CHUNK_DURATION=10
TRANSCRIPTION_WORKERS=1
TRANSCRIPTION_MAX_CONCURRENT=2
```

## Audio Processing Settings

### AUDIO_CHUNK_DURATION
**Default:** `5` seconds

How long to accumulate audio before transcribing.

- **Lower (2-3s):** More responsive, higher overhead
- **Medium (5-7s):** Good balance ⭐ **Recommended**
- **Higher (8-12s):** Less overhead, delayed transcription

### AUDIO_SILENCE_THRESHOLD
**Default:** `2.0` seconds

How long silence before considering an utterance complete.

- Too low: Cuts off mid-sentence
- Too high: Delays transcription
- **2-3s is usually good**

### AUDIO_MIN_DURATION
**Default:** `0.5` seconds

Minimum audio length to transcribe (filters out brief noises).

## Session Management

### SESSION_TIMEOUT
**Default:** `300` seconds (5 minutes)

How long before an inactive channel's session auto-ends.

- **Lower (60-180s):** Stricter, more separate sessions
- **Medium (300-600s):** Balanced ⭐ **Recommended**
- **Higher (900-1800s):** More lenient, longer sessions

## Security Configuration

### ALLOWED_USER_IDS
**Default:** Empty (all users allowed)

Restrict bot to specific Discord users.

**Format:** Comma-separated user IDs
```bash
ALLOWED_USER_IDS=123456789012345678,987654321098765432
```

**How to get user IDs:**
1. Enable Developer Mode in Discord (User Settings → Advanced)
2. Right-click user → Copy ID

### ALLOWED_CHANNEL_IDS
**Default:** Empty (all channels allowed)

Restrict bot to specific Discord channels.

**Format:** Comma-separated channel IDs
```bash
ALLOWED_CHANNEL_IDS=123456789012345678,987654321098765432
```

### ADMIN_USER_IDS
**Default:** Empty (no admins)

Users with elevated permissions for management commands.

**Format:** Comma-separated user IDs
```bash
ADMIN_USER_IDS=123456789012345678
```

## Feature Flags

Enable/disable major features:

```bash
FEATURE_TRANSCRIPTION=true      # Voice transcription
FEATURE_MESSAGE_LOGGING=true    # Text message logging
FEATURE_SESSION_TRACKING=true   # Session tracking
```

Useful for:
- Testing individual features
- Gradual rollout
- Debugging

## Advanced Settings

### WHISPER_COMPUTE_TYPE
**Default:** `float16`

Precision for GPU computation.

**Options:**
- `float16` - Best quality (requires GPU) ⭐ **Recommended**
- `int8` - Faster, slightly lower quality
- `int8_float16` - Balance

### TRANSCRIPTION_WORKERS
**Default:** `2`

Number of worker threads for transcription.

- More workers = more concurrent processing
- Don't exceed CPU core count (you have 32 threads available)
- 2-4 is usually fine

### TRANSCRIPTION_MAX_CONCURRENT
**Default:** `5`

Maximum simultaneous transcriptions.

- Prevents overwhelming GPU
- Your RTX 4090 can handle 10-20 easily

## Validation

After setting up your .env, validate it:

```bash
# Test configuration loading
python -c "from src.config import settings; print('Config loaded successfully!')"

# Check specific values
python -c "from src.config import settings; print(f'Model: {settings.whisper_model}'); print(f'Device: {settings.whisper_device}')"

# Test database connection
python -c "from sqlalchemy import create_engine; from src.config import settings; engine = create_engine(settings.get_database_url()); conn = engine.connect(); print('Database connection successful!'); conn.close()"
```

## Common Issues

### "No module named 'pydantic'"
```bash
pip install -r requirements.txt
```

### "DISCORD_TOKEN is required"
You forgot to set DISCORD_TOKEN in .env

### "Could not connect to database"
- Check PostgreSQL is running: `pg_isready`
- Verify DATABASE_URL is correct
- Ensure database exists

### "CUDA not available"
- Check GPU drivers
- Verify CUDA installation: `python -c "import torch; print(torch.cuda.is_available())"`
- Fall back to CPU: `WHISPER_DEVICE=cpu`

## Environment-Specific Configs

### Development
```bash
LOG_LEVEL=DEBUG
WHISPER_MODEL=base
AUDIO_CHUNK_DURATION=5
```

### Testing
```bash
LOG_LEVEL=INFO
WHISPER_MODEL=tiny
FEATURE_MESSAGE_LOGGING=false  # Don't log during tests
```

### Production
```bash
LOG_LEVEL=INFO
WHISPER_MODEL=small
AUDIO_CHUNK_DURATION=5
SESSION_AUTO_CLEANUP=true
```

## Best Practices

1. **Never commit .env to git** - It's in .gitignore, keep it that way
2. **Use strong passwords** - Especially for DATABASE_URL in production
3. **Start with defaults** - They're chosen to work well for most cases
4. **Tune gradually** - Change one setting at a time and test
5. **Monitor logs** - Check bot.log for performance insights
6. **Backup your .env** - Keep a secure backup (not in git!)

## Getting Help

If you're stuck:
1. Check SETUP.md for step-by-step setup
2. See README.md for general documentation
3. Look at bot.log for error messages
4. Verify .env has no typos (common issue!)

## Example .env Files

See `.env.example` for a complete, commented template with all options explained.
