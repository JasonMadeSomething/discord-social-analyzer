"""Enrichment worker for processing tasks from the queue."""
import asyncio
import logging
from typing import List, Dict
from collections import defaultdict

from src.repositories.enrichment_queue_repo import EnrichmentQueueRepository
from src.repositories.idea_repo import IdeaRepository
from src.repositories.exchange_repo import ExchangeRepository
from src.services.enrichment.base_handler import BaseTaskHandler
from src.services.enrichment.model_manager import ModelManager
from src.config import settings

logger = logging.getLogger(__name__)


class EnrichmentWorker:
    """Main enrichment worker that processes tasks from the queue."""
    
    def __init__(
        self,
        queue_repo: EnrichmentQueueRepository,
        handlers: List[BaseTaskHandler],
        model_manager: ModelManager,
        idea_repo: IdeaRepository,
        exchange_repo: ExchangeRepository
    ):
        """
        Initialize enrichment worker.
        
        Args:
            queue_repo: EnrichmentQueueRepository instance
            handlers: List of task handlers
            model_manager: ModelManager instance
            idea_repo: IdeaRepository instance
            exchange_repo: ExchangeRepository instance
        """
        self.queue_repo = queue_repo
        self.handlers = {h.task_type: h for h in handlers}
        self.model_manager = model_manager
        self.idea_repo = idea_repo
        self.exchange_repo = exchange_repo
        self._running = False
        self._task: asyncio.Task = None
    
    async def start(self) -> None:
        """Start the worker processing loop."""
        if self._running:
            logger.warning("Worker already running")
            return
        
        self._running = True
        logger.info("Enrichment worker started")
        
        while self._running:
            try:
                # Get pending tasks
                tasks = self.queue_repo.get_pending_tasks(
                    limit=settings.enrichment_batch_size
                )
                
                if not tasks:
                    await asyncio.sleep(settings.enrichment_poll_interval_sec)
                    continue
                
                logger.debug(f"Found {len(tasks)} pending tasks")
                
                # Group by task_type to minimize model swaps
                grouped = self._group_by_task_type(tasks)
                
                for task_type, task_batch in grouped.items():
                    handler = self.handlers.get(task_type)
                    if not handler:
                        logger.warning(f"No handler for task type: {task_type}")
                        # Mark as failed
                        for task in task_batch:
                            self.queue_repo.fail_task(
                                task.id,
                                f"No handler available for {task_type}"
                            )
                        continue
                    
                    await self._process_batch(handler, task_batch)
                
            except Exception as e:
                logger.error(f"Worker error: {e}", exc_info=True)
                await asyncio.sleep(5)
    
    async def stop(self) -> None:
        """Stop the worker."""
        self._running = False
        logger.info("Enrichment worker stopped")
    
    def _group_by_task_type(self, tasks) -> Dict[str, List]:
        """
        Group tasks by task_type.
        
        Args:
            tasks: List of EnrichmentTask objects
            
        Returns:
            Dict mapping task_type to list of tasks
        """
        grouped = defaultdict(list)
        for task in tasks:
            grouped[task.task_type].append(task)
        return dict(grouped)
    
    async def _process_batch(self, handler: BaseTaskHandler, tasks: List) -> None:
        """
        Process a batch of tasks with a handler.
        
        Args:
            handler: Task handler instance
            tasks: List of EnrichmentTask objects
        """
        # Load model if needed
        if handler.model_id:
            loaded = await self.model_manager.ensure_loaded(handler.model_id)
            if not loaded:
                logger.error(f"Failed to load model {handler.model_id}")
                for task in tasks:
                    self.queue_repo.fail_task(
                        task.id,
                        f"Model {handler.model_id} not available"
                    )
                return
        
        # Claim tasks atomically
        claimed_tasks = []
        for task in tasks:
            if self.queue_repo.claim_task(task.id):
                claimed_tasks.append(task)
            else:
                logger.debug(f"Failed to claim task {task.id} (already claimed)")
        
        if not claimed_tasks:
            logger.debug("No tasks claimed in batch")
            return
        
        logger.info("=" * 80)
        logger.info(f"⚙️  ENRICHMENT WORKER: Processing {len(claimed_tasks)} {handler.task_type} tasks")
        logger.info("=" * 80)
        
        # Prepare items for handler
        items = [
            {
                'task_id': str(task.id),
                'target_type': task.target_type,
                'target_id': task.target_id
            }
            for task in claimed_tasks
        ]
        
        try:
            # Process batch
            results = await handler.process(items)
            
            # Update task statuses
            for task, result in zip(claimed_tasks, results):
                if result.get('status') == 'complete':
                    self.queue_repo.complete_task(task.id)
                    logger.debug(f"Completed task {task.id}")
                else:
                    error = result.get('error', 'Unknown error')
                    self.queue_repo.fail_task(task.id, error)
                    logger.warning(f"Failed task {task.id}: {error}")
        
        except Exception as e:
            logger.error(f"Batch processing failed: {e}", exc_info=True)
            # Mark all as failed
            for task in claimed_tasks:
                self.queue_repo.fail_task(task.id, str(e))
