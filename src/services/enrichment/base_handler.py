"""Base class for enrichment task handlers."""
from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Any
import logging

logger = logging.getLogger(__name__)


class BaseTaskHandler(ABC):
    """Abstract base class for enrichment task handlers."""
    
    @property
    @abstractmethod
    def task_type(self) -> str:
        """Task type identifier (e.g., 'alias_detection')."""
        pass
    
    @property
    @abstractmethod
    def target_types(self) -> List[str]:
        """Supported target types (e.g., ['idea'])."""
        pass
    
    @property
    def model_id(self) -> Optional[str]:
        """Model ID if LLM-based, None for rule-based handlers."""
        return None
    
    @property
    def batch_size(self) -> int:
        """Preferred batch size for processing."""
        return 10
    
    @abstractmethod
    async def process(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Process a batch of items.
        
        Args:
            items: List of task items with target_id, target_type, task_id
            
        Returns:
            List of result dicts with 'status' key ('complete' or 'failed')
            and optional 'error' key for failures
        """
        pass
    
    def output_schema(self) -> Dict[str, Any]:
        """
        Define expected output structure for this handler.
        
        Returns:
            Schema dict describing output fields
        """
        return {}
