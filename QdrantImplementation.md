# Qdrant Implementation Guide for IDE AI

Implement complete Qdrant vector database integration for semantic search and topic analysis in the Discord Social Analyzer.

## Overview

We need to add:
1. QdrantProvider (implements IVectorStore interface)
2. SentenceTransformersProvider (implements IEmbeddingProvider interface)  
3. VectorService (coordinates embedding generation and storage)
4. Hook into utterance creation to auto-generate embeddings
5. Add semantic search commands
6. Update dependencies

## Step 1: Update requirements.txt

Add these dependencies:
```
qdrant-client==1.7.0
sentence-transformers==2.2.2
```

## Step 2: Create src/providers/qdrant_provider.py

Implement the Qdrant vector store provider:

```python
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue
from src.providers.interfaces import IVectorStore
from src.config import settings
import logging
from typing import Optional
import uuid

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
        
        # Connect to Qdrant
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
        
        # Ensure collection exists
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
            # Build filter if provided
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
            
            # Search
            results = self.client.search(
                collection_name=self.collection_name,
                query_vector=vector,
                limit=limit,
                query_filter=query_filter
            )
            
            # Format results
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
                'name': info.config.params.vectors.size,
                'vectors_count': info.vectors_count,
                'indexed_vectors_count': info.indexed_vectors_count,
                'points_count': info.points_count
            }
        except Exception as e:
            logger.error(f"Failed to get collection info: {e}")
            return {}
```

## Step 3: Create src/providers/embedding_provider.py

Implement the sentence transformers embedding provider:

```python
from sentence_transformers import SentenceTransformer
from src.providers.interfaces import IEmbeddingProvider
import logging
from typing import List
import torch

logger = logging.getLogger(__name__)


class SentenceTransformersProvider(IEmbeddingProvider):
    """
    Embedding provider using sentence-transformers.
    Uses all-MiniLM-L6-v2 model (384 dimensions, fast, good quality).
    """
    
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        """
        Initialize the embedding model.
        
        Args:
            model_name: Name of the sentence-transformers model
        """
        self.model_name = model_name
        self._dimension = 384  # Default for all-MiniLM-L6-v2
        
        logger.info(f"Loading embedding model: {model_name}")
        
        # Use GPU if available
        device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"Using device: {device}")
        
        try:
            self.model = SentenceTransformer(model_name, device=device)
            # Update dimension from model
            self._dimension = self.model.get_sentence_embedding_dimension()
            logger.info(f"Embedding model loaded: {model_name} (dim={self._dimension})")
        except Exception as e:
            logger.error(f"Failed to load embedding model: {e}", exc_info=True)
            raise
    
    async def embed_text(self, text: str) -> list[float]:
        """
        Generate embedding vector for text.
        
        Args:
            text: Text to embed
            
        Returns:
            Embedding vector as list of floats
        """
        try:
            # Encode single text
            embedding = self.model.encode(text, convert_to_numpy=True)
            return embedding.tolist()
        except Exception as e:
            logger.error(f"Failed to embed text: {e}", exc_info=True)
            raise
    
    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """
        Generate embeddings for multiple texts (more efficient).
        
        Args:
            texts: List of texts to embed
            
        Returns:
            List of embedding vectors
        """
        try:
            # Batch encode for efficiency
            embeddings = self.model.encode(texts, convert_to_numpy=True, show_progress_bar=False)
            return embeddings.tolist()
        except Exception as e:
            logger.error(f"Failed to embed batch: {e}", exc_info=True)
            raise
    
    @property
    def dimension(self) -> int:
        """Vector dimension size."""
        return self._dimension
```

## Step 4: Create src/services/vector_service.py

Create a service to coordinate embedding generation and storage:

```python
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
            # Generate embedding
            vector = await self.embedding_provider.embed_text(text)
            
            # Prepare metadata
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
            
            # Store in vector database
            vector_id = f"utterance_{utterance_id}"
            await self.vector_store.store_embedding(vector_id, vector, metadata)
            
            logger.debug(f"Stored utterance embedding: {vector_id}")
            
        except Exception as e:
            logger.error(f"Failed to store utterance embedding: {e}", exc_info=True)
            # Don't raise - embedding failure shouldn't break transcription
    
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
            # Generate query embedding
            query_vector = await self.embedding_provider.embed_text(query)
            
            # Build filters
            filters = {}
            if user_id is not None:
                filters['user_id'] = user_id
            if session_id is not None:
                filters['session_id'] = session_id
            if content_type is not None:
                filters['type'] = content_type
            
            # Search
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
            # Get the utterance's vector
            # Note: This requires getting the vector from Qdrant first
            # For now, we'll skip this and just return empty
            # You could enhance this by storing vectors in PostgreSQL too
            logger.warning("find_similar_to_utterance not yet fully implemented")
            return []
            
        except Exception as e:
            logger.error(f"Failed to find similar utterances: {e}", exc_info=True)
            return []
```

