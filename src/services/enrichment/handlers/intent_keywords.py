"""Intent and keyword extraction handler using Ollama LLM."""
import logging
from typing import List, Dict
from src.services.enrichment.base_handler import BaseTaskHandler
from src.repositories.idea_repo import IdeaRepository

logger = logging.getLogger(__name__)


class IntentKeywordsHandler(BaseTaskHandler):
    """Extract intent and keywords from ideas using LLM."""
    
    task_type = 'intent_keywords'
    model_id = 'phi3:mini'
    
    def __init__(self, idea_repo: IdeaRepository, ollama_client):
        """
        Initialize handler.
        
        Args:
            idea_repo: IdeaRepository instance
            ollama_client: OllamaClient instance
        """
        self.idea_repo = idea_repo
        self.ollama_client = ollama_client
    
    async def process(self, items: List[Dict]) -> List[Dict]:
        """
        Process intent and keyword extraction tasks.
        
        Args:
            items: List of task items with target_id (idea UUID)
            
        Returns:
            List of results with status
        """
        results = []
        
        for item in items:
            try:
                # Get idea
                idea = await self.idea_repo.get_idea(item['target_id'])
                if not idea:
                    results.append({'status': 'failed', 'error': 'Idea not found'})
                    continue
                
                # Extract intent and keywords using LLM
                intent, keywords = await self._extract_intent_keywords(idea.text)
                
                # Update idea
                success = await self.idea_repo.update_enrichments(
                    item['target_id'],
                    {
                        'intent': intent,
                        'keywords': keywords,
                        'enrichment_status.intent_keywords': 'complete'
                    }
                )
                
                if success:
                    results.append({'status': 'complete'})
                    logger.info(f"✓ Intent/Keywords: intent='{intent}', {len(keywords)} keywords for idea {item['target_id']}")
                    if keywords:
                        logger.info(f"   Keywords: {', '.join(keywords[:5])}{'...' if len(keywords) > 5 else ''}")
                else:
                    results.append({'status': 'failed', 'error': 'Failed to update idea'})
                
            except Exception as e:
                logger.error(f"Intent/keyword extraction failed for {item['target_id']}: {e}")
                results.append({'status': 'failed', 'error': str(e)})
        
        return results
    
    async def _extract_intent_keywords(self, text: str) -> tuple:
        """
        Extract intent and keywords from text using Ollama.
        
        Args:
            text: Idea text
            
        Returns:
            Tuple of (intent, keywords list)
        """
        prompt = f"""Analyze this conversation snippet and extract:
1. The primary INTENT (what the speaker is trying to do - e.g., "asking question", "making statement", "giving instruction", "expressing emotion")
2. Key KEYWORDS (important nouns, verbs, topics - max 5)

Text: "{text}"

Respond in this exact format:
INTENT: <one short phrase>
KEYWORDS: <comma-separated list>"""
        
        try:
            response = await self.ollama_client.generate(
                model=self.model_id,
                prompt=prompt,
                options={'temperature': 0.3}
            )
            
            # Parse response
            intent = "unknown"
            keywords = []
            
            for line in response.split('\n'):
                line = line.strip()
                if line.startswith('INTENT:'):
                    intent = line.replace('INTENT:', '').strip()
                elif line.startswith('KEYWORDS:'):
                    kw_text = line.replace('KEYWORDS:', '').strip()
                    keywords = [k.strip() for k in kw_text.split(',') if k.strip()]
            
            return intent, keywords[:5]  # Max 5 keywords
            
        except Exception as e:
            logger.error(f"Ollama intent/keyword extraction failed: {e}")
            return "unknown", []
