-- Migration 002: Add sequence number for utterance ordering within sessions
-- Date: 2026-01-18
-- Description: Adds sequence_num column to track utterance order within sessions

-- Add sequence number for utterance ordering within sessions
ALTER TABLE utterances 
ADD COLUMN IF NOT EXISTS sequence_num INTEGER;

-- Backfill existing data based on started_at timestamp
WITH numbered AS (
    SELECT id, ROW_NUMBER() OVER (
        PARTITION BY session_id 
        ORDER BY started_at, id
    ) as seq
    FROM utterances
)
UPDATE utterances u
SET sequence_num = n.seq
FROM numbered n
WHERE u.id = n.id;

-- Make not null after backfill
ALTER TABLE utterances 
ALTER COLUMN sequence_num SET NOT NULL;

-- Index for efficient sequence lookups
CREATE INDEX IF NOT EXISTS idx_utterances_session_sequence 
ON utterances(session_id, sequence_num);

-- Add comment for documentation
COMMENT ON COLUMN utterances.sequence_num IS 'Sequential order of utterance within session (1-based)';
