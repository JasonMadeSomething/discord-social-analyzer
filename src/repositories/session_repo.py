from sqlalchemy.orm import Session, scoped_session
from sqlalchemy import select
from typing import Optional, List
from datetime import datetime
import uuid

from src.models.database import SessionModel, ParticipantModel, SessionStatus
from src.models.domain import Session as DomainSession, Participant, SessionStatus as DomainSessionStatus


class SessionRepository:
    """Repository for session-related database operations."""
    
    def __init__(self, session_factory: scoped_session):
        self.session_factory = session_factory
    
    @property
    def db(self) -> Session:
        """Get a fresh database session."""
        return self.session_factory()
    
    def create_session(
        self,
        channel_id: int,
        channel_name: str,
        guild_id: int
    ) -> str:
        """
        Create a new session.
        
        Returns:
            session_id: UUID of the created session
        """
        session_id = str(uuid.uuid4())
        session = SessionModel(
            session_id=session_id,
            channel_id=channel_id,
            channel_name=channel_name,
            guild_id=guild_id,
            started_at=datetime.utcnow(),
            status=SessionStatus.ACTIVE
        )
        self.db.add(session)
        self.db.commit()
        return session_id
    
    def end_session(self, session_id: str, status: SessionStatus = SessionStatus.ENDED) -> None:
        """Mark a session as ended."""
        session = self.db.query(SessionModel).filter(
            SessionModel.session_id == session_id
        ).first()
        
        if session:
            session.ended_at = datetime.utcnow()
            session.status = status
            self.db.commit()
    
    def get_active_session(self, channel_id: int) -> Optional[str]:
        """
        Get active session ID for a channel.
        
        Returns:
            session_id or None if no active session
        """
        session = self.db.query(SessionModel).filter(
            SessionModel.channel_id == channel_id,
            SessionModel.status == SessionStatus.ACTIVE
        ).first()
        
        return session.session_id if session else None
    
    def add_participant(
        self,
        session_id: str,
        user_id: int,
        username: str,
        display_name: str
    ) -> None:
        """Add a participant to a session."""
        participant = ParticipantModel(
            session_id=session_id,
            user_id=user_id,
            username=username,
            display_name=display_name,
            joined_at=datetime.utcnow()
        )
        self.db.add(participant)
        self.db.commit()
    
    def remove_participant(
        self,
        session_id: str,
        user_id: int
    ) -> None:
        """Mark a participant as having left the session."""
        participant = self.db.query(ParticipantModel).filter(
            ParticipantModel.session_id == session_id,
            ParticipantModel.user_id == user_id,
            ParticipantModel.left_at.is_(None)
        ).first()
        
        if participant:
            participant.left_at = datetime.utcnow()
            self.db.commit()
    
    def get_session(self, session_id: str) -> Optional[DomainSession]:
        """Get a session with all its participants."""
        session = self.db.query(SessionModel).filter(
            SessionModel.session_id == session_id
        ).first()
        
        if not session:
            return None
        
        participants = [
            Participant(
                user_id=p.user_id,
                username=p.username,
                display_name=p.display_name,
                joined_at=p.joined_at,
                left_at=p.left_at
            )
            for p in session.participants
        ]
        
        return DomainSession(
            session_id=session.session_id,
            channel_id=session.channel_id,
            channel_name=session.channel_name,
            guild_id=session.guild_id,
            started_at=session.started_at,
            ended_at=session.ended_at,
            status=DomainSessionStatus(session.status.value),
            participants=participants
        )
    
    def get_sessions_by_channel(
        self,
        channel_id: int,
        limit: int = 10
    ) -> List[DomainSession]:
        """Get recent sessions for a channel."""
        sessions = self.db.query(SessionModel).filter(
            SessionModel.channel_id == channel_id
        ).order_by(
            SessionModel.started_at.desc()
        ).limit(limit).all()
        
        return [self._to_domain(s) for s in sessions]
    
    def get_active_sessions(self) -> List[DomainSession]:
        """Get all currently active sessions."""
        sessions = self.db.query(SessionModel).filter(
            SessionModel.status == SessionStatus.ACTIVE
        ).all()
        
        return [self._to_domain(s) for s in sessions]
    
    def _to_domain(self, session: SessionModel) -> DomainSession:
        """Convert database model to domain model."""
        participants = [
            Participant(
                user_id=p.user_id,
                username=p.username,
                display_name=p.display_name,
                joined_at=p.joined_at,
                left_at=p.left_at
            )
            for p in session.participants
        ]
        
        return DomainSession(
            session_id=session.session_id,
            channel_id=session.channel_id,
            channel_name=session.channel_name,
            guild_id=session.guild_id,
            started_at=session.started_at,
            ended_at=session.ended_at,
            status=DomainSessionStatus(session.status.value),
            participants=participants
        )
