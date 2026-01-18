"""Model manager for LLM inference coordination."""
import logging
from typing import Optional, Dict, Any

from src.services.ollama_client import OllamaClient

logger = logging.getLogger(__name__)


class ModelManager:
    """Manages model loading and inference for enrichment tasks."""
    
    def __init__(self, ollama_client: OllamaClient):
        """
        Initialize model manager.
        
        Args:
            ollama_client: OllamaClient instance
        """
        self.ollama = ollama_client
        self.current_model: Optional[str] = None
    
    async def ensure_loaded(self, model_id: str) -> bool:
        """
        Ensure model is loaded and ready.
        
        Note: Ollama handles model loading automatically on first use
        and keeps models warm in memory. This method primarily tracks
        the current model for logging purposes.
        
        Args:
            model_id: Model identifier (e.g., 'phi3:mini')
            
        Returns:
            True if model is available, False otherwise
        """
        if self.current_model != model_id:
            logger.info(f"Switching to model: {model_id}")
            
            # Verify model is available
            models = await self.ollama.list_models()
            if model_id not in models:
                logger.error(f"Model {model_id} not available. Available: {models}")
                return False
            
            self.current_model = model_id
        
        return True
    
    async def generate(
        self,
        prompt: str,
        format: Optional[str] = None,
        temperature: float = 0.7,
        system: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Generate completion using current model.
        
        Args:
            prompt: User prompt
            format: Optional format (e.g., 'json')
            temperature: Sampling temperature
            system: Optional system prompt
            
        Returns:
            Response dict or None on failure
        """
        if not self.current_model:
            logger.error("No model loaded")
            return None
        
        return await self.ollama.generate(
            model=self.current_model,
            prompt=prompt,
            format=format,
            temperature=temperature,
            system=system
        )
    
    async def chat(
        self,
        messages: list,
        format: Optional[str] = None,
        temperature: float = 0.7
    ) -> Optional[Dict[str, Any]]:
        """
        Chat completion using current model.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            format: Optional format (e.g., 'json')
            temperature: Sampling temperature
            
        Returns:
            Response dict or None on failure
        """
        if not self.current_model:
            logger.error("No model loaded")
            return None
        
        return await self.ollama.chat(
            model=self.current_model,
            messages=messages,
            format=format,
            temperature=temperature
        )
    
    def unload(self) -> None:
        """
        Unload current model.
        
        Note: Ollama manages memory automatically, so this primarily
        resets the tracking state.
        """
        if self.current_model:
            logger.info(f"Unloading model: {self.current_model}")
            self.current_model = None
