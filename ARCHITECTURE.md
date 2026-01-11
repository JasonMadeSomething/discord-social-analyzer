# System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Discord Server                           │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │ Voice Channel│  │ Text Channel │  │    Users     │          │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘          │
└─────────┼──────────────────┼──────────────────┼──────────────────┘
          │                  │                  │
          │                  │                  │
┌─────────▼──────────────────▼──────────────────▼──────────────────┐
│                         Discord Bot                               │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │                    Bot Client                              │  │
│  │  - Voice state tracking                                    │  │
│  │  - Audio capture per user                                  │  │
│  │  - Message monitoring                                      │  │
│  │  - Command handling                                        │  │
│  └─────────────┬──────────────────────────┬──────────────────┘  │
└────────────────┼──────────────────────────┼─────────────────────┘
                 │                          │
        ┌────────▼────────┐        ┌────────▼────────┐
        │   Audio Stream  │        │  Text Messages  │
        └────────┬────────┘        └────────┬────────┘
                 │                          │
┌────────────────▼──────────────────────────▼─────────────────────┐
│                        Services Layer                            │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │           Transcription Service                           │  │
│  │  - Audio buffering (per user, per channel)              │  │
│  │  - Buffer management (timing, staleness)                │  │
│  │  - Coordinate transcription                             │  │
│  └────────────┬──────────────────────────────────────────────┘  │
│               │                                                  │
│  ┌────────────▼──────────────────────────────────────────────┐  │
│  │           Session Manager                                 │  │
│  │  - Track session lifecycle                               │  │
│  │  - Manage participants (join/leave)                      │  │
│  │  - Handle timeouts                                       │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────┬────────────────────────────────────────┘
                          │
         ┌────────────────┼────────────────┐
         │                │                │
┌────────▼───────┐ ┌─────▼──────┐ ┌──────▼─────────┐
│ Transcription  │ │ Repositories│ │   Providers    │
│   Providers    │ │             │ │   (DI Layer)   │
│  - Whisper     │ │  - Session  │ │                │
│  - Vosk        │ │  - Utterance│ │ - Transcription│
│                │ │  - Message  │ │ - Vector DB    │
│  - GPU/CPU     │ │             │ │ - Embeddings   │
│  - VAD Filter  │ │             │ │ - LLM          │
└────────────────┘ └─────┬──────┘ └────────────────┘
                         │
                ┌────────▼────────┐
                │   PostgreSQL    │
                │                 │
                │  Tables:        │
                │  - sessions     │
                │  - participants │
                │  - utterances   │
                │  - messages     │
                └─────────────────┘
```

## Data Flow

### Voice Processing Flow
```
1. User speaks in Discord voice channel
   ↓
2. Bot captures audio stream (per user, separate streams)
   ↓
3. Audio buffered in TranscriptionService
   ↓
4. When buffer ready (5s duration) OR stale (2s silence):
   - Convert audio to numpy array
   - Send to transcription provider (Whisper or Vosk)
   ↓
5. Provider transcribes audio
   - Whisper: GPU/CPU acceleration with VAD
   - Vosk: Real-time CPU-friendly transcription
   - Returns text + confidence score
   ↓
6. Store in database via UtteranceRepository
   - Links to session
   - Full attribution (user, timestamps)
```

### Session Management Flow
```
1. User joins voice channel
   ↓
2. Bot detects via on_voice_state_update
   ↓
3. SessionManager.start_session() (if first user)
   ↓
4. SessionManager.add_participant()
   ↓
5. Continuous activity monitoring
   ↓
6. User leaves voice channel
   ↓
7. SessionManager.remove_participant()
   ↓
8. If last user: flush buffers, end session
```

### Query Flow
```
1. User sends command (!stats, !transcript)
   ↓
2. Bot command handler invoked
   ↓
3. Repository fetches data from database
   ↓
4. Data formatted and sent to Discord
```

## Dependency Injection

All components use interfaces (Abstract Base Classes) for dependencies:

```python
ITranscriptionProvider
├── WhisperProvider (GPU-accelerated, batch processing)
├── VoskProvider (CPU-friendly, real-time)
└── [Future: AzureProvider, GoogleProvider, etc.]

IVectorStore
├── [Future: QdrantProvider]
└── [Future: ChromaProvider]

IEmbeddingProvider
├── [Future: SentenceTransformersProvider]
└── [Future: OpenAIProvider]
```

This allows swapping implementations without changing core logic.

## Key Design Decisions

1. **Separate streams per user**: Discord (via Pycord) provides separate audio streams, no need for speaker diarization
2. **Local transcription**: Using Whisper or Vosk for speed and cost savings
3. **Dual-trigger buffering**: Transcribe on 5s chunks OR 2s silence for responsive real-time processing
4. **Session-based organization**: Natural grouping for analysis
5. **Repository pattern**: Clean separation between business logic and data access
6. **Provider interfaces**: Easy to swap backends (Whisper ↔ Vosk, or add cloud providers)
