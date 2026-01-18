# Prosody Feature Installation Guide

## Quick Start

### 1. Install Dependencies

```bash
pip install praat-parselmouth>=0.4.3 scipy
```

Or update from requirements.txt:

```bash
pip install -r requirements.txt
```

### 2. Apply Database Migration

For existing databases, run the SQL migration on the Docker container:

```powershell
# PowerShell (Windows)
Get-Content migrations/add_prosody_column.sql | docker exec -i discord-analyzer-postgres psql -U postgres -d discord_analyzer

# Or using bash/Linux
docker exec -i discord-analyzer-postgres psql -U postgres -d discord_analyzer < migrations/add_prosody_column.sql
```

**Note:** If you're starting fresh, the schema will be created automatically via SQLAlchemy when the bot starts.

### 3. Restart the Bot

```bash
./start.ps1
```

The prosody extractor will now run automatically for all new utterances.

## Verification

### Check Prosody Extraction is Working

1. **Start the bot and join a voice channel**
2. **Speak for a few seconds**
3. **Check the logs for:**
   ```
   Extracted prosody features for user <user_id>
   ```

4. **Query the database:**
   ```sql
   SELECT id, text, prosody 
   FROM utterances 
   WHERE prosody IS NOT NULL 
   ORDER BY id DESC 
   LIMIT 5;
   ```

### Example Output

```json
{
  "pitch_mean_hz": 145.3,
  "pitch_min_hz": 120.5,
  "pitch_max_hz": 180.2,
  "pitch_stdev": 15.8,
  "pitch_range_hz": 59.7,
  "final_pitch_slope": 12.4,
  "intensity_mean_db": 68.5,
  "intensity_max_db": 75.2,
  "intensity_stdev": 4.3,
  "final_intensity_slope": -2.1,
  "jitter_local": 0.012,
  "shimmer_local": 0.045,
  "hnr_db": 18.7,
  "voiced_fraction": 0.85,
  "pause_count": 2,
  "total_pause_duration_ms": 450.0,
  "speech_rate_syllables_sec": 4.2
}
```

## Troubleshooting

### Parselmouth Installation Issues

**Windows:**
```bash
# May need Visual C++ Build Tools
# Download from: https://visualstudio.microsoft.com/visual-cpp-build-tools/
pip install praat-parselmouth
```

**Linux:**
```bash
# May need additional dependencies
sudo apt-get install python3-dev
pip install praat-parselmouth
```

**macOS:**
```bash
# Should work out of the box
pip install praat-parselmouth
```

### Prosody Extraction Failures

If you see warnings like:
```
Prosody extraction failed for user <id>: <error>
```

**Common causes:**
1. **Very short audio** (< 0.3s): Some features require minimum duration
2. **Very noisy audio**: Pitch detection may fail
3. **Whispered speech**: Low intensity may cause issues

**These are non-fatal** - the utterance will still be stored with `prosody: null`.

### Performance Issues

If prosody extraction is slowing down the pipeline:

1. **Check extraction time in logs:**
   ```
   Extracted prosody features for user <id>  # Should be < 300ms
   ```

2. **Reduce sample rate** (in `src/services/transcription.py`):
   ```python
   self.prosody_extractor = ProsodyExtractor(target_sample_rate=8000)  # Lower quality but faster
   ```

3. **Disable for testing:**
   ```python
   # Temporarily comment out in _process_buffer
   # prosody_features = await asyncio.get_event_loop().run_in_executor(...)
   prosody_features = None
   ```

## Testing

### Manual Test

```python
import numpy as np
from src.services.prosody_extractor import ProsodyExtractor

# Create test audio (1 second of 440Hz tone)
sample_rate = 48000
duration = 1.0
t = np.linspace(0, duration, int(sample_rate * duration))
audio = 0.5 * np.sin(2 * np.pi * 440 * t).astype(np.float32)

# Extract features
extractor = ProsodyExtractor(target_sample_rate=16000)
features = extractor.extract_features(audio, sample_rate)

print(features)
# Should show pitch_mean_hz around 440Hz
```

### Integration Test

1. Start the bot
2. Use `/summon` to join a voice channel
3. Speak: "This is a test of prosody extraction"
4. Check database:
   ```sql
   SELECT 
       text,
       prosody->>'pitch_mean_hz' as pitch,
       prosody->>'intensity_mean_db' as loudness,
       prosody->>'speech_rate_syllables_sec' as rate
   FROM utterances
   WHERE text LIKE '%prosody extraction%';
   ```

## Next Steps

See `PROSODY_FEATURES.md` for:
- Complete feature descriptions
- Query examples
- Analysis use cases
- API usage examples
