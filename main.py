import asyncio
import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
import sys
import argparse

from src.config import settings
from src.models.database import Base
from src.providers.whisper_provider import WhisperProvider
from src.repositories.session_repo import SessionRepository
from src.repositories.utterance_repo import UtteranceRepository
from src.repositories.message_repo import MessageRepository
from src.services.transcription import TranscriptionService
from src.services.session_manager import SessionManager
from src.services.analyzer import ConversationAnalyzer
from src.bot.client import DiscordBot
from src.bot.commands import AnalysisCommands
from src.bot.analysis_commands import AdvancedAnalysisCommands
from src.bot.advanced_commands import DeepAnalysisCommands

# Setup logging
# Configure logging with UTF-8 encoding for Windows compatibility
stream_handler = logging.StreamHandler(sys.stdout)
stream_handler.setLevel(getattr(logging, settings.log_level))
stream_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))

# Use UTF-8 encoding for file handler to support Unicode characters
file_handler = logging.FileHandler('bot.log', encoding='utf-8')
file_handler.setLevel(getattr(logging, settings.log_level))
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))

logging.basicConfig(
    level=getattr(logging, settings.log_level),
    handlers=[stream_handler, file_handler]
)

logger = logging.getLogger(__name__)


class Application:
    """Main application class."""
    
    def __init__(self, provider_choice: str = 'whisper'):
        self.bot = None
        self.provider_choice = provider_choice.lower()
        self.Session = None
        self.engine = None
    
    def setup_database(self):
        """Initialize database connection and create tables."""
        logger.info("Setting up database...")
        
        # Create engine
        db_url = settings.get_database_url()
        self.engine = create_engine(
            db_url,
            pool_pre_ping=True,
            echo=False
        )
        
        # Create tables
        Base.metadata.create_all(self.engine)
        
        # Create session factory
        self.Session = scoped_session(
            sessionmaker(bind=self.engine)
        )
        
        logger.info("Database setup complete")
    
    async def create_dependencies(self):
        """Create all dependencies with dependency injection."""
        logger.info("Creating dependencies...")
        
        # Ollama client for enrichment engine
        from src.services.ollama_client import OllamaClient
        ollama_client = OllamaClient()
        
        # Qdrant client for analysis layer
        from qdrant_client import QdrantClient
        qdrant_client = QdrantClient(
            host=settings.qdrant_host,
            port=settings.qdrant_port
        )
        
        # Enrichment repositories
        from src.repositories.speaker_alias_repo import SpeakerAliasRepository
        from src.repositories.enrichment_queue_repo import EnrichmentQueueRepository
        from src.repositories.idea_repo import IdeaRepository
        from src.repositories.exchange_repo import ExchangeRepository
        
        speaker_alias_repo = SpeakerAliasRepository(self.Session)
        enrichment_queue_repo = EnrichmentQueueRepository(self.Session)
        idea_repo = IdeaRepository(qdrant_client, ollama_client)
        exchange_repo = ExchangeRepository(qdrant_client, ollama_client)
        
        # Boundary detector and model manager
        from src.services.boundary_detector import BoundaryDetector
        from src.services.enrichment.model_manager import ModelManager
        
        boundary_detector = BoundaryDetector(idea_repo, enrichment_queue_repo)
        model_manager = ModelManager(ollama_client)
        
        # Repositories (pass session factory instead of single session)
        session_repo = SessionRepository(self.Session)
        utterance_repo = UtteranceRepository(
            self.Session,
            speaker_alias_repo=speaker_alias_repo,
            boundary_detector=boundary_detector
        )
        message_repo = MessageRepository(self.Session)
        
        # Services
        # Dynamically select transcription provider based on environment variable or startup argument
        import os
        use_vosk = os.getenv('USE_VOSK', '').lower() in ('true', '1', 'yes')
        
        # Allow command-line argument to override environment variable
        if self.provider_choice == 'vosk':
            use_vosk = True
        elif self.provider_choice == 'whisper':
            use_vosk = False
        
        if use_vosk:
            from src.providers.vosk_provider import VoskProvider
            transcription_provider = VoskProvider()
            logger.info("Using Vosk transcription provider")
        else:
            transcription_provider = WhisperProvider()
            logger.info("Using Whisper transcription provider")
        
        # Vector database (Qdrant) for semantic search
        vector_service = None
        if settings.qdrant_enabled:
            logger.info("Initializing vector database...")
            try:
                from src.providers.qdrant_provider import QdrantProvider
                from src.providers.embedding_provider import SentenceTransformersProvider
                from src.services.vector_service import VectorService
                
                embedding_provider = SentenceTransformersProvider()
                vector_store = QdrantProvider(
                    collection_name=settings.qdrant_collection,
                    vector_size=embedding_provider.dimension
                )
                vector_service = VectorService(
                    vector_store=vector_store,
                    embedding_provider=embedding_provider
                )
                logger.info("Vector database initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize vector database: {e}", exc_info=True)
                logger.warning("Continuing without vector database features")
                vector_service = None
        else:
            logger.info("Vector database disabled (set QDRANT_ENABLED=true to enable)")
        
        session_manager = SessionManager(session_repo)
        transcription_service = TranscriptionService(
            transcription_provider=transcription_provider,
            utterance_repo=utterance_repo,
            session_manager=session_manager,
            vector_service=vector_service
        )
        
        # Analyzer service
        analyzer = ConversationAnalyzer(
            session_repo=session_repo,
            utterance_repo=utterance_repo,
            message_repo=message_repo
        )
        
        # Bot
        try:
            bot = DiscordBot(
                transcription_service=transcription_service,
                session_manager=session_manager,
                message_repo=message_repo
            )
            logger.info(f"Bot created successfully: {bot}")
        except Exception as e:
            logger.error(f"Failed to create bot: {e}", exc_info=True)
            raise
        
        # Add commands
        commands_cog = AnalysisCommands(
            bot=bot,
            session_repo=session_repo,
            utterance_repo=utterance_repo,
            message_repo=message_repo
        )
        
        advanced_commands_cog = AdvancedAnalysisCommands(
            bot=bot,
            analyzer=analyzer,
            session_repo=session_repo
        )
        
        deep_analysis_cog = DeepAnalysisCommands(
            bot=bot,
            analyzer=analyzer,
            session_repo=session_repo
        )
        
        # In Pycord, add_cog is not async
        bot.add_cog(commands_cog)
        bot.add_cog(advanced_commands_cog)
        bot.add_cog(deep_analysis_cog)
        
        # Add voice control commands
        from src.bot.voice_commands import VoiceCommands
        voice_commands_cog = VoiceCommands(bot=bot)
        bot.add_cog(voice_commands_cog)
        logger.info("Voice control commands enabled")
        
        # Add semantic search commands (if vector service is enabled)
        if vector_service:
            from src.bot.semantic_commands import SemanticCommands
            semantic_commands_cog = SemanticCommands(
                bot=bot,
                vector_service=vector_service,
                utterance_repo=utterance_repo,
                session_repo=session_repo
            )
            bot.add_cog(semantic_commands_cog)
            logger.info("Semantic commands enabled")
        
        # Add alias commands for enrichment engine
        from src.bot.alias_commands import AliasCommands
        alias_commands_cog = AliasCommands(
            bot=bot,
            speaker_alias_repo=speaker_alias_repo
        )
        bot.add_cog(alias_commands_cog)
        logger.info("Alias commands enabled")
        
        # Add diagnostic commands for enrichment engine
        from src.bot.diagnostic_commands import DiagnosticCommands
        diagnostic_commands_cog = DiagnosticCommands(
            bot=bot,
            idea_repo=idea_repo,
            exchange_repo=exchange_repo,
            enrichment_queue_repo=enrichment_queue_repo,
            speaker_alias_repo=speaker_alias_repo,
            session_repo=session_repo
        )
        bot.add_cog(diagnostic_commands_cog)
        logger.info("Diagnostic commands enabled")
        
        # Task handlers for enrichment engine
        from src.services.enrichment.handlers.alias_detection import AliasDetectionHandler
        from src.services.enrichment.handlers.prosody_interpretation import ProsodyInterpretationHandler
        from src.services.enrichment.handlers.response_mapping import ResponseMappingHandler
        from src.services.enrichment.handlers.intent_keywords import IntentKeywordsHandler
        
        handlers = [
            AliasDetectionHandler(speaker_alias_repo, idea_repo),
            ProsodyInterpretationHandler(idea_repo, utterance_repo),
            ResponseMappingHandler(idea_repo),
            IntentKeywordsHandler(idea_repo, ollama_client)
        ]
        
        # Enrichment worker
        from src.services.enrichment.worker import EnrichmentWorker
        worker = EnrichmentWorker(
            queue_repo=enrichment_queue_repo,
            handlers=handlers,
            model_manager=model_manager,
            idea_repo=idea_repo,
            exchange_repo=exchange_repo
        )
        
        # Store worker for later initialization
        self.enrichment_worker = worker
        self.idea_repo = idea_repo
        self.exchange_repo = exchange_repo
        
        self.bot = bot
        
        logger.info("Dependencies created")
        return bot
    
    async def run(self):
        """Run the application."""
        try:
            # Setup database
            self.setup_database()
            
            # Create dependencies
            bot = await self.create_dependencies()
            
            # Initialize Qdrant collections
            logger.info("Initializing Qdrant collections...")
            await self.idea_repo.initialize_collection()
            await self.exchange_repo.initialize_collection()
            logger.info("Qdrant collections initialized")
            
            # Start enrichment worker
            if settings.enrichment_worker_enabled:
                asyncio.create_task(self.enrichment_worker.start())
                logger.info("Enrichment worker started")
            else:
                logger.info("Enrichment worker disabled (set ENRICHMENT_WORKER_ENABLED=true to enable)")
            
            # Run bot
            logger.info("Starting bot...")
            try:
                await bot.start(settings.discord_token)
            except Exception as bot_error:
                logger.error(f"Bot failed to start: {bot_error}", exc_info=True)
                raise
            
        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt")
        except Exception as e:
            logger.error(f"Error running application: {e}", exc_info=True)
            raise
        finally:
            # Cleanup
            if self.bot:
                await self.bot.close()
            
            if self.Session:
                self.Session.remove()
            
            if self.engine:
                self.engine.dispose()
            
            logger.info("Application shutdown complete")


