# Slash Command Migration Guide

## Migration Status

### ✅ Completed
- **VoiceCommands** (`src/bot/voice_commands.py`) - 5 commands
  - `/summon` - Summon bot to voice channel
  - `/dismiss` - Dismiss bot from voice channel
  - `/move` - Move bot to your channel
  - `/swapprovider` - Hot-swap transcription provider
  - `/provider` - Show current provider

- **SemanticCommands** (`src/bot/semantic_commands.py`) - 4 commands
  - `/semantic` - Semantic search by meaning
  - `/topicmap` - Topic clustering (placeholder)
  - `/similar` - Find similar utterances (placeholder)
  - `/vectorstats` - Vector database statistics

- **AnalysisCommands** (`src/bot/commands.py`) - 5 commands
  - `/stats` - View session statistics
  - `/transcript` - Get conversation transcript
  - `/search` - Search utterances by text
  - `/sessions` - List recent sessions
  - `/help` - Show available commands

- **AdvancedAnalysisCommands** (`src/bot/analysis_commands.py`) - 7 commands
  - `/analyze` - Comprehensive session analysis
  - `/speaking` - Speaking pattern analysis
  - `/turns` - Turn-taking analysis
  - `/interactions` - Interaction patterns
  - `/keywords` - Extract keywords
  - `/myactivity` - Your participation stats
  - `/export` - Export analysis as JSON

- **DeepAnalysisCommands** (`src/bot/advanced_commands.py`) - 4 commands
  - `/topics` - Identify conversation topics
  - `/recap` - Generate conversation recap
  - `/dynamics` - Social dynamics analysis
  - `/influence` - Influence scores

- **Bot Client** (`src/bot/client.py`)
  - ✅ Removed `command_prefix` parameter
  - ✅ Added slash command sync in `on_ready()`
  - ✅ Removed `process_commands()` call

### ⏳ In Progress
- Documentation updates

## Key Changes Made

### Import Updates
```python
# Added
from discord import ApplicationContext, Option

# Changed
ctx: commands.Context → ctx: ApplicationContext
```

### Decorator Changes
```python
# Before
@commands.command(name='summon', aliases=['join'])
async def summon(self, ctx):

# After
@discord.slash_command(
    name="summon",
    description="Summon the bot to your current voice channel to start recording"
)
async def summon(self, ctx: ApplicationContext):
```

### Parameter Changes
```python
# Before
async def command(self, ctx, provider: str):

# After
async def command(
    self,
    ctx: ApplicationContext,
    provider: Option(
        str,
        description="Choose transcription provider",
        choices=["whisper", "vosk"]
    )
):
```

### Response Method Changes
```python
# Before
await ctx.send("message")

# After
await ctx.respond("message")  # First response
await ctx.followup.send("message")  # Subsequent responses
```

## Remaining Tasks

1. Migrate remaining command files
2. Update bot client (`src/bot/client.py`):
   - Remove `command_prefix` from bot initialization
   - Add command sync in `on_ready()`
   - Remove `await self.process_commands(message)` from `on_message()`
3. Update documentation:
   - `COMMANDS.md` - Change all `!command` to `/command`
   - `README.md` - Update command syntax
   - `QUICKREF.md` - Update command reference

## Testing Checklist

- [ ] Bot starts without errors
- [ ] Commands sync successfully (check logs)
- [ ] Type `/` in Discord and see commands with autocomplete
- [ ] Test each command for functionality
- [ ] Verify optional parameters work with defaults
- [ ] Verify error handling still works
- [ ] Verify embed messages display correctly

## Benefits of Slash Commands

- ✅ Autocomplete with inline help
- ✅ Type safety and validation
- ✅ Modern Discord standard
- ✅ Mobile-friendly
- ✅ Discoverable (users can see available commands)
- ✅ Better UX with parameter descriptions
