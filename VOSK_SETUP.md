# Vosk Setup Guide

Vosk is a faster, more accurate alternative to Whisper for real-time speech recognition.

## Installation

```powershell
pip install vosk
```

## Download a Model

1. Visit https://alphacephei.com/vosk/models
2. Download one of these models:

### Recommended Models

**For best accuracy (1.8GB):**
- `vosk-model-en-us-0.22` - Best quality for English
- Download: https://alphacephei.com/vosk/models/vosk-model-en-us-0.22.zip

**For faster/smaller (40MB):**
- `vosk-model-small-en-us-0.15` - Good for real-time, lower resource usage
- Download: https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip

## Setup

1. Create a `models` directory in your project root:
```powershell
mkdir models
```

2. Extract the downloaded model to the `models` directory:
```
discord-social-analyzer/
├── models/
│   └── vosk-model-en-us-0.22/
│       ├── am/
│       ├── conf/
│       ├── graph/
│       └── ivector/
```

3. Update your `.env` file:
```env
VOSK_MODEL_PATH=models/vosk-model-en-us-0.22
```

## Switching Providers

The code is already updated to use Vosk. In `main.py` line 80-81:

```python
from src.providers.vosk_provider import VoskProvider
transcription_provider = VoskProvider()
```

To switch back to Whisper, comment out Vosk and uncomment Whisper:

```python
# Option 1: Whisper
transcription_provider = WhisperProvider()

# Option 2: Vosk (faster, better for real-time)
# from src.providers.vosk_provider import VoskProvider
# transcription_provider = VoskProvider()
```

## Why Vosk is Better for Real-Time

- **Faster**: Processes audio in real-time without lag
- **More Accurate**: Better at handling conversational speech
- **Lightweight**: Smaller models, less memory usage
- **Offline**: No internet required
- **No VAD Issues**: Doesn't aggressively filter out speech like Whisper's VAD

## Comparison

| Feature | Whisper | Vosk |
|---------|---------|------|
| Speed | Slow (batch processing) | Fast (real-time) |
| Accuracy | Good for clear speech | Better for conversations |
| Model Size | 140MB - 2.9GB | 40MB - 1.8GB |
| Real-time | No | Yes |
| Resource Usage | High (GPU recommended) | Low (CPU is fine) |

## Troubleshooting

**Error: "Failed to load Vosk model"**
- Make sure you downloaded and extracted the model
- Check the path in your `.env` file matches the extracted folder name
- Verify the model folder contains `am/`, `conf/`, `graph/`, and `ivector/` directories

**Poor accuracy:**
- Try the larger model (`vosk-model-en-us-0.22`)
- Ensure your microphone quality is good
- Check Discord audio settings
