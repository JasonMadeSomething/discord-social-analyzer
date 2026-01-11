from typing import Dict, Optional, Set
from datetime import datetime, timedelta
from src.repositories.session_repo import SessionRepository
from src.models.database import SessionStatus
from src.config import settings
import logging
import asyncio

logger = logging.getLogger(__name__)


class SessionManager:
    """
    Manages voice channel sessions lifecycle.
    Tracks when users join/leave and determines when sessions should end.
    """
    
    def __init__(self, session_repo: SessionRepository):
        self.session_repo = session_repo
        self._active_sessions: Dict[int, str] = {}  # channel_id -> session_id
        self._last_activity: Dict[int, datetime] = {}  # channel_id -> last_activity_time
        self._session_participants: Dict[str, Set[int]] = {}  # session_id -> set of user_ids
        self._timeout_task: Optional[asyncio.Task] = None
    
    def start_session(
        self,
        channel_id: int,
        channel_name: str,
        guild_id: int
    ) -> str:
        """
        Start a new session for a channel.
        
        Returns:
            session_id: UUID of the new session
        """
        # Check if there's already an active session
        if channel_id in self._active_sessions:
            logger.warning(f"Session already active for channel {channel_id}")
            return self._active_sessions[channel_id]
        
        # Create new session
        session_id = self.session_repo.create_session(
            channel_id=channel_id,
            channel_name=channel_name,
            guild_id=guild_id
        )
        
        self._active_sessions[channel_id] = session_id
        self._last_activity[channel_id] = datetime.utcnow()
        self._session_participants[session_id] = set()
        
        logger.info(f"Started session {session_id} for channel {channel_name} ({channel_id})")
        return session_id
    
    def add_participant(
        self,
        channel_id: int,
        user_id: int,
        username: str,
        display_name: str
    ) -> Optional[str]:
        """
        Add a participant to a channel's session.
        Creates a new session if none exists.
        
        Returns:
            session_id or None if channel info not available
        """
        session_id = self._active_sessions.get(channel_id)
        
        if not session_id:
            logger.warning(f"No active session for channel {channel_id} when adding participant")
            return None
        
        # Add to session
        if user_id not in self._session_participants[session_id]:
            self.session_repo.add_participant(
                session_id=session_id,
                user_id=user_id,
                username=username,
                display_name=display_name
            )
            self._session_participants[session_id].add(user_id)
            logger.info(f"Added participant {username} ({user_id}) to session {session_id}")
        
        self._last_activity[channel_id] = datetime.utcnow()
        return session_id
    
    def remove_participant(
        self,
        channel_id: int,
        user_id: int
    ) -> Optional[str]:
        """
        Remove a participant from a channel's session.
        
        Returns:
            session_id or None if no active session
        """
        session_id = self._active_sessions.get(channel_id)
        
        if not session_id:
            return None
        
        if user_id in self._session_participants.get(session_id, set()):
            self.session_repo.remove_participant(
                session_id=session_id,
                user_id=user_id
            )
            self._session_participants[session_id].discard(user_id)
            logger.info(f"Removed participant {user_id} from session {session_id}")
        
        self._last_activity[channel_id] = datetime.utcnow()
        
        # Check if session should end (no participants left)
        if len(self._session_participants[session_id]) == 0:
            self._end_session(channel_id, SessionStatus.ENDED)
        
        return session_id
    
    def record_activity(self, channel_id: int) -> None:
        """Record activity in a channel (e.g., someone spoke)."""
        if channel_id in self._active_sessions:
            self._last_activity[channel_id] = datetime.utcnow()
    
    def get_active_session(self, channel_id: int) -> Optional[str]:
        """Get the active session ID for a channel."""
        return self._active_sessions.get(channel_id)
    
    def get_session_participants(self, session_id: str) -> Set[int]:
        """Get the set of participant user IDs for a session."""
        return self._session_participants.get(session_id, set()).copy()
    
    def end_session(self, channel_id: int) -> None:
        """Manually end a session."""
        self._end_session(channel_id, SessionStatus.ENDED)
    
    def _end_session(self, channel_id: int, status: SessionStatus) -> None:
        """Internal method to end a session."""
        session_id = self._active_sessions.get(channel_id)
        
        if not session_id:
            return
        
        # Mark session as ended
        self.session_repo.end_session(session_id, status)
        
        # Clean up tracking
        del self._active_sessions[channel_id]
        del self._last_activity[channel_id]
        del self._session_participants[session_id]
        
        logger.info(f"Ended session {session_id} with status {status.value}")
    
    async def start_timeout_monitor(self) -> None:
        """
        Start monitoring for idle sessions that should timeout.
        Runs continuously in the background.
        """
        if self._timeout_task:
            logger.warning("Timeout monitor already running")
            return
        
        self._timeout_task = asyncio.create_task(self._timeout_monitor_loop())
        logger.info("Started session timeout monitor")
    
    async def stop_timeout_monitor(self) -> None:
        """Stop the timeout monitor."""
        if self._timeout_task:
            self._timeout_task.cancel()
            try:
                await self._timeout_task
            except asyncio.CancelledError:
                pass
            self._timeout_task = None
            logger.info("Stopped session timeout monitor")
    
    async def _timeout_monitor_loop(self) -> None:
        """Monitor loop that checks for idle sessions."""
        timeout_seconds = settings.session_timeout
        
        while True:
            try:
                await asyncio.sleep(60)  # Check every minute
                
                now = datetime.utcnow()
                timeout_threshold = timedelta(seconds=timeout_seconds)
                
                # Find channels that have been idle too long
                channels_to_timeout = []
                for channel_id, last_activity in self._last_activity.items():
                    if now - last_activity > timeout_threshold:
                        channels_to_timeout.append(channel_id)
                
                # Timeout idle sessions
                for channel_id in channels_to_timeout:
                    logger.info(f"Timing out idle session for channel {channel_id}")
                    self._end_session(channel_id, SessionStatus.ABANDONED)
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in timeout monitor: {e}")
                await asyncio.sleep(60)
