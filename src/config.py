from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    """
    Application configuration with environment variable support.
    All settings can be overridden via environment variables or .env file.
    """
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"  # Ignore extra fields in .env
    )
    
    # =========================================================================
    # Discord Configuration
    # =========================================================================
    discord_token: str  # REQUIRED: Your Discord bot token
    discord_guild_id: Optional[int] = None  # Optional: Specific guild to monitor
    command_prefix: str = "!"
    
    # =========================================================================
    # Database Configuration
    # =========================================================================
    database_url: str = "postgresql://postgres:postgres@localhost:5432/discord_analyzer"
    
    # Individual database components (alternative to DATABASE_URL)
    db_host: Optional[str] = None
    db_port: Optional[int] = None
    db_user: Optional[str] = None
    db_password: Optional[str] = None
    db_name: Optional[str] = None
    
    # =========================================================================
    # Whisper Configuration
    # =========================================================================
    # Model size: tiny, base, small, medium, large-v2, large-v3
    whisper_model: str = "base"
    
    # Device: cuda or cpu
    whisper_device: str = "cuda"
    
    # Compute type: float16, int8, int8_float16
    whisper_compute_type: str = "float16"
    
    # Enable/disable voice activity detection (filters silence)
    whisper_vad_enabled: bool = True
    
    # Minimum silence duration in ms for VAD
    whisper_vad_min_silence_ms: int = 500
    
    # =========================================================================
    # Vector Store Configuration (Qdrant - for future use)
    # =========================================================================
    qdrant_enabled: bool = False
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_collection: str = "utterances"
    qdrant_api_key: Optional[str] = None
    
    # =========================================================================
    # Audio Processing Configuration
    # =========================================================================
    # Discord's native sample rate (don't change unless you know what you're doing)
    audio_sample_rate: int = 48000
    
    # Seconds to accumulate before transcribing (balance latency vs overhead)
    audio_chunk_duration: int = 5
    
    # Seconds of silence before considering an utterance complete
    audio_silence_threshold: float = 2.0
    
    # Minimum audio duration to transcribe (seconds)
    audio_min_duration: float = 0.5
    
    # =========================================================================
    # Session Management Configuration
    # =========================================================================
    # Seconds of inactivity before considering session ended
    session_timeout: int = 300
    
    # Enable automatic session cleanup
    session_auto_cleanup: bool = True
    
    # =========================================================================
    # Analysis Configuration
    # =========================================================================
    # Interaction window: utterances within N seconds are considered interactions
    analysis_interaction_window: int = 5
    
    # Maximum keywords to extract by default
    analysis_default_keyword_limit: int = 20
    
    # =========================================================================
    # Performance Configuration
    # =========================================================================
    # Number of worker threads for transcription
    transcription_workers: int = 2
    
    # Maximum concurrent transcriptions
    transcription_max_concurrent: int = 5
    
    # =========================================================================
    # Logging Configuration
    # =========================================================================
    log_level: str = "INFO"  # DEBUG, INFO, WARNING, ERROR, CRITICAL
    log_file: str = "bot.log"
    log_to_console: bool = True
    log_to_file: bool = True
    
    # =========================================================================
    # Feature Flags
    # =========================================================================
    # Enable/disable features
    feature_transcription: bool = True
    feature_message_logging: bool = True
    feature_session_tracking: bool = True
    
    # =========================================================================
    # Security Configuration
    # =========================================================================
    # Allowed user IDs (empty = all users allowed)
    allowed_user_ids: Optional[str] = None  # Comma-separated list
    
    # Allowed channel IDs (empty = all channels allowed)
    allowed_channel_ids: Optional[str] = None  # Comma-separated list
    
    # Admin user IDs who can use management commands
    admin_user_ids: Optional[str] = None  # Comma-separated list
    
    @property
    def allowed_users(self) -> set[int]:
        """Parse allowed user IDs from string."""
        if not self.allowed_user_ids:
            return set()
        return {int(uid.strip()) for uid in self.allowed_user_ids.split(',') if uid.strip()}
    
    @property
    def allowed_channels(self) -> set[int]:
        """Parse allowed channel IDs from string."""
        if not self.allowed_channel_ids:
            return set()
        return {int(cid.strip()) for cid in self.allowed_channel_ids.split(',') if cid.strip()}
    
    @property
    def admin_users(self) -> set[int]:
        """Parse admin user IDs from string."""
        if not self.admin_user_ids:
            return set()
        return {int(uid.strip()) for uid in self.admin_user_ids.split(',') if uid.strip()}
    
    def get_database_url(self) -> str:
        """
        Get database URL. If individual components are provided, construct URL.
        Otherwise use DATABASE_URL.
        """
        if all([self.db_host, self.db_user, self.db_password, self.db_name]):
            port = self.db_port or 5432
            return f"postgresql://{self.db_user}:{self.db_password}@{self.db_host}:{port}/{self.db_name}"
        return self.database_url


settings = Settings()
