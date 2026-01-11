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
│   Whisper      │ │ Repositories│ │   Providers    │
│   Provider     │ │             │ │   (DI Layer)   │
│  (faster-      │ │  - Session  │ │                │
│   whisper)     │ │  - Utterance│ │ - Transcription│
│                │ │  - Message  │ │ - Vector DB    │
│  - GPU Accel   │ │             │ │ - Embeddings   │
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
3. Audio buffered in TranscriptionService (5 second chunks)
   ↓
4. When buffer full or stale:
   - Convert audio to numpy array
   - Send to Whisper provider
   ↓
5. Whisper transcribes with GPU acceleration
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
├── WhisperProvider (current)
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

1. **Separate streams per user**: Discord provides separate audio streams, no need for speaker diarization
2. **Local GPU transcription**: Using faster-whisper for speed and cost savings
3. **Buffered transcription**: 5-second chunks balance latency vs overhead
4. **Session-based organization**: Natural grouping for analysis
5. **Repository pattern**: Clean separation between business logic and data access
6. **Provider interfaces**: Easy to swap backends (e.g., different transcription services)