## Step 5: Update src/services/transcription.py

In the `_process_buffer` method, after creating the utterance, add vector storage:

Find this section (around line 150-170):
```python
# Store utterance
utterance_id = self.utterance_repo.create_utterance(
    session_id=session_id,
    user_id=user_id,
    username=buffer.username,
    display_name=buffer.display_name,
    text=result.text,
    started_at=started_at,
    ended_at=ended_at,
    confidence=result.confidence,
    audio_duration=duration
)
```

Add AFTER it:
```python
# Store embedding in vector database (if enabled)
if hasattr(self, 'vector_service') and self.vector_service:
    await self.vector_service.store_utterance(
        utterance_id=utterance_id,
        text=result.text,
        user_id=user_id,
        username=buffer.username,
        session_id=session_id,
        timestamp=started_at,
        confidence=result.confidence
    )
```

Also update the `__init__` method to accept vector_service:
```python
def __init__(
    self,
    transcription_provider: ITranscriptionProvider,
    utterance_repo: UtteranceRepository,
    session_manager: SessionManager,
    vector_service: 'VectorService' = None  # Add this parameter
):
    self.transcription_provider = transcription_provider
    self.utterance_repo = utterance_repo
    self.session_manager = session_manager
    self.vector_service = vector_service  # Add this line
    # ... rest of __init__
```

## Step 6: Update src/config.py

Ensure these settings exist in the Settings class:
```python
# Vector database settings (should already be there)
qdrant_enabled: bool = False
qdrant_host: str = "localhost"
qdrant_port: int = 6333
qdrant_collection: str = "utterances"
qdrant_api_key: Optional[str] = None
```

## Step 7: Create src/bot/semantic_commands.py

Add semantic search commands:

```python
import discord
from discord.ext import commands
from src.services.vector_service import VectorService
from src.repositories.utterance_repo import UtteranceRepository
from src.repositories.session_repo import SessionRepository
import logging

logger = logging.getLogger(__name__)


class SemanticCommands(commands.Cog):
    """Commands for semantic search and topic analysis."""
    
    def __init__(
        self,
        bot: commands.Bot,
        vector_service: VectorService,
        utterance_repo: UtteranceRepository,
        session_repo: SessionRepository
    ):
        self.bot = bot
        self.vector_service = vector_service
        self.utterance_repo = utterance_repo
        self.session_repo = session_repo
    
    @commands.command(name='semantic')
    async def semantic_search(self, ctx, *, query: str):
        """
        Semantic search across all conversations.
        
        Usage: !semantic <query>
        Example: !semantic machine learning algorithms
        """
        if not self.vector_service.enabled:
            await ctx.send("❌ Semantic search is disabled. Set QDRANT_ENABLED=true in .env")
            return
        
        await ctx.send(f"🔍 Searching for: *{query}*...")
        
        try:
            results = await self.vector_service.semantic_search(
                query=query,
                limit=10
            )
            
            if not results:
                await ctx.send("No results found.")
                return
            
            # Format results
            embed = discord.Embed(
                title=f"Semantic Search Results",
                description=f"Query: *{query}*",
                color=discord.Color.blue()
            )
            
            for i, result in enumerate(results[:5], 1):
                metadata = result['metadata']
                score = result['score']
                
                # Format timestamp
                timestamp = metadata.get('timestamp', 'Unknown')
                
                embed.add_field(
                    name=f"{i}. {metadata.get('username', 'Unknown')} (Score: {score:.3f})",
                    value=f"```{metadata.get('text', '')[:200]}```\nTime: {timestamp}",
                    inline=False
                )
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Semantic search failed: {e}", exc_info=True)
            await ctx.send(f"❌ Search failed: {str(e)}")
    
    @commands.command(name='topics')
    async def show_topics(self, ctx):
        """
        Show common topics discussed (placeholder for future clustering).
        
        Usage: !topics
        """
        await ctx.send("📊 Topic clustering is not yet implemented. Coming soon!")
    
    @commands.command(name='similar')
    async def find_similar(self, ctx, utterance_id: int):
        """
        Find utterances similar to a specific one.
        
        Usage: !similar <utterance_id>
        Example: !similar 42
        """
        if not self.vector_service.enabled:
            await ctx.send("❌ Semantic search is disabled.")
            return
        
        # This is a placeholder - full implementation requires more work
        await ctx.send("🔍 Finding similar utterances is not yet fully implemented.")
    
    @commands.command(name='vectorstats')
    async def vector_stats(self, ctx):
        """
        Show vector database statistics.
        
        Usage: !vectorstats
        """
        if not self.vector_service.enabled:
            await ctx.send("❌ Vector database is disabled.")
            return
        
        try:
            info = self.vector_service.vector_store.get_collection_info()
            
            embed = discord.Embed(
                title="Vector Database Statistics",
                color=discord.Color.green()
            )
            
            embed.add_field(name="Collection", value=self.vector_service.vector_store.collection_name, inline=False)
            embed.add_field(name="Total Vectors", value=info.get('vectors_count', 'Unknown'), inline=True)
            embed.add_field(name="Indexed Vectors", value=info.get('indexed_vectors_count', 'Unknown'), inline=True)
            embed.add_field(name="Points", value=info.get('points_count', 'Unknown'), inline=True)
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Failed to get vector stats: {e}", exc_info=True)
            await ctx.send(f"❌ Failed to get stats: {str(e)}")
```

