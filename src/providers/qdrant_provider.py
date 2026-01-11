from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue
from src.providers.interfaces import IVectorStore
from src.config import settings
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class QdrantProvider(IVectorStore):
    """
    Qdrant vector database provider for semantic search.
    Stores embeddings with metadata for utterances and messages.
    """
    
    def __init__(self, collection_name: str = None, vector_size: int = 384):
        """
        Initialize Qdrant client and ensure collection exists.
        
        Args:
            collection_name: Name of the collection to use
            vector_size: Dimension of vectors (384 for all-MiniLM-L6-v2)
        """
        self.collection_name = collection_name or settings.qdrant_collection
        self.vector_size = vector_size
        
        if settings.qdrant_api_key:
            self.client = QdrantClient(
                host=settings.qdrant_host,
                port=settings.qdrant_port,
                api_key=settings.qdrant_api_key
            )
        else:
            self.client = QdrantClient(
                host=settings.qdrant_host,
                port=settings.qdrant_port
            )
        
        self._ensure_collection()
        
        logger.info(f"Qdrant provider initialized: {settings.qdrant_host}:{settings.qdrant_port}/{self.collection_name}")
    
    def _ensure_collection(self):
        """Create collection if it doesn't exist."""
        try:
            collections = self.client.get_collections().collections
            collection_names = [c.name for c in collections]
            
            if self.collection_name not in collection_names:
                logger.info(f"Creating Qdrant collection: {self.collection_name}")
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(
                        size=self.vector_size,
                        distance=Distance.COSINE
                    )
                )
                logger.info(f"Collection created: {self.collection_name}")
            else:
                logger.info(f"Collection already exists: {self.collection_name}")
        except Exception as e:
            logger.error(f"Failed to ensure collection: {e}", exc_info=True)
            raise
    
    async def store_embedding(
        self,
        id: str,
        vector: list[float],
        metadata: dict
    ) -> None:
        """
        Store a vector embedding with metadata.
        
        Args:
            id: Unique identifier for the embedding
            vector: The embedding vector
            metadata: Associated metadata (text, user_id, session_id, timestamp, etc.)
        """
        try:
            point = PointStruct(
                id=id,
                vector=vector,
                payload=metadata
            )
            
            self.client.upsert(
                collection_name=self.collection_name,
                points=[point]
            )
            
            logger.debug(f"Stored embedding: {id}")
        except Exception as e:
            logger.error(f"Failed to store embedding {id}: {e}", exc_info=True)
            raise
    
    async def search_similar(
        self,
        vector: list[float],
        limit: int = 10,
        filter_conditions: Optional[dict] = None
    ) -> list[dict]:
        """
        Search for similar vectors.
        
        Args:
            vector: Query vector
            limit: Maximum number of results
            filter_conditions: Optional filters (e.g., {'user_id': 123, 'session_id': 456})
            
        Returns:
            List of similar items with metadata and scores
        """
        try:
            query_filter = None
            if filter_conditions:
                must_conditions = []
                for key, value in filter_conditions.items():
                    must_conditions.append(
                        FieldCondition(
                            key=key,
                            match=MatchValue(value=value)
                        )
                    )
                query_filter = Filter(must=must_conditions)
            
            results = self.client.search(
                collection_name=self.collection_name,
                query_vector=vector,
                limit=limit,
                query_filter=query_filter
            )
            
            formatted_results = []
            for result in results:
                formatted_results.append({
                    'id': result.id,
                    'score': result.score,
                    'metadata': result.payload
                })
            
            logger.debug(f"Found {len(formatted_results)} similar vectors")
            return formatted_results
            
        except Exception as e:
            logger.error(f"Search failed: {e}", exc_info=True)
            return []
    
    async def delete(self, id: str) -> None:
        """
        Delete a vector by ID.
        
        Args:
            id: ID of the vector to delete
        """
        try:
            self.client.delete(
                collection_name=self.collection_name,
                points_selector=[id]
            )
            logger.debug(f"Deleted embedding: {id}")
        except Exception as e:
            logger.error(f"Failed to delete embedding {id}: {e}", exc_info=True)
            raise
    
    def get_collection_info(self) -> dict:
        """Get collection statistics."""
        try:
            info = self.client.get_collection(self.collection_name)
            return {
                'name': self.collection_name,
                'vectors_count': info.vectors_count,
                'indexed_vectors_count': info.indexed_vectors_count,
                'points_count': info.points_count
            }
        except Exception as e:
            logger.error(f"Failed to get collection info: {e}")
            return {}
