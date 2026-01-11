from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List
from enum import Enum


class SessionStatus(Enum):
    """Session lifecycle states."""
    ACTIVE = "active"
    ENDED = "ended"
    ABANDONED = "abandoned"  # Timeout without explicit end


@dataclass
class Participant:
    """Represents a participant in a session."""
    user_id: int
    username: str
    display_name: str
    joined_at: datetime
    left_at: Optional[datetime] = None


@dataclass
class Session:
    """Represents a voice channel session."""
    session_id: str
    channel_id: int
    channel_name: str
    guild_id: int
    started_at: datetime
    ended_at: Optional[datetime]
    status: SessionStatus
    participants: List[Participant]
    
    @property
    def duration(self) -> Optional[float]:
        """Duration in seconds."""
        if self.ended_at:
            return (self.ended_at - self.started_at).total_seconds()
        return None
    
    @property
    def active_participant_count(self) -> int:
        """Count of participants currently in the session."""
        return sum(1 for p in self.participants if p.left_at is None)


@dataclass
class Utterance:
    """Represents a single speech utterance."""
    utterance_id: Optional[int]
    session_id: str
    user_id: int
    username: str
    display_name: str
    text: str
    started_at: datetime
    ended_at: datetime
    confidence: float
    audio_duration: float  # seconds
    
    @property
    def duration(self) -> float:
        """Duration in seconds."""
        return (self.ended_at - self.started_at).total_seconds()


@dataclass
class Message:
    """Represents a chat message."""
    message_id: int
    channel_id: int
    user_id: int
    username: str
    display_name: str
    content: str
    timestamp: datetime
    session_id: Optional[str]  # Linked to voice session if during one
    reply_to_message_id: Optional[int] = None


@dataclass
class TranscriptionResult:
    """Result from transcription service."""
    text: str
    confidence: float
    language: Optional[str] = None
    duration: Optional[float] = None
