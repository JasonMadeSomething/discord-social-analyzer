"""Response mapping handler for detecting response relationships between ideas."""
from typing import List, Dict, Any
import logging

from src.services.enrichment.base_handler import BaseTaskHandler
from src.repositories.idea_repo import IdeaRepository
from src.config import settings

logger = logging.getLogger(__name__)


class ResponseMappingHandler(BaseTaskHandler):
    """Maps response relationships between ideas."""
    
    task_type = "response_mapping"
    target_types = ["idea"]
    model_id = None  # Rule-based
    
    def __init__(self, idea_repo: IdeaRepository):
        """
        Initialize response mapping handler.
        
        Args:
            idea_repo: IdeaRepository instance
        """
        self.idea_repo = idea_repo
    
    async def process(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Process batch of ideas for response mapping."""
        results = []
        
        for item in items:
            try:
                idea = self.idea_repo.get_idea(item['target_id'])
                if not idea:
                    results.append({'status': 'failed', 'error': 'Idea not found'})
                    continue
                
                # Find previous idea in session
                previous_idea = self.idea_repo.get_previous_idea(
                    session_id=idea.session_id,
                    before_timestamp=idea.started_at,
                    user_id=idea.user_id  # Different speaker
                )
                
                response_data = {}
                
                if previous_idea:
                    # Calculate latency
                    latency_ms = (idea.started_at - previous_idea.ended_at).total_seconds() * 1000
                    
                    # Check if within response threshold
                    if latency_ms <= settings.response_mapping_time_threshold_ms:
                        # Check prosody interpretation for completeness
                        prev_prosody = previous_idea.payload.get('prosody_interpretation', {})
                        is_complete = prev_prosody.get('is_complete', True)
                        
                        # If previous idea seems complete and timing is right, mark as response
                        if is_complete or latency_ms < 1000:  # Very quick responses likely related
                            response_data['is_response_to_idea_id'] = str(previous_idea.id)
                            response_data['response_latency_ms'] = latency_ms
                
                # Update idea
                response_data['enrichment_status.response_mapping'] = 'complete'
                
                success = self.idea_repo.update_enrichments(
                    item['target_id'],
                    response_data
                )
                
                if success:
                    results.append({'status': 'complete'})
                    if response_data.get('is_response_to_idea_id'):
                        logger.info(
                            f"Mapped idea {item['target_id']} as response to "
                            f"{response_data['is_response_to_idea_id']} "
                            f"(latency={response_data['response_latency_ms']:.0f}ms)"
                        )
                else:
                    results.append({'status': 'failed', 'error': 'Failed to update idea'})
                
            except Exception as e:
                logger.error(f"Response mapping failed for {item['target_id']}: {e}")
                results.append({'status': 'failed', 'error': str(e)})
        
        return results
