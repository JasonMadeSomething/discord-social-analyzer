from src.providers.interfaces import IVectorStore, IEmbeddingProvider
from src.config import settings
import logging
from typing import Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class VectorService:
    """
    Service for managing vector embeddings.
    Coordinates between embedding generation and vector storage.
    """
    
    def __init__(
        self,
        vector_store: IVectorStore,
        embedding_provider: IEmbeddingProvider
    ):
        self.vector_store = vector_store
        self.embedding_provider = embedding_provider
        self.enabled = settings.qdrant_enabled
        
        if self.enabled:
            logger.info("Vector service initialized and enabled")
        else:
            logger.info("Vector service initialized but disabled (set QDRANT_ENABLED=true to enable)")
    
    async def store_utterance(
        self,
        utterance_id: int,
        text: str,
        user_id: int,
        username: str,
        session_id: int,
        timestamp: datetime,
        confidence: float
    ) -> None:
        """
        Generate and store embedding for an utterance.
        
        Args:
            utterance_id: Database ID of the utterance
            text: The transcribed text
            user_id: Discord user ID
            username: User's name
            session_id: Session ID
            timestamp: When utterance occurred
            confidence: Transcription confidence
        """
        if not self.enabled:
            return
        
        try:
            vector = await self.embedding_provider.embed_text(text)
            
            metadata = {
                'text': text,
                'type': 'utterance',
                'user_id': user_id,
                'username': username,
                'session_id': session_id,
                'timestamp': timestamp.isoformat(),
                'confidence': confidence,
                'utterance_id': utterance_id
            }
            
            vector_id = f"utterance_{utterance_id}"
            await self.vector_store.store_embedding(vector_id, vector, metadata)
            
            logger.debug(f"Stored utterance embedding: {vector_id}")
            
        except Exception as e:
            logger.error(f"Failed to store utterance embedding: {e}", exc_info=True)
    
    async def store_message(
        self,
        message_id: int,
        text: str,
        user_id: int,
        username: str,
        session_id: Optional[int],
        timestamp: datetime
    ) -> None:
        """
        Generate and store embedding for a text message.
        """
        if not self.enabled or not text.strip():
            return
        
        try:
            vector = await self.embedding_provider.embed_text(text)
            
            metadata = {
                'text': text,
                'type': 'message',
                'user_id': user_id,
                'username': username,
                'session_id': session_id,
                'timestamp': timestamp.isoformat(),
                'message_id': message_id
            }
            
            vector_id = f"message_{message_id}"
            await self.vector_store.store_embedding(vector_id, vector, metadata)
            
            logger.debug(f"Stored message embedding: {vector_id}")
            
        except Exception as e:
            logger.error(f"Failed to store message embedding: {e}", exc_info=True)
    
    async def semantic_search(
        self,
        query: str,
        limit: int = 10,
        user_id: Optional[int] = None,
        session_id: Optional[int] = None,
        content_type: Optional[str] = None
    ) -> list[dict]:
        """
        Perform semantic search across all stored content.
        
        Args:
            query: Search query text
            limit: Maximum results to return
            user_id: Filter by user
            session_id: Filter by session
            content_type: Filter by type ('utterance' or 'message')
            
        Returns:
            List of similar items with scores and metadata
        """
        if not self.enabled:
            logger.warning("Vector service is disabled")
            return []
        
        try:
            query_vector = await self.embedding_provider.embed_text(query)
            
            filters = {}
            if user_id is not None:
                filters['user_id'] = user_id
            if session_id is not None:
                filters['session_id'] = session_id
            if content_type is not None:
                filters['type'] = content_type
            
            results = await self.vector_store.search_similar(
                vector=query_vector,
                limit=limit,
                filter_conditions=filters if filters else None
            )
            
            return results
            
        except Exception as e:
            logger.error(f"Semantic search failed: {e}", exc_info=True)
            return []
    
    async def find_similar_to_utterance(
        self,
        utterance_id: int,
        limit: int = 10
    ) -> list[dict]:
        """
        Find utterances/messages similar to a specific utterance.
        
        Args:
            utterance_id: ID of the reference utterance
            limit: Maximum results
            
        Returns:
            Similar items
        """
        if not self.enabled:
            return []
        
        try:
            logger.warning("find_similar_to_utterance not yet fully implemented")
            return []
            
        except Exception as e:
            logger.error(f"Failed to find similar utterances: {e}", exc_info=True)
            return []
