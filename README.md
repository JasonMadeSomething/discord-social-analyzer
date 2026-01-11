# Discord Social Analyzer

A Discord bot that captures voice and text conversations to analyze social dynamics, conversation patterns, and topics using local AI transcription (Whisper).

## Features

- **Real-time voice transcription** using faster-whisper (GPU accelerated)
- **Session tracking** with automatic start/stop based on channel activity
- **Full attribution** of utterances to users with timestamps
- **Text message capture** linked to voice sessions
- **Query commands** for conversation analysis
- **Extensible architecture** with dependency injection for easy provider swapping

## Architecture

```
Discord Voice/Text → Bot → Services → Repositories → PostgreSQL
                            ↓
                    Whisper (local GPU)
```

### Key Components

- **Providers**: Pluggable interfaces for transcription, embeddings, LLMs, etc.
- **Services**: Business logic (session management, transcription coordination)
- **Repositories**: Database operations
- **Models**: Domain models (business logic) + Database models (persistence)

## System Requirements

- **GPU**: NVIDIA GPU with CUDA support (for fast transcription)
- **RAM**: 8GB+ recommended
- **Python**: 3.10+
- **PostgreSQL**: 12+

## Installation

### 1. Clone and Setup

```bash
git clone <repo>
cd discord-social-analyzer

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Install PostgreSQL

**Windows (using chocolatey):**
```bash
choco install postgresql
```

**Or download from**: https://www.postgresql.org/download/windows/

### 3. Create Database

```bash
psql -U postgres
CREATE DATABASE discord_analyzer;
\q
```

### 4. Setup Discord Bot

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Create New Application
3. Go to "Bot" section:
   - Enable "Message Content Intent"
   - Enable "Server Members Intent"
   - Copy bot token
4. Go to "OAuth2" → "URL Generator":
   - Scopes: `bot`, `applications.commands`
   - Bot Permissions:
     - Read Messages/View Channels
     - Send Messages
     - Connect
     - Speak
     - Use Voice Activity
   - Copy the generated URL and invite bot to your server

### 5. Configure Environment

```bash
cp .env.example .env
# Edit .env with your values
```

**Required settings:**
- `DISCORD_TOKEN` - Your bot token from step 4

**Optional but recommended:**
- `DATABASE_URL` - Change default password
- `WHISPER_MODEL` - Adjust based on your hardware
- `LOG_LEVEL` - Set to INFO for production

**Quick reference:** See **QUICK_CONFIG.md** for copy-paste configurations
**Complete guide:** See **CONFIG.md** for detailed explanations of all settings

### 6. Run the Bot

**First, verify your setup:**
```bash
python check_env.py
```

This will check:
- .env file exists
- All packages are installed
- Configuration loads correctly
- Discord token is set
- Database connection works
- GPU/CUDA is available (if using)

**If all checks pass, start the bot:**
```bash
python main.py
```

## Usage

### Bot Commands

**Basic Commands:**
- `!stats [session_number]` - Get statistics for a session
- `!transcript [session_number] [limit]` - View conversation transcript
- `!search <query>` - Search utterances by text
- `!sessions [limit]` - List recent sessions
- `!help_analyzer` - Show all commands

**Advanced Analysis Commands:**
- `!analyze [session_number]` - Comprehensive analysis with insights
- `!speaking [session_number]` - Detailed speaking pattern breakdown
- `!turns [session_number]` - Turn-taking and response time analysis
- `!interactions [session_number]` - Who interacts with whom
- `!keywords [session_number] [count]` - Extract conversation keywords
- `!myactivity [count]` - Your participation across sessions
- `!export [session_number]` - Export full analysis as JSON

See **COMMANDS.md** for complete command reference with examples and interpretation guide.

### How It Works

1. **Automatic Session Detection**: When users join a voice channel, a session automatically starts
2. **Real-time Transcription**: Audio is buffered and transcribed every ~5 seconds
3. **Session End**: Sessions end when all users leave or after 5 minutes of inactivity
4. **Data Storage**: All utterances, messages, and session data are stored with full attribution

### Example Workflow

```
User joins voice channel
  → Bot joins and starts recording
  → Audio is captured per user
  → Every 5 seconds, audio is transcribed via Whisper
  → Transcription stored with user ID, timestamp, confidence
  → Text messages are also captured and linked to the session
  
User types: !stats
  → Bot shows speaking time, utterance count per participant

User types: !transcript
  → Bot displays chronological transcript with timestamps
```

## Configuration

### Whisper Models

| Model | Size | VRAM | Speed | Quality |
|-------|------|------|-------|---------|
| tiny | 39M | ~1GB | Fastest | Lowest |
| base | 74M | ~1GB | Fast | Low |
| small | 244M | ~2GB | Medium | Medium |
| medium | 769M | ~5GB | Slower | High |
| large-v3 | 1550M | ~10GB | Slowest | Highest |

**Recommendation**: Start with `base` for testing, use `large-v3` for production.

### Audio Settings

- `AUDIO_CHUNK_DURATION`: How long to accumulate audio before transcribing (default: 5s)
  - Lower = more responsive but more overhead
  - Higher = less overhead but delayed transcription
  
- `SESSION_TIMEOUT`: Seconds of inactivity before ending session (default: 300)

## Database Schema

### Sessions
- Tracks voice channel sessions with start/end times
- Status: active, ended, abandoned

### Participants
- Users in each session with join/leave times

### Utterances
- Transcribed speech with full attribution
- Includes confidence scores and audio duration

### Messages
- Text chat messages linked to sessions

## Future Extensions

The architecture supports easy addition of:

1. **Vector Database** (Qdrant) - Already interfaced, just needs implementation
2. **Embeddings** - For semantic search and topic clustering
3. **LLM Analysis** - Conversation summarization, sentiment analysis
4. **Social Graph Analysis** - Who talks to whom, influence scoring
5. **Real-time Dashboard** - Web interface for live insights

### Adding a New Provider

```python
# 1. Create implementation
class MyTranscriptionProvider(ITranscriptionProvider):
    async def transcribe(self, audio_data, sample_rate):
        # Your implementation
        pass

# 2. Wire it up in main.py
transcription_provider = MyTranscriptionProvider()
```

## Troubleshooting

### Bot not transcribing

1. Check logs for errors: `tail -f bot.log`
2. Verify CUDA is working: `python -c "import torch; print(torch.cuda.is_available())"`
3. Test Whisper: `python -c "from faster_whisper import WhisperModel; m = WhisperModel('base')"`

### Database connection errors

1. Verify PostgreSQL is running: `pg_isready`
2. Check credentials in `.env`
3. Ensure database exists: `psql -U postgres -l`

### Permission errors

1. Ensure bot has correct Discord permissions
2. Check intents are enabled in Discord Developer Portal

## Privacy & Legal

⚠️ **Important**: Recording conversations may have legal implications depending on your jurisdiction. Ensure:

1. All participants consent to being recorded
2. You comply with local wiretapping/recording laws
3. You have proper data retention and deletion policies
4. You secure the database appropriately

This bot is designed for research/educational purposes. Use responsibly.

## License

[Your chosen license]

## Contributing

Contributions welcome! The codebase is designed to be modular and extensible.

Key extension points:
- Add new providers in `src/providers/`
- Add analysis logic in `src/services/`
- Add commands in `src/bot/commands.py`
