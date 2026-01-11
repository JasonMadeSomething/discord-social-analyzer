from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime

from src.models.database import MessageModel
from src.models.domain import Message


class MessageRepository:
    """Repository for chat message operations."""
    
    def __init__(self, db_session: Session):
        self.db = db_session
    
    def create_message(
        self,
        message_id: int,
        channel_id: int,
        user_id: int,
        username: str,
        display_name: str,
        content: str,
        timestamp: datetime,
        session_id: Optional[str] = None,
        reply_to_message_id: Optional[int] = None
    ) -> None:
        """Create a new message."""
        message = MessageModel(
            message_id=message_id,
            channel_id=channel_id,
            user_id=user_id,
            username=username,
            display_name=display_name,
            content=content,
            timestamp=timestamp,
            session_id=session_id,
            reply_to_message_id=reply_to_message_id
        )
        self.db.add(message)
        self.db.commit()
    
    def get_messages_by_session(
        self,
        session_id: str,
        limit: Optional[int] = None
    ) -> List[Message]:
        """Get all messages associated with a session."""
        query = self.db.query(MessageModel).filter(
            MessageModel.session_id == session_id
        ).order_by(MessageModel.timestamp)
        
        if limit:
            query = query.limit(limit)
        
        messages = query.all()
        return [self._to_domain(m) for m in messages]
    
    def get_messages_by_channel(
        self,
        channel_id: int,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100
    ) -> List[Message]:
        """Get messages from a channel, optionally filtered by time."""
        query = self.db.query(MessageModel).filter(
            MessageModel.channel_id == channel_id
        )
        
        if start_time:
            query = query.filter(MessageModel.timestamp >= start_time)
        
        if end_time:
            query = query.filter(MessageModel.timestamp <= end_time)
        
        messages = query.order_by(
            MessageModel.timestamp.desc()
        ).limit(limit).all()
        
        return [self._to_domain(m) for m in messages]
    
    def get_messages_by_user(
        self,
        user_id: int,
        channel_id: Optional[int] = None,
        limit: int = 100
    ) -> List[Message]:
        """Get messages by a specific user."""
        query = self.db.query(MessageModel).filter(
            MessageModel.user_id == user_id
        )
        
        if channel_id:
            query = query.filter(MessageModel.channel_id == channel_id)
        
        messages = query.order_by(
            MessageModel.timestamp.desc()
        ).limit(limit).all()
        
        return [self._to_domain(m) for m in messages]
    
    def search_messages(
        self,
        text_query: str,
        channel_id: Optional[int] = None,
        session_id: Optional[str] = None,
        limit: int = 50
    ) -> List[Message]:
        """Search messages by content."""
        query = self.db.query(MessageModel).filter(
            MessageModel.content.ilike(f"%{text_query}%")
        )
        
        if channel_id:
            query = query.filter(MessageModel.channel_id == channel_id)
        
        if session_id:
            query = query.filter(MessageModel.session_id == session_id)
        
        messages = query.order_by(
            MessageModel.timestamp.desc()
        ).limit(limit).all()
        
        return [self._to_domain(m) for m in messages]
    
    def _to_domain(self, message: MessageModel) -> Message:
        """Convert database model to domain model."""
        return Message(
            message_id=message.message_id,
            channel_id=message.channel_id,
            user_id=message.user_id,
            username=message.username,
            display_name=message.display_name,
            content=message.content,
            timestamp=message.timestamp,
            session_id=message.session_id,
            reply_to_message_id=message.reply_to_message_id
        )
