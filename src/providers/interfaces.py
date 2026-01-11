from abc import ABC, abstractmethod
from typing import BinaryIO, Optional
from src.models.domain import TranscriptionResult
import numpy as np


class ITranscriptionProvider(ABC):
    """Interface for speech-to-text transcription services."""
    
    @abstractmethod
    async def transcribe(self, audio_data: np.ndarray, sample_rate: int) -> TranscriptionResult:
        """
        Transcribe audio data to text.
        
        Args:
            audio_data: Audio samples as numpy array
            sample_rate: Sample rate of the audio
            
        Returns:
            TranscriptionResult with text and metadata
        """
        pass
    
    @abstractmethod
    async def transcribe_file(self, file_path: str) -> TranscriptionResult:
        """
        Transcribe audio from a file.
        
        Args:
            file_path: Path to audio file
            
        Returns:
            TranscriptionResult with text and metadata
        """
        pass


class IVectorStore(ABC):
    """Interface for vector database operations."""
    
    @abstractmethod
    async def store_embedding(
        self, 
        id: str, 
        vector: list[float], 
        metadata: dict
    ) -> None:
        """Store a vector embedding with metadata."""
        pass
    
    @abstractmethod
    async def search_similar(
        self, 
        vector: list[float], 
        limit: int = 10,
        filter_conditions: Optional[dict] = None
    ) -> list[dict]:
        """Search for similar vectors."""
        pass
    
    @abstractmethod
    async def delete(self, id: str) -> None:
        """Delete a vector by ID."""
        pass


class IEmbeddingProvider(ABC):
    """Interface for text embedding generation."""
    
    @abstractmethod
    async def embed_text(self, text: str) -> list[float]:
        """Generate embedding vector for text."""
        pass
    
    @abstractmethod
    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts."""
        pass
    
    @property
    @abstractmethod
    def dimension(self) -> int:
        """Vector dimension size."""
        pass


class ILLMProvider(ABC):
    """Interface for Large Language Model providers (for analysis/summarization)."""
    
    @abstractmethod
    async def generate(
        self, 
        prompt: str, 
        max_tokens: int = 1000,
        temperature: float = 0.7
    ) -> str:
        """Generate text from prompt."""
        pass
    
    @abstractmethod
    async def analyze_conversation(
        self, 
        utterances: list[str], 
        context: Optional[dict] = None
    ) -> dict:
        """Analyze conversation dynamics and topics."""
        pass
