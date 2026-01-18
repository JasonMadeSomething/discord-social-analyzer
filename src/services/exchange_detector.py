"""Exchange detector for grouping related ideas into conversational exchanges."""
import logging
from typing import List, Optional, Dict
from datetime import datetime, timedelta
from collections import defaultdict

from src.repositories.idea_repo import IdeaRepository
from src.repositories.exchange_repo import ExchangeRepository
from src.repositories.enrichment_queue_repo import EnrichmentQueueRepository
from src.config import settings

logger = logging.getLogger(__name__)


class ExchangeDetector:
    """
    Detects and creates exchanges from related ideas.
    
    An exchange is a group of ideas that form a conversational unit:
    - Temporal: Ideas from same speaker within a short time window (join)
    - Semantic: Ideas from different speakers that respond to each other (relate)
    """
    
    def __init__(
        self,
        idea_repo: IdeaRepository,
        exchange_repo: ExchangeRepository,
        queue_repo: EnrichmentQueueRepository
    ):
        self.idea_repo = idea_repo
        self.exchange_repo = exchange_repo
        self.queue_repo = queue_repo
        
        # Track pending ideas per session for exchange detection
        self._pending_ideas: Dict[str, List] = defaultdict(list)
    
    async def on_idea_created(self, idea_id: str, session_id: str, user_id: int) -> None:
        """
        Called when a new idea is created.
        Checks if it should be joined/related to form an exchange.
        
        Args:
            idea_id: Idea UUID
            session_id: Session ID
            user_id: User ID
        """
        try:
            # Get the idea
            idea = await self.idea_repo.get_idea(idea_id)
            if not idea:
                logger.warning(f"Idea {idea_id} not found for exchange detection")
                return
            
            # Add to pending
            self._pending_ideas[session_id].append({
                'id': idea_id,
                'user_id': user_id,
                'started_at': idea.started_at,
                'ended_at': idea.ended_at,
                'text': idea.text
            })
            
            # Check for temporal joins (same speaker, short gap)
            await self._check_temporal_join(session_id, user_id)
            
            # Check for semantic relations (different speakers, conversational flow)
            await self._check_semantic_relation(session_id, user_id)
            
        except Exception as e:
            logger.error(f"Error in exchange detection for idea {idea_id}: {e}", exc_info=True)
    
    async def _check_temporal_join(self, session_id: str, user_id: int) -> None:
        """
        Check if recent ideas from same speaker should be joined into an exchange.
        
        Temporal join criteria:
        - Same speaker
        - Gap < 5 seconds between ideas
        - Total duration < 30 seconds
        """
        pending = self._pending_ideas[session_id]
        
        # Get ideas from this user
        user_ideas = [i for i in pending if i['user_id'] == user_id]
        
        if len(user_ideas) < 2:
            return
        
        # Check if last 2+ ideas should be joined
        recent_ideas = sorted(user_ideas[-3:], key=lambda x: x['started_at'])
        
        if len(recent_ideas) < 2:
            return
        
        # Check temporal proximity
        first_idea = recent_ideas[0]
        last_idea = recent_ideas[-1]
        
        # Gap between ideas
        max_gap = timedelta(seconds=5)
        for i in range(len(recent_ideas) - 1):
            gap = recent_ideas[i + 1]['started_at'] - recent_ideas[i]['ended_at']
            if gap > max_gap:
                return  # Gap too large, don't join
        
        # Total duration
        total_duration = (last_idea['ended_at'] - first_idea['started_at']).total_seconds()
        if total_duration > 30:
            return  # Too long to be a single exchange
        
        # Create exchange (temporal join)
        logger.info(f"Temporal join detected: {len(recent_ideas)} ideas from user {user_id}")
        await self._create_exchange(
            session_id=session_id,
            ideas=recent_ideas,
            exchange_type='temporal_join'
        )
    
    async def _check_semantic_relation(self, session_id: str, user_id: int) -> None:
        """
        Check if ideas from different speakers should be related into an exchange.
        
        Semantic relation criteria:
        - Different speakers
        - Response within 10 seconds
        - Conversational flow (A speaks, B responds, A responds, etc.)
        """
        pending = self._pending_ideas[session_id]
        
        if len(pending) < 2:
            return
        
        # Get last few ideas
        recent_ideas = sorted(pending[-5:], key=lambda x: x['started_at'])
        
        # Check for conversational pattern (alternating speakers or quick responses)
        exchange_candidates = []
        current_exchange = [recent_ideas[0]]
        
        for i in range(1, len(recent_ideas)):
            prev_idea = recent_ideas[i - 1]
            curr_idea = recent_ideas[i]
            
            # Time gap between ideas
            gap = (curr_idea['started_at'] - prev_idea['ended_at']).total_seconds()
            
            # If quick response (< 10 seconds), likely part of exchange
            if gap < 10:
                current_exchange.append(curr_idea)
            else:
                # Gap too large, start new potential exchange
                if len(current_exchange) >= 2:
                    exchange_candidates.append(current_exchange)
                current_exchange = [curr_idea]
        
        # Check final exchange
        if len(current_exchange) >= 2:
            exchange_candidates.append(current_exchange)
        
        # Create exchanges for multi-speaker interactions
        for exchange_ideas in exchange_candidates:
            # Check if multiple speakers
            speakers = set(i['user_id'] for i in exchange_ideas)
            if len(speakers) >= 2:
                logger.info(f"Semantic relation detected: {len(exchange_ideas)} ideas from {len(speakers)} speakers")
                await self._create_exchange(
                    session_id=session_id,
                    ideas=exchange_ideas,
                    exchange_type='semantic_relation'
                )
    
    async def _create_exchange(
        self,
        session_id: str,
        ideas: List[Dict],
        exchange_type: str
    ) -> Optional[str]:
        """
        Create an exchange from a group of ideas.
        
        Args:
            session_id: Session ID
            ideas: List of idea dicts
            exchange_type: 'temporal_join' or 'semantic_relation'
            
        Returns:
            Exchange UUID if created, None otherwise
        """
        try:
            idea_ids = [i['id'] for i in ideas]
            participant_user_ids = list(set(i['user_id'] for i in ideas))
            combined_text = " ".join(i['text'] for i in ideas)
            started_at = min(i['started_at'] for i in ideas)
            ended_at = max(i['ended_at'] for i in ideas)
            
            exchange_id = await self.exchange_repo.create_exchange(
                idea_ids=idea_ids,
                session_id=session_id,
                participant_user_ids=participant_user_ids,
                combined_text=combined_text,
                started_at=started_at,
                ended_at=ended_at
            )
            
            if exchange_id:
                logger.info("=" * 80)
                logger.info(f"💬 EXCHANGE CREATED: {exchange_id} ({exchange_type})")
                logger.info(f"   Ideas: {len(idea_ids)} combined")
                logger.info(f"   Participants: {len(participant_user_ids)} speakers")
                logger.info(f"   Duration: {(ended_at - started_at).total_seconds():.1f}s")
                logger.info("=" * 80)
                
                # Enqueue exchange enrichment tasks
                # (e.g., topic extraction, sentiment analysis, turn-taking analysis)
                self.queue_repo.enqueue(
                    target_type='exchange',
                    target_id=exchange_id,
                    task_type='topic_extraction',
                    priority=2
                )
                
                # Remove processed ideas from pending
                idea_id_set = set(idea_ids)
                self._pending_ideas[session_id] = [
                    i for i in self._pending_ideas[session_id]
                    if i['id'] not in idea_id_set
                ]
                
                return exchange_id
            
        except Exception as e:
            logger.error(f"Failed to create exchange: {e}", exc_info=True)
            return None
    
    async def flush_session(self, session_id: str) -> None:
        """
        Flush pending ideas for a session (called on session end).
        Creates exchanges from any remaining ideas.
        
        Args:
            session_id: Session ID to flush
        """
        if session_id not in self._pending_ideas:
            return
        
        pending = self._pending_ideas[session_id]
        
        if len(pending) >= 2:
            logger.info(f"Flushing {len(pending)} pending ideas for session {session_id}")
            await self._create_exchange(
                session_id=session_id,
                ideas=pending,
                exchange_type='session_end'
            )
        
        # Clear pending
        del self._pending_ideas[session_id]
