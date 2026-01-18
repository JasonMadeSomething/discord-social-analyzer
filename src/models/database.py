from sqlalchemy import (
    Column, Integer, String, Float, DateTime, ForeignKey, 
    BigInteger, Text, Index, Enum as SQLEnum, Boolean
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
import uuid

Base = declarative_base()


class SessionStatus(enum.Enum):
    """Session lifecycle states."""
    ACTIVE = "active"
    ENDED = "ended"
    ABANDONED = "abandoned"


class SessionModel(Base):
    """Voice channel session."""
    __tablename__ = "sessions"
    
    session_id = Column(String(36), primary_key=True)
    channel_id = Column(BigInteger, nullable=False, index=True)
    channel_name = Column(String(100), nullable=False)
    guild_id = Column(BigInteger, nullable=False, index=True)
    started_at = Column(DateTime, nullable=False, index=True)
    ended_at = Column(DateTime, nullable=True)
    status = Column(SQLEnum(SessionStatus), nullable=False, default=SessionStatus.ACTIVE)
    
    # Relationships
    participants = relationship("ParticipantModel", back_populates="session", cascade="all, delete-orphan")
    utterances = relationship("UtteranceModel", back_populates="session", cascade="all, delete-orphan")
    messages = relationship("MessageModel", back_populates="session")
    
    __table_args__ = (
        Index('idx_session_time', 'started_at', 'ended_at'),
        Index('idx_session_status', 'status', 'channel_id'),
    )


class ParticipantModel(Base):
    """Participant in a voice session."""
    __tablename__ = "participants"
    
    id = Column(Integer, primary_key=True)
    session_id = Column(String(36), ForeignKey("sessions.session_id"), nullable=False)
    user_id = Column(BigInteger, nullable=False, index=True)
    username = Column(String(100), nullable=False)
    display_name = Column(String(100), nullable=False)
    joined_at = Column(DateTime, nullable=False)
    left_at = Column(DateTime, nullable=True)
    
    # Relationships
    session = relationship("SessionModel", back_populates="participants")
    
    __table_args__ = (
        Index('idx_participant_user', 'user_id', 'session_id'),
        Index('idx_participant_time', 'joined_at', 'left_at'),
    )


class UtteranceModel(Base):
    """Speech utterance with transcription."""
    __tablename__ = "utterances"
    
    id = Column(Integer, primary_key=True)
    session_id = Column(String(36), ForeignKey("sessions.session_id"), nullable=False, index=True)
    user_id = Column(BigInteger, nullable=False, index=True)
    username = Column(String(100), nullable=False)
    display_name = Column(String(100), nullable=False)
    text = Column(Text, nullable=False)
    started_at = Column(DateTime, nullable=False, index=True)
    ended_at = Column(DateTime, nullable=False)
    confidence = Column(Float, nullable=False)
    audio_duration = Column(Float, nullable=False)  # seconds
    sequence_num = Column(Integer, nullable=False)  # Sequential order within session
    prosody = Column(JSONB, nullable=True)  # Prosodic features extracted from audio
    
    # Relationships
    session = relationship("SessionModel", back_populates="utterances")
    
    __table_args__ = (
        Index('idx_utterance_user_time', 'user_id', 'started_at'),
        Index('idx_utterance_session_time', 'session_id', 'started_at'),
        Index('idx_utterances_prosody', 'prosody', postgresql_using='gin'),
    )


class MessageModel(Base):
    """Text chat message."""
    __tablename__ = "messages"
    
    message_id = Column(BigInteger, primary_key=True)
    channel_id = Column(BigInteger, nullable=False, index=True)
    user_id = Column(BigInteger, nullable=False, index=True)
    username = Column(String(100), nullable=False)
    display_name = Column(String(100), nullable=False)
    content = Column(Text, nullable=False)
    timestamp = Column(DateTime, nullable=False, index=True)
    session_id = Column(String(36), ForeignKey("sessions.session_id"), nullable=True, index=True)
    reply_to_message_id = Column(BigInteger, nullable=True)
    
    # Relationships
    session = relationship("SessionModel", back_populates="messages")
    
    __table_args__ = (
        Index('idx_message_channel_time', 'channel_id', 'timestamp'),
        Index('idx_message_user_time', 'user_id', 'timestamp'),
    )


class SpeakerAliasModel(Base):
    """Speaker alias mapping (reference data)."""
    __tablename__ = "speaker_aliases"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(BigInteger, nullable=False, index=True)
    alias = Column(Text, nullable=False)
    alias_type = Column(String(20), nullable=False)  # username, display_name, nickname, mention
    confidence = Column(Float, default=1.0)
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(BigInteger, nullable=True)
    
    __table_args__ = (
        Index('idx_speaker_aliases_user_id', 'user_id'),
        Index('idx_speaker_aliases_alias', 'alias'),
    )


class EnrichmentQueueModel(Base):
    """Enrichment task queue (operational)."""
    __tablename__ = "enrichment_queue"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    target_type = Column(String(20), nullable=False)  # idea, exchange, session
    target_id = Column(Text, nullable=False)
    task_type = Column(String(50), nullable=False)
    priority = Column(Integer, nullable=False, default=2)
    status = Column(String(20), nullable=False, default='pending')
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    attempts = Column(Integer, default=0)
    error = Column(Text, nullable=True)
    
    __table_args__ = (
        Index('idx_enrichment_queue_status_priority', 'status', 'priority', 'created_at'),
        Index('idx_enrichment_queue_target', 'target_type', 'target_id'),
    )
