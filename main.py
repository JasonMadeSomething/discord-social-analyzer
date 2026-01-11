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
from src.bot.client import DiscordBot
from src.bot.commands import AnalysisCommands

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
        self.engine = create_engine(
            settings.database_url,
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
    
    def create_dependencies(self):
        """Create all dependencies with dependency injection."""
        logger.info("Creating dependencies...")
        
        # Database session
        db_session = self.Session()
        
        # Repositories
        session_repo = SessionRepository(db_session)
        utterance_repo = UtteranceRepository(db_session)
        message_repo = MessageRepository(db_session)
        
        # Services
        transcription_provider = WhisperProvider()
        session_manager = SessionManager(session_repo)
        transcription_service = TranscriptionService(
            transcription_provider=transcription_provider,
            utterance_repo=utterance_repo,
            session_manager=session_manager
        )
        
        # Bot
        bot = DiscordBot(
            transcription_service=transcription_service,
            session_manager=session_manager,
            message_repo=message_repo
        )
        
        # Add commands
        commands_cog = AnalysisCommands(
            bot=bot,
            session_repo=session_repo,
            utterance_repo=utterance_repo,
            message_repo=message_repo
        )
        
        asyncio.get_event_loop().run_until_complete(
            bot.add_cog(commands_cog)
        )
        
        self.bot = bot
        
        logger.info("Dependencies created")
        return bot
    
    async def run(self):
        """Run the application."""
        try:
            # Setup database
            self.setup_database()
            
            # Create dependencies
            bot = self.create_dependencies()
            
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
    logger.info("=== Discord Social Analyzer Starting ===")
    logger.info(f"Model: {settings.whisper_model}")
    logger.info(f"Device: {settings.whisper_device}")
    logger.info(f"Database: {settings.database_url}")
    
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
