# Setup Checklist

Use this checklist to ensure everything is properly configured.

## Prerequisites

- [ ] Python 3.10+ installed
- [ ] NVIDIA GPU with CUDA support (for GPU acceleration)
- [ ] PostgreSQL 12+ installed
- [ ] Discord account and server for testing

## Installation Steps

### 1. Repository Setup
- [ ] Clone repository
- [ ] Create virtual environment: `python -m venv venv`
- [ ] Activate virtual environment
  - Windows: `venv\Scripts\activate`
  - Linux/Mac: `source venv/bin/activate`
- [ ] Install dependencies: `pip install -r requirements.txt`

### 2. Database Setup
- [ ] PostgreSQL service is running
- [ ] Create database: `CREATE DATABASE discord_analyzer;`
- [ ] Test connection: `psql -U postgres -d discord_analyzer -c "SELECT 1;"`

### 3. Discord Bot Setup
- [ ] Created application in Discord Developer Portal
- [ ] Created bot under application
- [ ] Enabled required intents:
  - [ ] Message Content Intent
  - [ ] Server Members Intent
- [ ] Copied bot token
- [ ] Generated OAuth2 URL with scopes: `bot`, `applications.commands`
- [ ] Generated OAuth2 URL with permissions:
  - [ ] Read Messages/View Channels
  - [ ] Send Messages
  - [ ] Connect
  - [ ] Speak
  - [ ] Use Voice Activity
- [ ] Invited bot to test server

### 4. Configuration
- [ ] Copied `.env.example` to `.env`
- [ ] Set `DISCORD_TOKEN` in `.env`
- [ ] Set `DATABASE_URL` in `.env`
- [ ] Chose `WHISPER_MODEL` (start with `base`)
- [ ] Set `WHISPER_DEVICE` (`cuda` or `cpu`)

### 5. Testing

#### Test Database Connection
```bash
python -c "from sqlalchemy import create_engine; from src.config import settings; engine = create_engine(settings.database_url); print('Database OK' if engine.connect() else 'Database FAILED')"
```
- [ ] Database connection successful

#### Test CUDA (if using GPU)
```bash
python -c "import torch; print(f'CUDA Available: {torch.cuda.is_available()}'); print(f'GPU: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else "N/A"}')"
```
- [ ] CUDA is available
- [ ] GPU detected

#### Test Whisper
```bash
python -c "from faster_whisper import WhisperModel; m = WhisperModel('base', device='cuda'); print('Whisper OK')"
```
- [ ] Whisper model loads successfully

#### Test Bot Connection
```bash
python main.py
# Watch for "Logged in as..." message
# Press Ctrl+C to stop
```
- [ ] Bot connects to Discord
- [ ] No error messages in logs

## First Run

### 6. Live Test
- [ ] Start bot: `python main.py`
- [ ] Verify bot appears online in Discord
- [ ] Join a voice channel
- [ ] Verify bot joins and starts recording (check logs)
- [ ] Speak for a few seconds
- [ ] Check logs for "Transcribed utterance" messages
- [ ] Run `!stats` command
- [ ] Verify stats display correctly
- [ ] Run `!transcript` command
- [ ] Verify transcript displays your speech

## Troubleshooting

### Bot won't start
- Check `bot.log` for errors
- Verify `DISCORD_TOKEN` is correct
- Ensure database is accessible

### Bot joins but doesn't transcribe
- Check GPU/CUDA setup
- Try `WHISPER_MODEL=tiny` for faster testing
- Check logs for transcription errors
- Verify VAD is working (voice activity detection)

### Transcription is slow
- Your GPU may be busy
- Try smaller model (`tiny` or `base`)
- Check `nvidia-smi` for GPU usage

### Transcription quality is poor
- Use larger model (`medium` or `large-v3`)
- Ensure good audio quality in Discord
- Check microphone settings

### Database errors
- Verify PostgreSQL is running
- Check database exists
- Verify credentials in `.env`

## Performance Tuning

### For Better Speed
- [ ] Use smaller model (`tiny`, `base`)
- [ ] Increase `AUDIO_CHUNK_DURATION` to 10-15 seconds
- [ ] Ensure GPU is not being used by other applications

### For Better Quality
- [ ] Use larger model (`large-v3`)
- [ ] Decrease `AUDIO_CHUNK_DURATION` to 3 seconds
- [ ] Use `WHISPER_COMPUTE_TYPE=float16` for best quality

### For Lower Resource Usage
- [ ] Use `WHISPER_DEVICE=cpu` (much slower)
- [ ] Use `tiny` model
- [ ] Increase `AUDIO_CHUNK_DURATION` to reduce frequency

## Recommended Settings by Use Case

### Development/Testing
```
WHISPER_MODEL=base
WHISPER_DEVICE=cuda
AUDIO_CHUNK_DURATION=5
```

### Production (Quality)
```
WHISPER_MODEL=large-v3
WHISPER_DEVICE=cuda
WHISPER_COMPUTE_TYPE=float16
AUDIO_CHUNK_DURATION=3
```

### Production (Speed)
```
WHISPER_MODEL=small
WHISPER_DEVICE=cuda
WHISPER_COMPUTE_TYPE=int8
AUDIO_CHUNK_DURATION=8
```

### Low Resource
```
WHISPER_MODEL=tiny
WHISPER_DEVICE=cpu
AUDIO_CHUNK_DURATION=10
```

## Next Steps

Once everything is working:

1. **Add more commands** in `src/bot/commands.py`
2. **Implement analysis features** in `src/services/analyzer.py`
3. **Add vector database** for semantic search
4. **Add embeddings** for topic clustering
5. **Build dashboard** for visualization

See `README.md` for detailed documentation.