def main():
    """Main entry point."""
    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description='Discord Social Analyzer - Transcribe and analyze voice conversations',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Transcription Providers:
  whisper  - OpenAI Whisper (high accuracy, slower, GPU recommended)
  vosk     - Vosk (fast, CPU-friendly, good for real-time)

Examples:
  python main.py --provider whisper
  python main.py --provider vosk
  python main.py  (defaults to whisper)
        """
    )
    parser.add_argument(
        '--provider',
        type=str,
        choices=['whisper', 'vosk'],
        default='whisper',
        help='Transcription provider to use (default: whisper)'
    )
    
    args = parser.parse_args()
    
    logger.info("=" * 70)
    logger.info("Discord Social Analyzer Starting")
    logger.info("=" * 70)
    logger.info(f"Transcription Provider: {args.provider.upper()}")
    
    # Show configuration
    if args.provider == 'whisper':
        logger.info(f"Whisper Model: {settings.whisper_model}")
        logger.info(f"Whisper Device: {settings.whisper_device}")
        logger.info(f"Whisper Compute Type: {settings.whisper_compute_type}")
        logger.info(f"Whisper VAD Enabled: {settings.whisper_vad_enabled}")
    else:
        logger.info(f"Vosk Model Path: {settings.vosk_model_path}")
    logger.info(f"Database: {settings.get_database_url().split('@')[1] if '@' in settings.get_database_url() else settings.get_database_url()}")
    logger.info(f"Audio Chunk Duration: {settings.audio_chunk_duration}s")
    logger.info(f"Session Timeout: {settings.session_timeout}s")
    logger.info(f"Log Level: {settings.log_level}")
    logger.info(f"Command Prefix: {settings.command_prefix}")
    
    # Feature flags
    logger.info("Features:")
    logger.info(f"  - Transcription: {settings.feature_transcription}")
    logger.info(f"  - Message Logging: {settings.feature_message_logging}")
    logger.info(f"  - Session Tracking: {settings.feature_session_tracking}")
    
    # Security
    if settings.allowed_users:
        logger.info(f"Restricted to {len(settings.allowed_users)} allowed users")
    if settings.allowed_channels:
        logger.info(f"Restricted to {len(settings.allowed_channels)} allowed channels")
    if settings.admin_users:
        logger.info(f"{len(settings.admin_users)} admin user(s) configured")
    
    logger.info("=" * 70)
    
    app = Application(provider_choice=args.provider)
    
    try:
        asyncio.run(app.run())
    except KeyboardInterrupt:
        logger.info("Shutdown requested")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
