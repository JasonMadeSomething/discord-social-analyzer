"""Qdrant collection schemas for analysis layer."""
from typing import Dict, Any, List, Optional
from datetime import datetime
from qdrant_client.models import Distance, VectorParams, PointStruct
import uuid


# Collection names
IDEAS_COLLECTION = "ideas"
EXCHANGES_COLLECTION = "exchanges"


def get_idea_collection_config() -> Dict[str, Any]:
    """
    Get configuration for ideas collection.
    
    Returns:
        Collection configuration dict
    """
    return {
        "vectors_config": VectorParams(
            size=768,  # nomic-embed-text dimension
            distance=Distance.COSINE
        )
    }


def get_exchange_collection_config() -> Dict[str, Any]:
    """
    Get configuration for exchanges collection.
    
    Returns:
        Collection configuration dict
    """
    return {
        "vectors_config": VectorParams(
            size=768,  # nomic-embed-text dimension
            distance=Distance.COSINE
        )
    }


def create_idea_payload(
    utterance_ids: List[int],
    session_id: str,
    user_id: int,
    text: str,
    started_at: datetime,
    ended_at: datetime
) -> Dict[str, Any]:
    """
    Create payload structure for an idea.
    
    Args:
        utterance_ids: List of constituent utterance IDs from Postgres
        session_id: Session ID
        user_id: Speaker user ID
        text: Combined utterance text
        started_at: Idea start timestamp
        ended_at: Idea end timestamp
        
    Returns:
        Payload dict with all fields initialized
    """
    return {
        # Core fields (immutable)
        "utterance_ids": utterance_ids,
        "session_id": session_id,
        "user_id": user_id,
        "text": text,
        "started_at": started_at.isoformat(),
        "ended_at": ended_at.isoformat(),
        
        # Enrichments (populated by workers)
        "intent": None,
        "intent_confidence": None,
        "keywords": None,
        "mentions": None,
        "is_response_to_idea_id": None,
        "response_latency_ms": None,
        
        # Prosody interpretation (derived from raw prosody in utterances)
        "prosody_interpretation": None,
        
        # Enrichment status tracking
        "enrichment_status": {
            "alias_detection": "pending",
            "intent_keywords": "pending",
            "response_mapping": "pending",
            "prosody_interpretation": "pending"
        }
    }


def create_exchange_payload(
    idea_ids: List[str],
    session_id: str,
    participant_user_ids: List[int],
    started_at: datetime,
    ended_at: datetime
) -> Dict[str, Any]:
    """
    Create payload structure for an exchange.
    
    Args:
        idea_ids: List of constituent idea UUIDs
        session_id: Session ID
        participant_user_ids: List of participant user IDs
        started_at: Exchange start timestamp
        ended_at: Exchange end timestamp
        
    Returns:
        Payload dict with all fields initialized
    """
    return {
        # Core fields (immutable)
        "idea_ids": idea_ids,
        "session_id": session_id,
        "participant_user_ids": participant_user_ids,
        "started_at": started_at.isoformat(),
        "ended_at": ended_at.isoformat(),
        
        # Enrichments (populated by workers)
        "summary": None,
        "primary_keywords": None,
        "exchange_type": None,
        
        # Enrichment status tracking
        "enrichment_status": {
            "summary": "pending",
            "keywords": "pending",
            "classification": "pending"
        }
    }


class IdeaPoint:
    """Domain model for an Idea point in Qdrant."""
    
    def __init__(
        self,
        id: str,
        vector: List[float],
        payload: Dict[str, Any]
    ):
        self.id = id
        self.vector = vector
        self.payload = payload
    
    @property
    def utterance_ids(self) -> List[int]:
        return self.payload.get("utterance_ids", [])
    
    @property
    def session_id(self) -> str:
        return self.payload.get("session_id")
    
    @property
    def user_id(self) -> int:
        return self.payload.get("user_id")
    
    @property
    def text(self) -> str:
        return self.payload.get("text", "")
    
    @property
    def started_at(self) -> datetime:
        return datetime.fromisoformat(self.payload.get("started_at"))
    
    @property
    def ended_at(self) -> datetime:
        return datetime.fromisoformat(self.payload.get("ended_at"))
    
    @property
    def intent(self) -> Optional[str]:
        return self.payload.get("intent")
    
    @property
    def keywords(self) -> Optional[List[str]]:
        return self.payload.get("keywords")
    
    @property
    def mentions(self) -> Optional[List[Dict[str, Any]]]:
        return self.payload.get("mentions")
    
    @property
    def is_response_to_idea_id(self) -> Optional[str]:
        return self.payload.get("is_response_to_idea_id")
    
    @property
    def enrichment_status(self) -> Dict[str, str]:
        return self.payload.get("enrichment_status", {})


class ExchangePoint:
    """Domain model for an Exchange point in Qdrant."""
    
    def __init__(
        self,
        id: str,
        vector: List[float],
        payload: Dict[str, Any]
    ):
        self.id = id
        self.vector = vector
        self.payload = payload
    
    @property
    def idea_ids(self) -> List[str]:
        return self.payload.get("idea_ids", [])
    
    @property
    def session_id(self) -> str:
        return self.payload.get("session_id")
    
    @property
    def participant_user_ids(self) -> List[int]:
        return self.payload.get("participant_user_ids", [])
    
    @property
    def started_at(self) -> datetime:
        return datetime.fromisoformat(self.payload.get("started_at"))
    
    @property
    def ended_at(self) -> datetime:
        return datetime.fromisoformat(self.payload.get("ended_at"))
    
    @property
    def summary(self) -> Optional[str]:
        return self.payload.get("summary")
    
    @property
    def primary_keywords(self) -> Optional[List[str]]:
        return self.payload.get("primary_keywords")
    
    @property
    def exchange_type(self) -> Optional[str]:
        return self.payload.get("exchange_type")
    
    @property
    def enrichment_status(self) -> Dict[str, str]:
        return self.payload.get("enrichment_status", {})
