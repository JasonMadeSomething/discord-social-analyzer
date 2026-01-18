"""Alias detection handler for identifying speaker mentions."""
from typing import List, Dict, Any
import logging
import re

from src.services.enrichment.base_handler import BaseTaskHandler
from src.repositories.speaker_alias_repo import SpeakerAliasRepository
from src.repositories.idea_repo import IdeaRepository

logger = logging.getLogger(__name__)


class AliasDetectionHandler(BaseTaskHandler):
    """Detects speaker mentions in idea text using known aliases."""
    
    task_type = "alias_detection"
    target_types = ["idea"]
    model_id = None  # Rule-based
    
    def __init__(
        self,
        speaker_alias_repo: SpeakerAliasRepository,
        idea_repo: IdeaRepository
    ):
        """
        Initialize alias detection handler.
        
        Args:
            speaker_alias_repo: SpeakerAliasRepository instance
            idea_repo: IdeaRepository instance
        """
        self.speaker_alias_repo = speaker_alias_repo
        self.idea_repo = idea_repo
    
    async def process(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Process batch of ideas for alias detection."""
        # Get all aliases once for batch processing
        alias_map = self.speaker_alias_repo.get_all_aliases_map()
        
        results = []
        for item in items:
            try:
                idea = self.idea_repo.get_idea(item['target_id'])
                if not idea:
                    results.append({'status': 'failed', 'error': 'Idea not found'})
                    continue
                
                # Detect mentions
                mentions = self._detect_mentions(idea.text, alias_map, idea.user_id)
                
                # Update idea
                success = self.idea_repo.update_enrichments(
                    item['target_id'],
                    {
                        'mentions': mentions,
                        'enrichment_status.alias_detection': 'complete'
                    }
                )
                
                if success:
                    results.append({'status': 'complete'})
                    if mentions:
                        logger.info(f"✓ Alias Detection: Found {len(mentions)} mentions in idea {item['target_id']}")
                        for mention in mentions:
                            logger.info(f"   - '{mention['alias']}' → user {mention['resolved_user_id']}")
                    else:
                        logger.debug(f"✓ Alias Detection: No mentions found in idea {item['target_id']}")
                else:
                    results.append({'status': 'failed', 'error': 'Failed to update idea'})
                
            except Exception as e:
                logger.error(f"Alias detection failed for {item['target_id']}: {e}")
                results.append({'status': 'failed', 'error': str(e)})
        
        return results
    
    def _detect_mentions(
        self,
        text: str,
        alias_map: Dict[str, int],
        speaker_user_id: int
    ) -> List[Dict[str, Any]]:
        """
        Detect mentions in text using alias map.
        
        Args:
            text: Text to search for mentions
            alias_map: Map of lowercase alias -> user_id
            speaker_user_id: User ID of speaker (to exclude self-mentions)
            
        Returns:
            List of mention dicts with alias, resolved_user_id, confidence
        """
        mentions = []
        seen_users = set()
        
        # Tokenize text (simple word-based)
        words = re.findall(r'\b\w+\b', text.lower())
        
        for word in words:
            if word in alias_map:
                user_id = alias_map[word]
                
                # Skip self-mentions
                if user_id == speaker_user_id:
                    continue
                
                # Skip duplicates
                if user_id in seen_users:
                    continue
                
                mentions.append({
                    'alias': word,
                    'resolved_user_id': user_id,
                    'confidence': 1.0
                })
                seen_users.add(user_id)
        
        return mentions
