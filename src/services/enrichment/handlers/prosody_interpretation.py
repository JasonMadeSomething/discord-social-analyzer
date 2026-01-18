"""Prosody interpretation handler for deriving semantic meaning from prosody."""
from typing import List, Dict, Any
import logging

from src.services.enrichment.base_handler import BaseTaskHandler
from src.repositories.idea_repo import IdeaRepository
from src.repositories.utterance_repo import UtteranceRepository

logger = logging.getLogger(__name__)


class ProsodyInterpretationHandler(BaseTaskHandler):
    """Interprets prosodic features to derive semantic indicators."""
    
    task_type = "prosody_interpretation"
    target_types = ["idea"]
    model_id = None  # Rule-based
    
    def __init__(
        self,
        idea_repo: IdeaRepository,
        utterance_repo: UtteranceRepository
    ):
        """
        Initialize prosody interpretation handler.
        
        Args:
            idea_repo: IdeaRepository instance
            utterance_repo: UtteranceRepository instance
        """
        self.idea_repo = idea_repo
        self.utterance_repo = utterance_repo
    
    async def process(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Process batch of ideas for prosody interpretation."""
        results = []
        
        for item in items:
            try:
                idea = self.idea_repo.get_idea(item['target_id'])
                if not idea:
                    results.append({'status': 'failed', 'error': 'Idea not found'})
                    continue
                
                # Get constituent utterances
                utterances = []
                for utt_id in idea.utterance_ids:
                    utt = self.utterance_repo.get_utterance_by_id(utt_id)
                    if utt:
                        utterances.append(utt)
                
                if not utterances:
                    results.append({'status': 'failed', 'error': 'No utterances found'})
                    continue
                
                # Interpret prosody
                interpretation = self._interpret_prosody(utterances)
                
                # Update idea
                success = self.idea_repo.update_enrichments(
                    item['target_id'],
                    {
                        'prosody_interpretation': interpretation,
                        'enrichment_status.prosody_interpretation': 'complete'
                    }
                )
                
                if success:
                    results.append({'status': 'complete'})
                else:
                    results.append({'status': 'failed', 'error': 'Failed to update idea'})
                
            except Exception as e:
                logger.error(f"Prosody interpretation failed for {item['target_id']}: {e}")
                results.append({'status': 'failed', 'error': str(e)})
        
        return results
    
    def _interpret_prosody(self, utterances: List) -> Dict[str, Any]:
        """
        Interpret prosodic features from utterances.
        
        Args:
            utterances: List of utterance objects with prosody data
            
        Returns:
            Interpretation dict with derived indicators
        """
        interpretation = {
            'is_complete': None,
            'is_question_prosody': None,
            'confidence_indicators': {}
        }
        
        # Get last utterance for final prosody
        last_utt = utterances[-1]
        if not last_utt.prosody:
            return interpretation
        
        prosody = last_utt.prosody
        
        # Detect question prosody (rising intonation)
        final_pitch_slope = prosody.get('final_pitch_slope')
        if final_pitch_slope is not None:
            interpretation['is_question_prosody'] = final_pitch_slope > 5
        
        # Detect completeness (falling intonation + falling intensity)
        final_intensity_slope = prosody.get('final_intensity_slope')
        if final_pitch_slope is not None and final_intensity_slope is not None:
            is_falling = final_pitch_slope < -5 and final_intensity_slope < -1
            interpretation['is_complete'] = is_falling
        
        # Confidence indicators
        hnr_db = prosody.get('hnr_db')
        if hnr_db is not None:
            interpretation['confidence_indicators']['voice_clarity'] = 'high' if hnr_db > 15 else 'low'
        
        jitter = prosody.get('jitter_local')
        if jitter is not None:
            interpretation['confidence_indicators']['pitch_stability'] = 'stable' if jitter < 0.02 else 'unstable'
        
        intensity_mean = prosody.get('intensity_mean_db')
        if intensity_mean is not None:
            interpretation['confidence_indicators']['loudness'] = 'high' if intensity_mean > 65 else 'low'
        
        return interpretation
