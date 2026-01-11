from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime

from src.models.database import UtteranceModel
from src.models.domain import Utterance


class UtteranceRepository:
    """Repository for utterance-related database operations."""
    
    def __init__(self, db_session: Session):
        self.db = db_session
    
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
        audio_duration: float
    ) -> int:
        """
        Create a new utterance.
        
        Returns:
            utterance_id: ID of the created utterance
        """
        utterance = UtteranceModel(
            session_id=session_id,
            user_id=user_id,
            username=username,
            display_name=display_name,
            text=text,
            started_at=started_at,
            ended_at=ended_at,
            confidence=confidence,
            audio_duration=audio_duration
        )
        self.db.add(utterance)
        self.db.commit()
        self.db.refresh(utterance)
        return utterance.id
    
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
