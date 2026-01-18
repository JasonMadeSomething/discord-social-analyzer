"""Boundary detection service for creating ideas from utterances."""
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import logging

from src.repositories.idea_repo import IdeaRepository
from src.repositories.enrichment_queue_repo import EnrichmentQueueRepository
from src.config import settings

logger = logging.getLogger(__name__)


class BoundaryDetector:
    """Detects idea boundaries and creates ideas in Qdrant."""
    
    def __init__(
        self,
        idea_repo: IdeaRepository,
        queue_repo: EnrichmentQueueRepository,
        exchange_detector=None
    ):
        """
        Initialize boundary detector.
        
        Args:
            idea_repo: IdeaRepository instance
            queue_repo: EnrichmentQueueRepository instance
            exchange_detector: Optional ExchangeDetector instance
        """
        self.idea_repo = idea_repo
        self.queue_repo = queue_repo
        self.exchange_detector = exchange_detector
        
        # session_id -> {user_id -> [utterances]}
        self._pending_utterances: Dict[str, Dict[int, List]] = {}
    
    async def on_utterance_created(self, utterance) -> None:
        """
        Called after an utterance is saved to Postgres.
        Checks for idea boundaries and creates ideas.
        
        Args:
            utterance: UtteranceModel instance
        """
        session_id = utterance.session_id
        user_id = utterance.user_id
        
        logger.debug(f"BoundaryDetector: Processing utterance {utterance.id} (session={session_id}, user={user_id})")
        
        # Initialize structures
        if session_id not in self._pending_utterances:
            self._pending_utterances[session_id] = {}
            logger.debug(f"BoundaryDetector: Initialized session {session_id}")
        if user_id not in self._pending_utterances[session_id]:
            self._pending_utterances[session_id][user_id] = []
            logger.debug(f"BoundaryDetector: Initialized user {user_id} in session {session_id}")
        
        # Add to pending
        self._pending_utterances[session_id][user_id].append(utterance)
        pending_count = len(self._pending_utterances[session_id][user_id])
        logger.debug(f"BoundaryDetector: Added utterance, now {pending_count} pending for user {user_id}")
        
        # Check if boundary reached
        if await self._is_boundary(session_id, user_id, utterance):
            logger.info(f"BoundaryDetector: Boundary detected for user {user_id}, creating idea...")
            await self._create_idea(session_id, user_id)
        else:
            logger.debug(f"BoundaryDetector: No boundary yet, continuing to accumulate utterances")
    
    async def flush_session(self, session_id: str) -> None:
        """
        Flush all pending utterances for a session (called on session end).
        
        Args:
            session_id: Session ID to flush
        """
        if session_id not in self._pending_utterances:
            return
        
        # Create ideas for all pending utterances
        for user_id in list(self._pending_utterances[session_id].keys()):
            if self._pending_utterances[session_id][user_id]:
                await self._create_idea(session_id, user_id)
        
        # Clean up
        del self._pending_utterances[session_id]
        logger.info(f"Flushed all pending utterances for session {session_id}")
    
    async def _is_boundary(self, session_id: str, user_id: int, utterance) -> bool:
        """
        Check if current utterance marks an idea boundary.
        
        Args:
            session_id: Session ID
            user_id: User ID
            utterance: Current utterance
            
        Returns:
            True if boundary detected, False otherwise
        """
        pending = self._pending_utterances[session_id][user_id]
        
        if len(pending) == 0:
            return False
        
        # 1. Max duration threshold (ideas shouldn't be too long)
        duration = (utterance.ended_at - pending[0].started_at).total_seconds()
        if duration >= settings.idea_max_duration_sec:
            logger.debug(f"Boundary: max duration ({duration:.1f}s)")
            return True
        
        # 2. Reasonable duration threshold (most ideas are 5-20 seconds)
        # After 15 seconds, be more aggressive about creating boundaries
        if duration >= 15 and len(pending) >= 2:
            logger.debug(f"Boundary: reasonable duration ({duration:.1f}s) with {len(pending)} utterances")
            return True
        
        # 3. Multiple utterances - create idea after 3 utterances
        # This is the primary boundary condition for normal conversation
        if len(pending) >= 3:
            logger.debug(f"Boundary: multiple utterances ({len(pending)})")
            return True
        
        # Note: Speaker change and silence gaps are detected externally
        # by checking timing between consecutive utterances from different speakers
        
        return False
    
    async def check_speaker_change(
        self,
        session_id: str,
        new_user_id: int,
        new_utterance_time: datetime
    ) -> None:
        """
        Check if a speaker change creates a boundary for previous speaker.
        
        Args:
            session_id: Session ID
            new_user_id: New speaker's user ID
            new_utterance_time: Timestamp of new utterance
        """
        if session_id not in self._pending_utterances:
            return
        
        # Check all other speakers
        for user_id in list(self._pending_utterances[session_id].keys()):
            if user_id == new_user_id:
                continue
            
            pending = self._pending_utterances[session_id][user_id]
            if not pending:
                continue
            
            # Check silence gap
            last_utterance = pending[-1]
            gap_ms = (new_utterance_time - last_utterance.ended_at).total_seconds() * 1000
            
            if gap_ms >= settings.idea_boundary_silence_ms:
                logger.debug(f"Boundary: speaker change + silence gap ({gap_ms:.0f}ms)")
                await self._create_idea(session_id, user_id)
    
    async def _create_idea(self, session_id: str, user_id: int) -> Optional[str]:
        """
        Create an idea from pending utterances.
        
        Args:
            session_id: Session ID
            user_id: User ID
            
        Returns:
            Idea UUID if created, None otherwise
        """
        pending = self._pending_utterances[session_id][user_id]
        
        if not pending:
            return None
        
        try:
            # Combine text
            text = " ".join(u.text for u in pending)
            utterance_ids = [u.id for u in pending]
            started_at = pending[0].started_at
            ended_at = pending[-1].ended_at
            
            # Create idea in Qdrant
            idea_id = await self.idea_repo.create_idea(
                utterance_ids=utterance_ids,
                session_id=session_id,
                user_id=user_id,
                text=text,
                started_at=started_at,
                ended_at=ended_at
            )
            
            if idea_id:
                logger.info("=" * 80)
                logger.info(f"🧠 ENRICHMENT ENGINE: Created idea {idea_id}")
                logger.info(f"   Utterances: {len(utterance_ids)} combined")
                logger.info(f"   Text preview: {text[:100]}...")
                logger.info(f"   Session: {session_id}")
                logger.info(f"   User: {user_id}")
                logger.info("=" * 80)
                
                # Enqueue enrichment tasks
                task_types = ['alias_detection', 'prosody_interpretation', 
                             'response_mapping', 'intent_keywords']
                logger.info(f"📋 Enqueueing {len(task_types)} enrichment tasks for idea {idea_id}")
                for task_type in task_types:
                    task_id = self.queue_repo.enqueue(
                        target_type='idea',
                        target_id=idea_id,
                        task_type=task_type,
                        priority=2
                    )
                    if task_id:
                        logger.debug(f"   ✓ Queued: {task_type} (task_id={task_id})")
                    else:
                        logger.warning(f"   ✗ Failed to queue: {task_type}")
                
                # Clear pending
                self._pending_utterances[session_id][user_id] = []
                
                # Trigger exchange detection
                if self.exchange_detector:
                    await self.exchange_detector.on_idea_created(idea_id, session_id, user_id)
                
                return idea_id
            else:
                logger.error("Failed to create idea")
                return None
                
        except Exception as e:
            logger.error(f"Error creating idea: {e}", exc_info=True)
            return None
