-- PostgreSQL schema for comic-translate storage with pgvector
-- Requires: CREATE EXTENSION vector;

CREATE EXTENSION IF NOT EXISTS vector;

-- Comics table: stores comic metadata and embeddings
CREATE TABLE IF NOT EXISTS comics (
    base_fp TEXT PRIMARY KEY,
    creator_id TEXT,
    work_id TEXT,
    meta_embedding VECTOR(384),
    hit_count INT DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Blocks table: stores individual text blocks with embeddings and translations
CREATE TABLE IF NOT EXISTS blocks (
    block_uid TEXT PRIMARY KEY,
    base_fp TEXT NOT NULL REFERENCES comics(base_fp) ON DELETE CASCADE,
    block_type TEXT NOT NULL,
    bbox JSONB NOT NULL,
    original_texts JSONB NOT NULL,
    translations JSONB DEFAULT '{}',
    semantic_routing JSONB,
    nsfw_flag BOOLEAN DEFAULT FALSE,
    embedding VECTOR(384),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Contributions table: tracks user edits and approvals
CREATE TABLE IF NOT EXISTS contributions (
    id SERIAL PRIMARY KEY,
    user_key TEXT NOT NULL,
    base_fp TEXT NOT NULL REFERENCES comics(base_fp) ON DELETE CASCADE,
    block_uid TEXT REFERENCES blocks(block_uid) ON DELETE CASCADE,
    manual_edits JSONB,
    approved BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Indexes for vector similarity search
CREATE INDEX IF NOT EXISTS blocks_embedding_idx
    ON blocks USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

CREATE INDEX IF NOT EXISTS comics_meta_embedding_idx
    ON comics USING ivfflat (meta_embedding vector_cosine_ops)
    WITH (lists = 100);

-- Index for fast block lookup by comic
CREATE INDEX IF NOT EXISTS blocks_base_fp_idx ON blocks(base_fp);

-- Index for contributions lookup
CREATE INDEX IF NOT EXISTS contributions_user_key_idx ON contributions(user_key);
CREATE INDEX IF NOT EXISTS contributions_base_fp_idx ON contributions(base_fp);
