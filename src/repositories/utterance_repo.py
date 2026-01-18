from sqlalchemy.orm import Session, scoped_session
from typing import List, Optional
from datetime import datetime
import logging

from src.models.database import UtteranceModel
from src.models.domain import Utterance

logger = logging.getLogger(__name__)


class UtteranceRepository:
    """Repository for utterance-related database operations."""
    
    def __init__(self, session_factory: scoped_session, speaker_alias_repo=None, boundary_detector=None):
        self.session_factory = session_factory
        self.speaker_alias_repo = speaker_alias_repo
        self.boundary_detector = boundary_detector
    
    @property
    def db(self) -> Session:
        """Get a fresh database session."""
        return self.session_factory()
    
    def create_utterance(
        self,
        session_id: str,
        user_id: int,
        username: str,
        display_name: str,
        text: str,
        started_at: datetime,
        ended_at: datetime,
        confidence: float,
        audio_duration: float,
        prosody: Optional[dict] = None
    ) -> int:
        """
        Create a new utterance.
        
        Returns:
            utterance_id: ID of the created utterance
        """
        logger.debug(f"Creating utterance for session {session_id}, user {username} ({user_id})")
        logger.debug(f"Text: \"{text[:100]}...\" Duration: {audio_duration:.2f}s Confidence: {confidence:.2f}")
        
        try:
            # Calculate sequence_num
            sequence_num = self._get_next_sequence_num(session_id)
            
            utterance = UtteranceModel(
                session_id=session_id,
                user_id=user_id,
                username=username,
                display_name=display_name,
                text=text,
                started_at=started_at,
                ended_at=ended_at,
                confidence=confidence,
                audio_duration=audio_duration,
                sequence_num=sequence_num,
                prosody=prosody
            )
            self.db.add(utterance)
            self.db.commit()
            self.db.refresh(utterance)
            logger.info(f"Successfully created utterance #{utterance.id} for user {username} ({user_id})")
            
            # Auto-seed speaker aliases
            if self.speaker_alias_repo:
                self.speaker_alias_repo.auto_seed_from_utterance(
                    user_id, username, display_name
                )
            
            # Trigger boundary detection (async) - schedule for later execution
            if self.boundary_detector:
                import asyncio
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        logger.debug(f"Triggering boundary detection for utterance {utterance.id}")
                        # Check for speaker change boundary
                        asyncio.create_task(
                            self.boundary_detector.check_speaker_change(
                                session_id, user_id, started_at
                            )
                        )
                        # Process current utterance
                        asyncio.create_task(
                            self.boundary_detector.on_utterance_created(utterance)
                        )
                    else:
                        logger.warning("Event loop exists but not running, skipping boundary detection")
                except RuntimeError as e:
                    # No event loop running, skip boundary detection
                    logger.warning(f"No event loop running, skipping boundary detection: {e}")
            else:
                logger.warning("Boundary detector not initialized!")
            
            return utterance.id
        except Exception as e:
            logger.error(f"Failed to create utterance: {e}", exc_info=True)
            raise
    
    def get_utterances_by_session(
        self,
        session_id: str,
        limit: Optional[int] = None
    ) -> List[Utterance]:
        """Get all utterances for a session, ordered by time."""
        query = self.db.query(UtteranceModel).filter(
            UtteranceModel.session_id == session_id
        ).order_by(UtteranceModel.started_at)
        
        if limit:
            query = query.limit(limit)
        
        utterances = query.all()
        return [self._to_domain(u) for u in utterances]
    
    def get_utterances_by_user(
        self,
        user_id: int,
        session_id: Optional[str] = None,
        limit: int = 100
    ) -> List[Utterance]:
        """Get utterances by a specific user."""
        query = self.db.query(UtteranceModel).filter(
            UtteranceModel.user_id == user_id
        )
        
        if session_id:
            query = query.filter(UtteranceModel.session_id == session_id)
        
        utterances = query.order_by(
            UtteranceModel.started_at.desc()
        ).limit(limit).all()
        
        return [self._to_domain(u) for u in utterances]
    
    def get_utterances_in_timerange(
        self,
        start_time: datetime,
        end_time: datetime,
        session_id: Optional[str] = None
    ) -> List[Utterance]:
        """Get utterances within a time range."""
        query = self.db.query(UtteranceModel).filter(
            UtteranceModel.started_at >= start_time,
            UtteranceModel.ended_at <= end_time
        )
        
        if session_id:
            query = query.filter(UtteranceModel.session_id == session_id)
        
        utterances = query.order_by(UtteranceModel.started_at).all()
        return [self._to_domain(u) for u in utterances]
    
    def search_utterances(
        self,
        text_query: str,
        session_id: Optional[str] = None,
        user_id: Optional[int] = None,
        limit: int = 50
    ) -> List[Utterance]:
        """Search utterances by text content."""
        query = self.db.query(UtteranceModel).filter(
            UtteranceModel.text.ilike(f"%{text_query}%")
        )
        
        if session_id:
            query = query.filter(UtteranceModel.session_id == session_id)
        
        if user_id:
            query = query.filter(UtteranceModel.user_id == user_id)
        
        utterances = query.order_by(
            UtteranceModel.started_at.desc()
        ).limit(limit).all()
        
        return [self._to_domain(u) for u in utterances]
    
    def get_conversation_stats(self, session_id: str) -> dict:
        """Get statistics about a conversation."""
        from sqlalchemy import func
        
        stats = self.db.query(
            UtteranceModel.user_id,
            UtteranceModel.username,
            func.count(UtteranceModel.id).label('utterance_count'),
            func.sum(UtteranceModel.audio_duration).label('total_speaking_time'),
            func.avg(UtteranceModel.confidence).label('avg_confidence')
        ).filter(
            UtteranceModel.session_id == session_id
        ).group_by(
            UtteranceModel.user_id,
            UtteranceModel.username
        ).all()
        
        return [
            {
                'user_id': s.user_id,
                'username': s.username,
                'utterance_count': s.utterance_count,
                'total_speaking_time': float(s.total_speaking_time or 0),
                'avg_confidence': float(s.avg_confidence or 0)
            }
            for s in stats
        ]
    
    def get_utterance_by_id(self, utterance_id: int):
        """
        Get utterance by ID.
        
        Args:
            utterance_id: Utterance ID
            
        Returns:
            UtteranceModel if found, None otherwise
        """
        return self.db.query(UtteranceModel).filter(
            UtteranceModel.id == utterance_id
        ).first()
    
    def _get_next_sequence_num(self, session_id: str) -> int:
        """
        Get next sequence number for session.
        
        Args:
            session_id: Session ID
            
        Returns:
            Next sequence number (1-based)
        """
        from sqlalchemy import func
        max_seq = self.db.query(func.max(UtteranceModel.sequence_num)).filter(
            UtteranceModel.session_id == session_id
        ).scalar()
        return (max_seq or 0) + 1
    
    def _to_domain(self, utterance: UtteranceModel) -> Utterance:
        """Convert database model to domain model."""
        return Utterance(
            utterance_id=utterance.id,
            session_id=utterance.session_id,
            user_id=utterance.user_id,
            username=utterance.username,
            display_name=utterance.display_name,
            text=utterance.text,
            started_at=utterance.started_at,
            ended_at=utterance.ended_at,
            confidence=utterance.confidence,
            audio_duration=utterance.audio_duration
        )
