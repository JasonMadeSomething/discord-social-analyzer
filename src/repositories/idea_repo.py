"""Repository for Idea operations in Qdrant."""
from typing import List, Optional, Dict, Any
from datetime import datetime
import logging
import uuid

from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, Filter, FieldCondition, MatchValue

from src.models.qdrant_schema import (
    IDEAS_COLLECTION,
    IdeaPoint,
    get_idea_collection_config,
    create_idea_payload
)
from src.services.ollama_client import OllamaClient
from src.config import settings

logger = logging.getLogger(__name__)


class IdeaRepository:
    """Repository for Idea operations in Qdrant (analysis layer)."""
    
    def __init__(self, qdrant_client: QdrantClient, ollama_client: OllamaClient):
        self.qdrant = qdrant_client
        self.ollama = ollama_client
        self.collection_name = IDEAS_COLLECTION
    
    async def initialize_collection(self) -> bool:
        """
        Initialize the ideas collection if it doesn't exist.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            # Check if collection exists
            collections = self.qdrant.get_collections().collections
            exists = any(c.name == self.collection_name for c in collections)
            
            if not exists:
                config = get_idea_collection_config()
                self.qdrant.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=config["vectors_config"]
                )
                logger.info(f"Created Qdrant collection: {self.collection_name}")
            else:
                logger.info(f"Qdrant collection already exists: {self.collection_name}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize ideas collection: {e}")
            return False
    
    async def create_idea(
        self,
        utterance_ids: List[int],
        session_id: str,
        user_id: int,
        text: str,
        started_at: datetime,
        ended_at: datetime
    ) -> Optional[str]:
        """
        Create a new idea in Qdrant.
        
        Args:
            utterance_ids: List of constituent utterance IDs from Postgres
            session_id: Session ID
            user_id: Speaker user ID
            text: Combined utterance text
            started_at: Idea start timestamp
            ended_at: Idea end timestamp
            
        Returns:
            Idea UUID if successful, None otherwise
        """
        try:
            # Generate embedding
            embedding = await self.ollama.embed(
                model=settings.ollama_embed_model,
                text=text
            )
            
            if not embedding:
                logger.error(f"Failed to generate embedding for idea")
                return None
            
            # Create payload
            payload = create_idea_payload(
                utterance_ids=utterance_ids,
                session_id=session_id,
                user_id=user_id,
                text=text,
                started_at=started_at,
                ended_at=ended_at
            )
            
            # Generate UUID
            idea_id = str(uuid.uuid4())
            
            # Create point
            point = PointStruct(
                id=idea_id,
                vector=embedding,
                payload=payload
            )
            
            # Insert into Qdrant
            self.qdrant.upsert(
                collection_name=self.collection_name,
                points=[point]
            )
            
            logger.info(f"Created idea {idea_id} with {len(utterance_ids)} utterances")
            return idea_id
            
        except Exception as e:
            logger.error(f"Failed to create idea: {e}")
            return None
    
    def get_idea(self, idea_id: str) -> Optional[IdeaPoint]:
        """
        Retrieve an idea by UUID.
        
        Args:
            idea_id: Idea UUID
            
        Returns:
            IdeaPoint if found, None otherwise
        """
        try:
            points = self.qdrant.retrieve(
                collection_name=self.collection_name,
                ids=[idea_id],
                with_vectors=True,
                with_payload=True
            )
            
            if not points:
                return None
            
            point = points[0]
            return IdeaPoint(
                id=str(point.id),
                vector=point.vector,
                payload=point.payload
            )
            
        except Exception as e:
            logger.error(f"Failed to get idea {idea_id}: {e}")
            return None
    
    def update_enrichments(
        self,
        idea_id: str,
        enrichment_dict: Dict[str, Any]
    ) -> bool:
        """
        Partially update enrichment fields for an idea.
        
        Args:
            idea_id: Idea UUID
            enrichment_dict: Dict of fields to update (supports nested keys with dot notation)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Qdrant doesn't support partial updates directly, need to get and update
            idea = self.get_idea(idea_id)
            if not idea:
                logger.warning(f"Idea {idea_id} not found for update")
                return False
            
            # Update payload
            payload = idea.payload.copy()
            for key, value in enrichment_dict.items():
                # Handle nested keys (e.g., "enrichment_status.alias_detection")
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
                id=idea_id,
                vector=idea.vector,
                payload=payload
            )
            
            self.qdrant.upsert(
                collection_name=self.collection_name,
                points=[point]
            )
            
            logger.debug(f"Updated enrichments for idea {idea_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update enrichments for idea {idea_id}: {e}")
            return False
    
    def get_ideas_by_session(
        self,
        session_id: str,
        limit: int = 100
    ) -> List[IdeaPoint]:
        """
        Get all ideas for a session.
        
        Args:
            session_id: Session ID
            limit: Maximum number of ideas to return
            
        Returns:
            List of IdeaPoint objects
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
                IdeaPoint(
                    id=str(p.id),
                    vector=p.vector,
                    payload=p.payload
                )
                for p in points
            ]
            
        except Exception as e:
            logger.error(f"Failed to get ideas for session {session_id}: {e}")
            return []
    
    def get_ideas_needing_enrichment(
        self,
        task_type: str,
        limit: int = 100
    ) -> List[IdeaPoint]:
        """
        Get ideas that need a specific enrichment.
        
        Args:
            task_type: Enrichment task type (e.g., 'alias_detection')
            limit: Maximum number of ideas to return
            
        Returns:
            List of IdeaPoint objects
        """
        try:
            # Query for ideas where enrichment_status.<task_type> == 'pending'
            results = self.qdrant.scroll(
                collection_name=self.collection_name,
                scroll_filter=Filter(
                    must=[
                        FieldCondition(
                            key=f"enrichment_status.{task_type}",
                            match=MatchValue(value="pending")
                        )
                    ]
                ),
                limit=limit,
                with_vectors=True,
                with_payload=True
            )
            
            points, _ = results
            return [
                IdeaPoint(
                    id=str(p.id),
                    vector=p.vector,
                    payload=p.payload
                )
                for p in points
            ]
            
        except Exception as e:
            logger.error(f"Failed to get ideas needing {task_type}: {e}")
            return []
    
    async def search_similar(
        self,
        query_text: str,
        limit: int = 10,
        session_id: Optional[str] = None,
        user_id: Optional[int] = None
    ) -> List[IdeaPoint]:
        """
        Search for similar ideas using semantic search.
        
        Args:
            query_text: Text to search for
            limit: Maximum number of results
            session_id: Optional session filter
            user_id: Optional user filter
            
        Returns:
            List of IdeaPoint objects ordered by similarity
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
            filter_conditions = []
            if session_id:
                filter_conditions.append(
                    FieldCondition(
                        key="session_id",
                        match=MatchValue(value=session_id)
                    )
                )
            if user_id:
                filter_conditions.append(
                    FieldCondition(
                        key="user_id",
                        match=MatchValue(value=user_id)
                    )
                )
            
            search_filter = Filter(must=filter_conditions) if filter_conditions else None
            
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
                IdeaPoint(
                    id=str(r.id),
                    vector=r.vector,
                    payload=r.payload
                )
                for r in results
            ]
            
        except Exception as e:
            logger.error(f"Failed to search similar ideas: {e}")
            return []
    
    def get_previous_idea(
        self,
        session_id: str,
        before_timestamp: datetime,
        user_id: Optional[int] = None
    ) -> Optional[IdeaPoint]:
        """
        Get the most recent idea before a given timestamp.
        
        Args:
            session_id: Session ID
            before_timestamp: Timestamp to search before
            user_id: Optional user filter
            
        Returns:
            IdeaPoint if found, None otherwise
        """
        try:
            # Get all ideas for session (Qdrant doesn't support timestamp comparisons in filters)
            ideas = self.get_ideas_by_session(session_id, limit=1000)
            
            # Filter and sort in Python
            filtered = [
                idea for idea in ideas
                if idea.ended_at < before_timestamp
                and (user_id is None or idea.user_id != user_id)  # Different speaker
            ]
            
            if not filtered:
                return None
            
            # Sort by ended_at descending and return first
            filtered.sort(key=lambda x: x.ended_at, reverse=True)
            return filtered[0]
            
        except Exception as e:
            logger.error(f"Failed to get previous idea: {e}")
            return None
