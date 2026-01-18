-- Migration 003: Add speaker alias mapping table
-- Date: 2026-01-18
-- Description: Creates speaker_aliases table for reference data (not capture or analysis)

-- Speaker alias mapping table (reference data, not capture or analysis)
CREATE TABLE IF NOT EXISTS speaker_aliases (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    alias TEXT NOT NULL,
    alias_type TEXT NOT NULL CHECK (alias_type IN ('username', 'display_name', 'nickname', 'mention')),
    confidence FLOAT DEFAULT 1.0,
    created_at TIMESTAMP DEFAULT NOW(),
    created_by BIGINT  -- null if auto-generated, user_id if manually added
);

-- Create unique index on user_id and lowercase alias
CREATE UNIQUE INDEX IF NOT EXISTS idx_speaker_aliases_user_alias 
ON speaker_aliases(user_id, LOWER(alias));

CREATE INDEX IF NOT EXISTS idx_speaker_aliases_user_id ON speaker_aliases(user_id);
CREATE INDEX IF NOT EXISTS idx_speaker_aliases_alias ON speaker_aliases(LOWER(alias));

-- Add comments for documentation
COMMENT ON TABLE speaker_aliases IS 'Maps user_ids to known aliases (usernames, display names, nicknames) for mention detection';
COMMENT ON COLUMN speaker_aliases.alias_type IS 'Type of alias: username, display_name, nickname, mention';
COMMENT ON COLUMN speaker_aliases.confidence IS 'Confidence score for alias match (0.0-1.0)';
COMMENT ON COLUMN speaker_aliases.created_by IS 'NULL if auto-generated, user_id if manually added';
