-- Migration 004: Add enrichment task queue
-- Date: 2026-01-18
-- Description: Creates enrichment_queue table for operational task management (not capture)

-- Enrichment task queue (operational, not capture)
CREATE TABLE IF NOT EXISTS enrichment_queue (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    target_type TEXT NOT NULL CHECK (target_type IN ('idea', 'exchange', 'session')),
    target_id TEXT NOT NULL,  -- Qdrant UUID for ideas/exchanges, session_id for session-level tasks
    task_type TEXT NOT NULL,
    priority INTEGER NOT NULL DEFAULT 2 CHECK (priority BETWEEN 1 AND 3),
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'complete', 'failed')),
    created_at TIMESTAMP DEFAULT NOW(),
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    attempts INTEGER DEFAULT 0,
    error TEXT,
    UNIQUE(target_type, target_id, task_type)
);

CREATE INDEX IF NOT EXISTS idx_enrichment_queue_status_priority 
ON enrichment_queue(status, priority, created_at) 
WHERE status = 'pending';

CREATE INDEX IF NOT EXISTS idx_enrichment_queue_target 
ON enrichment_queue(target_type, target_id);

-- Add comments for documentation
COMMENT ON TABLE enrichment_queue IS 'Task queue for enrichment workers processing ideas and exchanges';
COMMENT ON COLUMN enrichment_queue.target_type IS 'Type of target: idea, exchange, or session';
COMMENT ON COLUMN enrichment_queue.target_id IS 'Qdrant UUID for ideas/exchanges, session_id for sessions';
COMMENT ON COLUMN enrichment_queue.task_type IS 'Type of enrichment task (e.g., alias_detection, intent_keywords)';
COMMENT ON COLUMN enrichment_queue.priority IS 'Task priority: 1=high, 2=normal, 3=low';
COMMENT ON COLUMN enrichment_queue.status IS 'Task status: pending, processing, complete, failed';
