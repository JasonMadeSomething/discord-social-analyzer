"""Repository for speaker alias operations."""
from sqlalchemy.orm import Session, scoped_session
from typing import List, Optional, Dict
from datetime import datetime
import logging

from src.models.database import SpeakerAliasModel

logger = logging.getLogger(__name__)


class SpeakerAlias:
    """Domain model for speaker alias."""
    def __init__(self, id: int, user_id: int, alias: str, alias_type: str, 
                 confidence: float, created_at: datetime, created_by: Optional[int]):
        self.id = id
        self.user_id = user_id
        self.alias = alias
        self.alias_type = alias_type
        self.confidence = confidence
        self.created_at = created_at
        self.created_by = created_by


class SpeakerAliasRepository:
    """Repository for speaker alias-related database operations."""
    
    def __init__(self, session_factory: scoped_session):
        self.session_factory = session_factory
    
    @property
    def db(self) -> Session:
        """Get a fresh database session."""
        return self.session_factory()
    
    def get_aliases_for_user(self, user_id: int) -> List[SpeakerAlias]:
        """
        Get all aliases for a specific user.
        
        Args:
            user_id: Discord user ID
            
        Returns:
            List of SpeakerAlias objects
        """
        try:
            aliases = self.db.query(SpeakerAliasModel).filter(
                SpeakerAliasModel.user_id == user_id
            ).all()
            
            return [self._to_domain(a) for a in aliases]
        except Exception as e:
            logger.error(f"Failed to get aliases for user {user_id}: {e}")
            return []
    
    def get_user_by_alias(self, alias_text: str) -> Optional[int]:
        """
        Look up user_id by alias (case-insensitive).
        
        Args:
            alias_text: Alias to search for
            
        Returns:
            user_id if found, None otherwise
        """
        try:
            from sqlalchemy import func
            
            alias = self.db.query(SpeakerAliasModel).filter(
                func.lower(SpeakerAliasModel.alias) == alias_text.lower()
            ).first()
            
            return alias.user_id if alias else None
        except Exception as e:
            logger.error(f"Failed to lookup alias '{alias_text}': {e}")
            return None
    
    def get_all_aliases_map(self) -> Dict[str, int]:
        """
        Get all aliases as a map for batch matching.
        
        Returns:
            Dict mapping lowercase alias -> user_id
        """
        try:
            aliases = self.db.query(SpeakerAliasModel).all()
            return {a.alias.lower(): a.user_id for a in aliases}
        except Exception as e:
            logger.error(f"Failed to get all aliases map: {e}")
            return {}
    
    def add_alias(
        self,
        user_id: int,
        alias: str,
        alias_type: str,
        confidence: float = 1.0,
        created_by: Optional[int] = None
    ) -> Optional[int]:
        """
        Add a new alias for a user.
        
        Args:
            user_id: Discord user ID
            alias: Alias text
            alias_type: Type of alias (username, display_name, nickname, mention)
            confidence: Confidence score (0.0-1.0)
            created_by: User ID who created this alias (None if auto-generated)
            
        Returns:
            Alias ID if successful, None otherwise
        """
        try:
            # Check if alias already exists for this user
            from sqlalchemy import func
            existing = self.db.query(SpeakerAliasModel).filter(
                SpeakerAliasModel.user_id == user_id,
                func.lower(SpeakerAliasModel.alias) == alias.lower()
            ).first()
            
            if existing:
                logger.debug(f"Alias '{alias}' already exists for user {user_id}")
                return existing.id
            
            # Create new alias
            alias_model = SpeakerAliasModel(
                user_id=user_id,
                alias=alias,
                alias_type=alias_type,
                confidence=confidence,
                created_by=created_by
            )
            
            self.db.add(alias_model)
            self.db.commit()
            self.db.refresh(alias_model)
            
            logger.info(f"Added alias '{alias}' ({alias_type}) for user {user_id}")
            return alias_model.id
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to add alias '{alias}' for user {user_id}: {e}")
            return None
    
    def remove_alias(self, user_id: int, alias: str) -> bool:
        """
        Remove an alias for a user.
        
        Args:
            user_id: Discord user ID
            alias: Alias text to remove
            
        Returns:
            True if removed, False otherwise
        """
        try:
            from sqlalchemy import func
            
            deleted = self.db.query(SpeakerAliasModel).filter(
                SpeakerAliasModel.user_id == user_id,
                func.lower(SpeakerAliasModel.alias) == alias.lower()
            ).delete()
            
            self.db.commit()
            
            if deleted > 0:
                logger.info(f"Removed alias '{alias}' for user {user_id}")
                return True
            else:
                logger.warning(f"Alias '{alias}' not found for user {user_id}")
                return False
                
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to remove alias '{alias}' for user {user_id}: {e}")
            return False
    
    def auto_seed_from_utterance(
        self,
        user_id: int,
        username: str,
        display_name: str
    ) -> None:
        """
        Auto-seed aliases from first utterance by a user.
        
        Args:
            user_id: Discord user ID
            username: Discord username
            display_name: Discord display name
        """
        try:
            # Check if user already has aliases
            existing = self.db.query(SpeakerAliasModel).filter(
                SpeakerAliasModel.user_id == user_id
            ).first()
            
            if existing:
                return  # Already seeded
            
            # Add username alias
            if username:
                self.add_alias(
                    user_id=user_id,
                    alias=username,
                    alias_type='username',
                    confidence=1.0,
                    created_by=None
                )
            
            # Add display_name alias if different from username
            if display_name and display_name.lower() != username.lower():
                self.add_alias(
                    user_id=user_id,
                    alias=display_name,
                    alias_type='display_name',
                    confidence=1.0,
                    created_by=None
                )
            
            logger.info(f"Auto-seeded aliases for user {user_id} ({username})")
            
        except Exception as e:
            logger.error(f"Failed to auto-seed aliases for user {user_id}: {e}")
    
    def _to_domain(self, alias: SpeakerAliasModel) -> SpeakerAlias:
        """Convert database model to domain model."""
        return SpeakerAlias(
            id=alias.id,
            user_id=alias.user_id,
            alias=alias.alias,
            alias_type=alias.alias_type,
            confidence=alias.confidence,
            created_at=alias.created_at,
            created_by=alias.created_by
        )
