import asyncio
import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
import sys

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

# Setup logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('bot.log')
    ]
)

logger = logging.getLogger(__name__)


class Application:
    """Main application that wires up all dependencies."""
    
    def __init__(self):
        self.engine = None
        self.Session = None
        self.bot = None
    
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
        
        # Repositories (pass session factory instead of single session)
        session_repo = SessionRepository(self.Session)
        utterance_repo = UtteranceRepository(self.Session)
        message_repo = MessageRepository(self.Session)
        
        # Services
        # Choose transcription provider:
        # Option 1: Whisper (slower, less accurate for real-time)
        # transcription_provider = WhisperProvider()
        
        # Option 2: Vosk (faster, better for real-time)
        # Requires: pip install vosk
        # Download model from: https://alphacephei.com/vosk/models
        from src.providers.vosk_provider import VoskProvider
        transcription_provider = VoskProvider()
        
        session_manager = SessionManager(session_repo)
        transcription_service = TranscriptionService(
            transcription_provider=transcription_provider,
            utterance_repo=utterance_repo,
            session_manager=session_manager
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
        
        # In Pycord, add_cog is not async
        bot.add_cog(commands_cog)
        bot.add_cog(advanced_commands_cog)
        
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
            
            # Run bot
            logger.info("Starting bot...")
            await bot.start(settings.discord_token)
            
        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt")
        except Exception as e:
            logger.error(f"Error running application: {e}", exc_info=True)
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
    logger.info("=" * 70)
    logger.info("Discord Social Analyzer Starting")
    logger.info("=" * 70)
    
    # Show configuration
    logger.info(f"Whisper Model: {settings.whisper_model}")
    logger.info(f"Whisper Device: {settings.whisper_device}")
    logger.info(f"Whisper Compute Type: {settings.whisper_compute_type}")
    logger.info(f"Whisper VAD Enabled: {settings.whisper_vad_enabled}")
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
    
    app = Application()
    
    try:
        asyncio.run(app.run())
    except KeyboardInterrupt:
        logger.info("Shutdown requested")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
