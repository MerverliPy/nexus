-- Initialize pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Create indexes for common queries
-- (Additional indexes will be created via Alembic migrations)
