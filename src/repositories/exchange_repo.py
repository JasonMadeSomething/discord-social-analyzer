"""Repository for Exchange operations in Qdrant."""
from typing import List, Optional, Dict, Any
from datetime import datetime
import logging
import uuid

from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, Filter, FieldCondition, MatchValue

from src.models.qdrant_schema import (
    EXCHANGES_COLLECTION,
    ExchangePoint,
    get_exchange_collection_config,
    create_exchange_payload
)
from src.services.ollama_client import OllamaClient
from src.config import settings

logger = logging.getLogger(__name__)


class ExchangeRepository:
    """Repository for Exchange operations in Qdrant (analysis layer)."""
    
    def __init__(self, qdrant_client: QdrantClient, ollama_client: OllamaClient):
        self.qdrant = qdrant_client
        self.ollama = ollama_client
        self.collection_name = EXCHANGES_COLLECTION
    
    async def initialize_collection(self) -> bool:
        """
        Initialize the exchanges collection if it doesn't exist.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            collections = self.qdrant.get_collections().collections
            exists = any(c.name == self.collection_name for c in collections)
            
            if not exists:
                config = get_exchange_collection_config()
                self.qdrant.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=config["vectors_config"]
                )
                logger.info(f"Created Qdrant collection: {self.collection_name}")
            else:
                logger.info(f"Qdrant collection already exists: {self.collection_name}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize exchanges collection: {e}")
            return False
    
    async def create_exchange(
        self,
        idea_ids: List[str],
        session_id: str,
        participant_user_ids: List[int],
        combined_text: str,
        started_at: datetime,
        ended_at: datetime
    ) -> Optional[str]:
        """
        Create a new exchange in Qdrant.
        
        Args:
            idea_ids: List of constituent idea UUIDs
            session_id: Session ID
            participant_user_ids: List of participant user IDs
            combined_text: Combined text from all ideas for embedding
            started_at: Exchange start timestamp
            ended_at: Exchange end timestamp
            
        Returns:
            Exchange UUID if successful, None otherwise
        """
        try:
            # Generate embedding from combined idea content
            embedding = await self.ollama.embed(
                model=settings.ollama_embed_model,
                text=combined_text
            )
            
            if not embedding:
                logger.error("Failed to generate embedding for exchange")
                return None
            
            # Create payload
            payload = create_exchange_payload(
                idea_ids=idea_ids,
                session_id=session_id,
                participant_user_ids=participant_user_ids,
                started_at=started_at,
                ended_at=ended_at
            )
            
            # Generate UUID
            exchange_id = str(uuid.uuid4())
            
            # Create point
            point = PointStruct(
                id=exchange_id,
                vector=embedding,
                payload=payload
            )
            
            # Insert into Qdrant
            self.qdrant.upsert(
                collection_name=self.collection_name,
                points=[point]
            )
            
            logger.info(f"Created exchange {exchange_id} with {len(idea_ids)} ideas")
            return exchange_id
            
        except Exception as e:
            logger.error(f"Failed to create exchange: {e}")
            return None
    
    def get_exchange(self, exchange_id: str) -> Optional[ExchangePoint]:
        """
        Retrieve an exchange by UUID.
        
        Args:
            exchange_id: Exchange UUID
            
        Returns:
            ExchangePoint if found, None otherwise
        """
        try:
            points = self.qdrant.retrieve(
                collection_name=self.collection_name,
                ids=[exchange_id],
                with_vectors=True,
                with_payload=True
            )
            
            if not points:
                return None
            
            point = points[0]
            return ExchangePoint(
                id=str(point.id),
                vector=point.vector,
                payload=point.payload
            )
            
        except Exception as e:
            logger.error(f"Failed to get exchange {exchange_id}: {e}")
            return None
    
    def update_enrichments(
        self,
        exchange_id: str,
        enrichment_dict: Dict[str, Any]
    ) -> bool:
        """
        Partially update enrichment fields for an exchange.
        
        Args:
            exchange_id: Exchange UUID
            enrichment_dict: Dict of fields to update
            
        Returns:
            True if successful, False otherwise
        """
        try:
            exchange = self.get_exchange(exchange_id)
            if not exchange:
                logger.warning(f"Exchange {exchange_id} not found for update")
                return False
            
            # Update payload
            payload = exchange.payload.copy()
            for key, value in enrichment_dict.items():
                if '.' in key:
                    parts = key.split('.')
                    current = payload
                    for part in parts[:-1]:
                        if part not in current:
                            current[part] = {}
                        current = current[part]
                    current[parts[-1]] = value
                else:
                    payload[key] = value
            
            # Update point
            point = PointStruct(
                id=exchange_id,
                vector=exchange.vector,
                payload=payload
            )
            
            self.qdrant.upsert(
                collection_name=self.collection_name,
                points=[point]
            )
            
            logger.debug(f"Updated enrichments for exchange {exchange_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update enrichments for exchange {exchange_id}: {e}")
            return False
    
    def get_exchanges_by_session(
        self,
        session_id: str,
        limit: int = 100
    ) -> List[ExchangePoint]:
        """
        Get all exchanges for a session.
        
        Args:
            session_id: Session ID
            limit: Maximum number of exchanges to return
            
        Returns:
            List of ExchangePoint objects
        """
        try:
            results = self.qdrant.scroll(
                collection_name=self.collection_name,
                scroll_filter=Filter(
                    must=[
                        FieldCondition(
                            key="session_id",
                            match=MatchValue(value=session_id)
                        )
                    ]
                ),
                limit=limit,
                with_vectors=True,
                with_payload=True
            )
            
            points, _ = results
            return [
                ExchangePoint(
                    id=str(p.id),
                    vector=p.vector,
                    payload=p.payload
                )
                for p in points
            ]
            
        except Exception as e:
            logger.error(f"Failed to get exchanges for session {session_id}: {e}")
            return []
    
    async def search_similar(
        self,
        query_text: str,
        limit: int = 10,
        session_id: Optional[str] = None
    ) -> List[ExchangePoint]:
        """
        Search for similar exchanges using semantic search.
        
        Args:
            query_text: Text to search for
            limit: Maximum number of results
            session_id: Optional session filter
            
        Returns:
            List of ExchangePoint objects ordered by similarity
        """
        try:
            # Generate query embedding
            embedding = await self.ollama.embed(
                model=settings.ollama_embed_model,
                text=query_text
            )
            
            if not embedding:
                logger.error("Failed to generate query embedding")
                return []
            
            # Build filter
            search_filter = None
            if session_id:
                search_filter = Filter(
                    must=[
                        FieldCondition(
                            key="session_id",
                            match=MatchValue(value=session_id)
                        )
                    ]
                )
            
            # Search
            results = self.qdrant.search(
                collection_name=self.collection_name,
                query_vector=embedding,
                query_filter=search_filter,
                limit=limit,
                with_vectors=True,
                with_payload=True
            )
            
            return [
                ExchangePoint(
                    id=str(r.id),
                    vector=r.vector,
                    payload=r.payload
                )
                for r in results
            ]
            
        except Exception as e:
            logger.error(f"Failed to search similar exchanges: {e}")
            return []
