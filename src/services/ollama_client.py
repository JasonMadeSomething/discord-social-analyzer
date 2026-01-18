"""Ollama LLM client service for enrichment tasks."""
import logging
import aiohttp
from typing import Optional, Dict, Any, List
from src.config import settings

logger = logging.getLogger(__name__)


class OllamaClient:
    """Client for Ollama HTTP API."""
    
    def __init__(self, base_url: Optional[str] = None):
        """
        Initialize Ollama client.
        
        Args:
            base_url: Ollama API base URL (default from settings)
        """
        self.base_url = base_url or settings.ollama_base_url
        self._session: Optional[aiohttp.ClientSession] = None
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session
    
    async def close(self):
        """Close the client session."""
        if self._session and not self._session.closed:
            await self._session.close()
    
    async def is_healthy(self) -> bool:
        """
        Check if Ollama service is healthy and reachable.
        
        Returns:
            True if service is healthy, False otherwise
        """
        try:
            session = await self._get_session()
            async with session.get(f"{self.base_url}/api/tags", timeout=aiohttp.ClientTimeout(total=5)) as response:
                return response.status == 200
        except Exception as e:
            logger.warning(f"Ollama health check failed: {e}")
            return False
    
    async def list_models(self) -> List[str]:
        """
        List available models.
        
        Returns:
            List of model names
        """
        try:
            session = await self._get_session()
            async with session.get(f"{self.base_url}/api/tags") as response:
                response.raise_for_status()
                data = await response.json()
                return [model['name'] for model in data.get('models', [])]
        except Exception as e:
            logger.error(f"Failed to list models: {e}")
            return []
    
    async def generate(
        self,
        model: str,
        prompt: str,
        format: Optional[str] = None,
        system: Optional[str] = None,
        temperature: float = 0.7,
        stream: bool = False
    ) -> Optional[Dict[str, Any]]:
        """
        Generate completion from model.
        
        Args:
            model: Model name (e.g., 'phi3:mini')
            prompt: User prompt
            format: Optional format specification (e.g., 'json')
            system: Optional system prompt
            temperature: Sampling temperature (0.0-1.0)
            stream: Whether to stream response (not implemented)
            
        Returns:
            Response dict with 'response' key, or None on failure
        """
        try:
            session = await self._get_session()
            
            payload = {
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": temperature
                }
            }
            
            if format:
                payload["format"] = format
            
            if system:
                payload["system"] = system
            
            async with session.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=60)
            ) as response:
                response.raise_for_status()
                return await response.json()
                
        except Exception as e:
            logger.error(f"Ollama generate failed: {e}")
            return None
    
    async def embed(
        self,
        model: str,
        text: str
    ) -> Optional[List[float]]:
        """
        Generate embedding vector for text.
        
        Args:
            model: Embedding model name (e.g., 'nomic-embed-text')
            text: Text to embed
            
        Returns:
            Embedding vector as list of floats, or None on failure
        """
        try:
            session = await self._get_session()
            
            payload = {
                "model": model,
                "prompt": text
            }
            
            async with session.post(
                f"{self.base_url}/api/embeddings",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                response.raise_for_status()
                data = await response.json()
                return data.get('embedding')
                
        except Exception as e:
            logger.error(f"Ollama embed failed: {e}")
            return None
    
    async def chat(
        self,
        model: str,
        messages: List[Dict[str, str]],
        format: Optional[str] = None,
        temperature: float = 0.7
    ) -> Optional[Dict[str, Any]]:
        """
        Chat completion with message history.
        
        Args:
            model: Model name
            messages: List of message dicts with 'role' and 'content'
            format: Optional format specification (e.g., 'json')
            temperature: Sampling temperature
            
        Returns:
            Response dict with 'message' key, or None on failure
        """
        try:
            session = await self._get_session()
            
            payload = {
                "model": model,
                "messages": messages,
                "stream": False,
                "options": {
                    "temperature": temperature
                }
            }
            
            if format:
                payload["format"] = format
            
            async with session.post(
                f"{self.base_url}/api/chat",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=60)
            ) as response:
                response.raise_for_status()
                return await response.json()
                
        except Exception as e:
            logger.error(f"Ollama chat failed: {e}")
            return None