## Step 8: Update main.py

In the `create_dependencies` method, add vector service initialization:

After creating the transcription_provider, add:

```python
# ============================================================================
# VECTOR DATABASE (Qdrant) - for semantic search
# ============================================================================
vector_service = None
if settings.qdrant_enabled:
    logger.info("Initializing vector database...")
    try:
        from src.providers.qdrant_provider import QdrantProvider
        from src.providers.embedding_provider import SentenceTransformersProvider
        from src.services.vector_service import VectorService
        
        # Create embedding provider
        embedding_provider = SentenceTransformersProvider()
        
        # Create vector store
        vector_store = QdrantProvider(
            collection_name=settings.qdrant_collection,
            vector_size=embedding_provider.dimension
        )
        
        # Create vector service
        vector_service = VectorService(
            vector_store=vector_store,
            embedding_provider=embedding_provider
        )
        
        logger.info("Vector database initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize vector database: {e}", exc_info=True)
        logger.warning("Continuing without vector database features")
        vector_service = None
else:
    logger.info("Vector database disabled (set QDRANT_ENABLED=true to enable)")
```

Then update the TranscriptionService creation to include vector_service:

```python
transcription_service = TranscriptionService(
    transcription_provider=transcription_provider,
    utterance_repo=utterance_repo,
    session_manager=session_manager,
    vector_service=vector_service  # Add this line
)
```

And add the semantic commands cog:

```python
# Add semantic search commands (if vector service is enabled)
if vector_service:
    from src.bot.semantic_commands import SemanticCommands
    semantic_commands_cog = SemanticCommands(
        bot=bot,
        vector_service=vector_service,
        utterance_repo=utterance_repo,
        session_repo=session_repo
    )
    bot.add_cog(semantic_commands_cog)
    logger.info("Semantic commands enabled")
```

## Step 9: Update .env

Set these values in your .env file to enable Qdrant:

```env
# Enable Qdrant
QDRANT_ENABLED=true

# Qdrant connection (defaults work with Docker Compose)
QDRANT_HOST=localhost
QDRANT_PORT=6333
QDRANT_COLLECTION=utterances
```

## Testing

1. **Start the bot** with the startup script
2. **Join a voice channel** and speak
3. **Check logs** - you should see "Stored utterance embedding" messages
4. **Try semantic search**: `!semantic machine learning`
5. **Check vector stats**: `!vectorstats`
6. **View Qdrant dashboard**: http://localhost:6333/dashboard

## What This Enables

Once implemented, you can:

1. **Semantic Search**: Find conversations by meaning, not just keywords
2. **Topic Clustering**: Automatically group related discussions
3. **User Interests**: See what topics each person discusses most
4. **Topic Evolution**: Track how conversations shift over time
5. **Cross-References**: Find connections between different conversations

## Future Enhancements

- Topic clustering using UMAP/HDBSCAN
- User interest profiles
- Conversation summarization using embeddings
- Real-time topic detection
- Topic-based notifications

Implement all of the above files and code changes.