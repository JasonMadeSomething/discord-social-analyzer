"""Repository for enrichment queue operations."""
from sqlalchemy.orm import Session, scoped_session
from typing import List, Optional
from datetime import datetime
import logging
import uuid

from src.models.database import EnrichmentQueueModel

logger = logging.getLogger(__name__)


class EnrichmentTask:
    """Domain model for enrichment task."""
    def __init__(self, id: uuid.UUID, target_type: str, target_id: str, 
                 task_type: str, priority: int, status: str,
                 created_at: datetime, started_at: Optional[datetime],
                 completed_at: Optional[datetime], attempts: int, error: Optional[str]):
        self.id = id
        self.target_type = target_type
        self.target_id = target_id
        self.task_type = task_type
        self.priority = priority
        self.status = status
        self.created_at = created_at
        self.started_at = started_at
        self.completed_at = completed_at
        self.attempts = attempts
        self.error = error


class EnrichmentQueueRepository:
    """Repository for enrichment queue operations."""
    
    def __init__(self, session_factory: scoped_session):
        self.session_factory = session_factory
    
    @property
    def db(self) -> Session:
        """Get a fresh database session."""
        return self.session_factory()
    
    def get_pending_tasks(
        self,
        limit: int = 10,
        task_types: Optional[List[str]] = None
    ) -> List[EnrichmentTask]:
        """
        Get pending tasks ordered by priority and creation time.
        
        Args:
            limit: Maximum number of tasks to return
            task_types: Optional list of task types to filter by
            
        Returns:
            List of EnrichmentTask objects
        """
        try:
            query = self.db.query(EnrichmentQueueModel).filter(
                EnrichmentQueueModel.status == 'pending'
            )
            
            if task_types:
                query = query.filter(EnrichmentQueueModel.task_type.in_(task_types))
            
            tasks = query.order_by(
                EnrichmentQueueModel.priority.asc(),
                EnrichmentQueueModel.created_at.asc()
            ).limit(limit).all()
            
            return [self._to_domain(t) for t in tasks]
            
        except Exception as e:
            logger.error(f"Failed to get pending tasks: {e}")
            return []
    
    def claim_task(self, task_id: uuid.UUID) -> bool:
        """
        Atomically claim a task by updating status to 'processing'.
        
        Args:
            task_id: Task UUID
            
        Returns:
            True if claimed successfully, False otherwise
        """
        try:
            # Atomic update - only succeeds if status is still 'pending'
            updated = self.db.query(EnrichmentQueueModel).filter(
                EnrichmentQueueModel.id == task_id,
                EnrichmentQueueModel.status == 'pending'
            ).update({
                'status': 'processing',
                'started_at': datetime.utcnow(),
                'attempts': EnrichmentQueueModel.attempts + 1
            }, synchronize_session=False)
            
            self.db.commit()
            
            if updated > 0:
                logger.debug(f"Claimed task {task_id}")
                return True
            else:
                logger.debug(f"Task {task_id} already claimed or not pending")
                return False
                
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to claim task {task_id}: {e}")
            return False
    
    def complete_task(self, task_id: uuid.UUID) -> bool:
        """
        Mark a task as complete.
        
        Args:
            task_id: Task UUID
            
        Returns:
            True if updated successfully, False otherwise
        """
        try:
            updated = self.db.query(EnrichmentQueueModel).filter(
                EnrichmentQueueModel.id == task_id
            ).update({
                'status': 'complete',
                'completed_at': datetime.utcnow(),
                'error': None
            }, synchronize_session=False)
            
            self.db.commit()
            
            if updated > 0:
                logger.debug(f"Completed task {task_id}")
                return True
            else:
                logger.warning(f"Task {task_id} not found")
                return False
                
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to complete task {task_id}: {e}")
            return False
    
    def fail_task(self, task_id: uuid.UUID, error: str) -> bool:
        """
        Mark a task as failed with error message.
        
        Args:
            task_id: Task UUID
            error: Error message
            
        Returns:
            True if updated successfully, False otherwise
        """
        try:
            updated = self.db.query(EnrichmentQueueModel).filter(
                EnrichmentQueueModel.id == task_id
            ).update({
                'status': 'failed',
                'completed_at': datetime.utcnow(),
                'error': error
            }, synchronize_session=False)
            
            self.db.commit()
            
            if updated > 0:
                logger.warning(f"Failed task {task_id}: {error}")
                return True
            else:
                logger.warning(f"Task {task_id} not found")
                return False
                
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to mark task {task_id} as failed: {e}")
            return False
    
    def enqueue(
        self,
        target_type: str,
        target_id: str,
        task_type: str,
        priority: int = 2
    ) -> Optional[uuid.UUID]:
        """
        Enqueue a new enrichment task.
        
        Args:
            target_type: Type of target (idea, exchange, session)
            target_id: Target identifier (Qdrant UUID or session_id)
            task_type: Type of enrichment task
            priority: Task priority (1=high, 2=normal, 3=low)
            
        Returns:
            Task UUID if created, None if already exists or error
        """
        try:
            # Check if task already exists (UNIQUE constraint handles this too)
            existing = self.db.query(EnrichmentQueueModel).filter(
                EnrichmentQueueModel.target_type == target_type,
                EnrichmentQueueModel.target_id == target_id,
                EnrichmentQueueModel.task_type == task_type
            ).first()
            
            if existing:
                logger.debug(f"Task already exists: {task_type} for {target_type}/{target_id}")
                return existing.id
            
            # Create new task
            task = EnrichmentQueueModel(
                target_type=target_type,
                target_id=target_id,
                task_type=task_type,
                priority=priority,
                status='pending'
            )
            
            self.db.add(task)
            self.db.commit()
            self.db.refresh(task)
            
            logger.info(f"Enqueued task: {task_type} for {target_type}/{target_id} (priority={priority})")
            return task.id
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to enqueue task {task_type} for {target_type}/{target_id}: {e}")
            return None
    
    def get_task(self, task_id: uuid.UUID) -> Optional[EnrichmentTask]:
        """
        Get a specific task by ID.
        
        Args:
            task_id: Task UUID
            
        Returns:
            EnrichmentTask if found, None otherwise
        """
        try:
            task = self.db.query(EnrichmentQueueModel).filter(
                EnrichmentQueueModel.id == task_id
            ).first()
            
            return self._to_domain(task) if task else None
            
        except Exception as e:
            logger.error(f"Failed to get task {task_id}: {e}")
            return None
    
    def reset_stale_tasks(self, max_age_minutes: int = 30) -> int:
        """
        Reset tasks that have been 'processing' for too long back to 'pending'.
        
        Args:
            max_age_minutes: Maximum age in minutes before considering stale
            
        Returns:
            Number of tasks reset
        """
        try:
            from sqlalchemy import func
            
            cutoff = datetime.utcnow()
            cutoff = cutoff.replace(minute=cutoff.minute - max_age_minutes)
            
            updated = self.db.query(EnrichmentQueueModel).filter(
                EnrichmentQueueModel.status == 'processing',
                EnrichmentQueueModel.started_at < cutoff
            ).update({
                'status': 'pending',
                'started_at': None
            }, synchronize_session=False)
            
            self.db.commit()
            
            if updated > 0:
                logger.warning(f"Reset {updated} stale tasks")
            
            return updated
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to reset stale tasks: {e}")
            return 0
    
    def _to_domain(self, task: EnrichmentQueueModel) -> EnrichmentTask:
        """Convert database model to domain model."""
        return EnrichmentTask(
            id=task.id,
            target_type=task.target_type,
            target_id=task.target_id,
            task_type=task.task_type,
            priority=task.priority,
            status=task.status,
            created_at=task.created_at,
            started_at=task.started_at,
            completed_at=task.completed_at,
            attempts=task.attempts,
            error=task.error
        )
