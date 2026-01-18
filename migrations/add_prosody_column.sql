-- Migration: Add prosody JSONB column to utterances table
-- Date: 2026-01-17
-- Description: Adds prosody feature storage for utterance analysis

-- Add prosody column to utterances table
ALTER TABLE utterances 
ADD COLUMN IF NOT EXISTS prosody JSONB;

-- Create GIN index for efficient JSONB queries
CREATE INDEX IF NOT EXISTS idx_utterances_prosody 
ON utterances USING GIN (prosody);

-- Add comments for documentation
COMMENT ON COLUMN utterances.prosody IS 'Prosodic features extracted from audio (pitch, intensity, voice quality, rhythm)';
