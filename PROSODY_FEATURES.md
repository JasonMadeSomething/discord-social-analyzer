# Prosody Feature Extraction

This document describes the prosodic feature extraction system integrated into the utterance capture pipeline.

## Overview

Prosody features are automatically extracted from each utterance's audio using Parselmouth (a Python interface to Praat). These features capture vocal characteristics beyond the transcribed text, including pitch, intensity, voice quality, and rhythm patterns.

## Features Extracted

### Pitch (F0) Features
- **pitch_mean_hz**: Average fundamental frequency across the utterance
- **pitch_min_hz**: Minimum pitch value
- **pitch_max_hz**: Maximum pitch value  
- **pitch_stdev**: Standard deviation of pitch (variability)
- **pitch_range_hz**: Pitch range (max - min)
- **final_pitch_slope**: Linear slope over final 200ms (Hz/s, positive = rising intonation)

### Intensity Features
- **intensity_mean_db**: Average loudness in decibels
- **intensity_max_db**: Peak loudness
- **intensity_stdev**: Loudness variability
- **final_intensity_slope**: Slope over final 200ms (dB/s, negative = trailing off)

### Voice Quality Features
- **jitter_local**: Pitch perturbation (cycle-to-cycle variation)
- **shimmer_local**: Amplitude perturbation
- **hnr_db**: Harmonics-to-Noise Ratio (voice clarity)

### Rhythm/Fluency Features
- **voiced_fraction**: Proportion of utterance that contains voiced speech (0.0-1.0)
- **pause_count**: Number of internal silences > 150ms
- **total_pause_duration_ms**: Total duration of pauses in milliseconds
- **speech_rate_syllables_sec**: Estimated syllables per second (via intensity peaks)

## Database Storage

Features are stored in the `prosody` JSONB column on the `utterances` table:

```sql
-- Example query: Find utterances with rising intonation
SELECT id, text, prosody->>'final_pitch_slope' as pitch_slope
FROM utterances
WHERE (prosody->>'final_pitch_slope')::float > 0
ORDER BY (prosody->>'final_pitch_slope')::float DESC
LIMIT 10;

-- Example: Find high-energy utterances
SELECT id, text, prosody->>'intensity_mean_db' as loudness
FROM utterances
WHERE (prosody->>'intensity_mean_db')::float > 70
ORDER BY started_at DESC;

-- Example: Analyze speaking rate by user
SELECT 
    username,
    AVG((prosody->>'speech_rate_syllables_sec')::float) as avg_speech_rate
FROM utterances
WHERE prosody->>'speech_rate_syllables_sec' IS NOT NULL
GROUP BY username
ORDER BY avg_speech_rate DESC;
```

## Implementation Details

### Audio Processing
- Input: 48kHz Discord audio (float32, mono)
- Resampled to 16kHz for Parselmouth processing
- Extraction runs asynchronously in thread pool to avoid blocking transcription

### Error Handling
- Extraction failures are logged but don't block utterance storage
- Individual feature failures result in `null` values for that feature
- Very short or noisy segments may have limited feature availability

### Performance
- Prosody extraction runs in parallel with transcription
- Average extraction time: ~100-300ms per utterance
- No impact on transcription latency

## Usage Examples

### Python API
```python
from src.repositories.utterance_repo import UtteranceRepository

# Query utterances with prosody data
utterances = utterance_repo.get_utterances_by_session(session_id)

for utt in utterances:
    if utt.prosody:
        pitch = utt.prosody.get('pitch_mean_hz')
        intensity = utt.prosody.get('intensity_mean_db')
        print(f"{utt.username}: pitch={pitch:.1f}Hz, loudness={intensity:.1f}dB")
```

### Analysis Use Cases
1. **Emotion Detection**: High pitch + high intensity + rising intonation → excitement
2. **Engagement Metrics**: Speech rate, pause patterns, voice quality
3. **Turn-taking Analysis**: Final pitch slope indicates question vs statement
4. **Speaker Profiling**: Average pitch, intensity, speaking rate per user
5. **Conversation Dynamics**: Energy levels, interruption patterns

## Dependencies

- `praat-parselmouth>=0.4.3`: Praat interface for acoustic analysis
- `scipy`: Statistical functions for slope calculation
- `numpy`: Array operations

## Migration

For existing databases, run the migration script:

```bash
psql -U your_user -d your_database -f migrations/add_prosody_column.sql
```

Or the migration will be applied automatically on next bot startup via SQLAlchemy schema updates.

## Configuration

Prosody extraction is enabled by default. To disable (not recommended):

```python
# In TranscriptionService.__init__
self.prosody_extractor = None  # Disable prosody extraction
```

## Troubleshooting

### Missing Features
If many features are `null`:
- Check audio quality (very noisy audio may fail pitch detection)
- Verify utterance duration (very short clips < 0.3s may have limited features)
- Check logs for specific extraction errors

### Performance Issues
If prosody extraction is too slow:
- Reduce `target_sample_rate` in ProsodyExtractor (default: 16000)
- Consider disabling for very high-volume scenarios

## Future Enhancements

Potential additions:
- Formant analysis (vowel quality)
- Speaking style classification
- Emotion/sentiment from prosody
- Speaker diarization features
- Real-time prosody monitoring
