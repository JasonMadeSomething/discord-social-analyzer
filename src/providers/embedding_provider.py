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
        self._dimension = 384
        
        logger.info(f"Loading embedding model: {model_name}")
        
        device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"Using device: {device}")
        
        try:
            self.model = SentenceTransformer(model_name, device=device)
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
            embeddings = self.model.encode(texts, convert_to_numpy=True, show_progress_bar=False)
            return embeddings.tolist()
        except Exception as e:
            logger.error(f"Failed to embed batch: {e}", exc_info=True)
            raise
    
    @property
    def dimension(self) -> int:
        """Vector dimension size."""
        return self._dimension
