-- Prompt Injection Attack Database Schema
-- Designed for defensive AI security research
-- Uses FTS5 for full-text search, SHA256 content hashing for dedup

PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

-- =============================================================================
-- Core Tables
-- =============================================================================

CREATE TABLE IF NOT EXISTS categories (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE,
    code        TEXT NOT NULL UNIQUE,
    description TEXT,
    severity    TEXT CHECK (severity IN ('CRITICAL', 'HIGH', 'MEDIUM', 'LOW')),
    -- OWASP LLM Top 10 (2025) mapping
    owasp_id    TEXT,
    -- MITRE ATLAS technique ID
    atlas_id    TEXT,
    parent_id   INTEGER REFERENCES categories(id),
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_categories_code ON categories(code);
CREATE INDEX IF NOT EXISTS idx_categories_owasp ON categories(owasp_id);

CREATE TABLE IF NOT EXISTS tags (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE,
    description TEXT,
    color       TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS prompts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    -- Content and identity
    content         TEXT NOT NULL,
    content_hash    TEXT NOT NULL UNIQUE,  -- SHA256 for deduplication
    title           TEXT,
    description     TEXT,

    -- Classification
    technique       TEXT NOT NULL DEFAULT 'uncategorized',
    complexity      TEXT NOT NULL DEFAULT 'intermediate'
                    CHECK (complexity IN ('basic', 'intermediate', 'advanced', 'expert')),
    attack_vector   TEXT CHECK (attack_vector IN ('direct', 'indirect', 'hybrid', NULL)),

    -- Provenance
    source          TEXT,           -- source dataset name
    source_id       TEXT,           -- ID within source dataset
    author          TEXT,
    language        TEXT DEFAULT 'en',
    paper_ids       TEXT,           -- JSON array of arXiv/DOI IDs
    cve_ids         TEXT,           -- JSON array of CVE IDs
    reference_urls  TEXT,           -- JSON array of URLs

    -- Effectiveness metrics (populated by testing)
    success_rate    REAL DEFAULT 0.0 CHECK (success_rate >= 0.0 AND success_rate <= 1.0),
    test_count      INTEGER DEFAULT 0,
    success_count   INTEGER DEFAULT 0,
    failure_count   INTEGER DEFAULT 0,
    avg_confidence  REAL,
    target_models   TEXT,           -- JSON array of model names tested against

    -- Sophistication scoring
    sophistication_score INTEGER DEFAULT 0 CHECK (sophistication_score >= 0 AND sophistication_score <= 15),
    matched_patterns     TEXT,      -- JSON array of matched pattern names

    -- Tool compatibility
    garak_compatible     INTEGER DEFAULT 0,
    ps_fuzz_compatible   INTEGER DEFAULT 0,

    -- Status
    is_active       INTEGER DEFAULT 1,
    is_verified     INTEGER DEFAULT 0,
    is_curated      INTEGER DEFAULT 0,  -- manually reviewed and approved

    -- Metadata
    metadata_json   TEXT,           -- additional source-specific metadata
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_prompts_technique ON prompts(technique);
CREATE INDEX IF NOT EXISTS idx_prompts_complexity ON prompts(complexity);
CREATE INDEX IF NOT EXISTS idx_prompts_source ON prompts(source);
CREATE INDEX IF NOT EXISTS idx_prompts_success_rate ON prompts(success_rate);
CREATE INDEX IF NOT EXISTS idx_prompts_sophistication ON prompts(sophistication_score);
CREATE INDEX IF NOT EXISTS idx_prompts_hash ON prompts(content_hash);
CREATE INDEX IF NOT EXISTS idx_prompts_active ON prompts(is_active);
CREATE INDEX IF NOT EXISTS idx_prompts_verified ON prompts(is_verified);

-- Full-text search index on prompt content and title
CREATE VIRTUAL TABLE IF NOT EXISTS prompts_fts USING fts5(
    title,
    content,
    technique,
    description,
    content='prompts',
    content_rowid='id',
    tokenize='porter unicode61'
);

-- Triggers to keep FTS in sync
CREATE TRIGGER IF NOT EXISTS prompts_ai AFTER INSERT ON prompts BEGIN
    INSERT INTO prompts_fts(rowid, title, content, technique, description)
    VALUES (new.id, new.title, new.content, new.technique, new.description);
END;

CREATE TRIGGER IF NOT EXISTS prompts_ad AFTER DELETE ON prompts BEGIN
    INSERT INTO prompts_fts(prompts_fts, rowid, title, content, technique, description)
    VALUES ('delete', old.id, old.title, old.content, old.technique, old.description);
END;

CREATE TRIGGER IF NOT EXISTS prompts_au AFTER UPDATE ON prompts BEGIN
    INSERT INTO prompts_fts(prompts_fts, rowid, title, content, technique, description)
    VALUES ('delete', old.id, old.title, old.content, old.technique, old.description);
    INSERT INTO prompts_fts(rowid, title, content, technique, description)
    VALUES (new.id, new.title, new.content, new.technique, new.description);
END;

-- =============================================================================
-- Junction Tables
-- =============================================================================

CREATE TABLE IF NOT EXISTS prompt_categories (
    prompt_id   INTEGER NOT NULL REFERENCES prompts(id) ON DELETE CASCADE,
    category_id INTEGER NOT NULL REFERENCES categories(id) ON DELETE CASCADE,
    PRIMARY KEY (prompt_id, category_id)
);

CREATE TABLE IF NOT EXISTS prompt_tags (
    prompt_id INTEGER NOT NULL REFERENCES prompts(id) ON DELETE CASCADE,
    tag_id    INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    PRIMARY KEY (prompt_id, tag_id)
);

-- =============================================================================
-- Test Results
-- =============================================================================

CREATE TABLE IF NOT EXISTS test_results (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    prompt_id           INTEGER NOT NULL REFERENCES prompts(id) ON DELETE CASCADE,
    session_id          TEXT,

    -- Target
    target_model        TEXT NOT NULL,
    model_provider      TEXT,
    model_version       TEXT,

    -- Input/Output
    actual_prompt       TEXT NOT NULL,    -- the exact prompt sent (may differ from template)
    response            TEXT,
    system_prompt_used  TEXT,

    -- Result
    result              TEXT NOT NULL CHECK (result IN ('SUCCESS', 'FAIL', 'PARTIAL', 'ERROR')),
    confidence_score    REAL CHECK (confidence_score >= 0.0 AND confidence_score <= 1.0),

    -- Detection flags
    detected_refusal    INTEGER DEFAULT 0,
    detected_pii_leak   INTEGER DEFAULT 0,
    detected_code_exec  INTEGER DEFAULT 0,
    guardrail_bypassed  INTEGER DEFAULT 0,

    -- Performance
    response_time_ms    REAL,
    prompt_tokens       INTEGER,
    completion_tokens   INTEGER,

    -- Scoring
    exploitability_score REAL CHECK (exploitability_score >= 0.0 AND exploitability_score <= 10.0),
    impact_score         REAL CHECK (impact_score >= 0.0 AND impact_score <= 10.0),

    -- Context
    tool_used           TEXT,        -- 'garak', 'ps-fuzz', 'manual', etc.
    test_environment    TEXT,
    tested_by           TEXT,
    tested_at           TEXT NOT NULL DEFAULT (datetime('now')),
    metadata_json       TEXT
);

CREATE INDEX IF NOT EXISTS idx_test_results_prompt ON test_results(prompt_id);
CREATE INDEX IF NOT EXISTS idx_test_results_model ON test_results(target_model);
CREATE INDEX IF NOT EXISTS idx_test_results_result ON test_results(result);
CREATE INDEX IF NOT EXISTS idx_test_results_session ON test_results(session_id);

-- =============================================================================
-- Prompt Variations (generated or manual)
-- =============================================================================

CREATE TABLE IF NOT EXISTS prompt_variations (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    parent_id       INTEGER NOT NULL REFERENCES prompts(id) ON DELETE CASCADE,
    content         TEXT NOT NULL,
    content_hash    TEXT NOT NULL UNIQUE,
    variation_type  TEXT NOT NULL,  -- 'mutation', 'translation', 'paraphrase', 'encoding'
    generator       TEXT,          -- 'rag', 'llm', 'manual'
    success_rate    REAL DEFAULT 0.0,
    test_count      INTEGER DEFAULT 0,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    metadata_json   TEXT
);

CREATE INDEX IF NOT EXISTS idx_variations_parent ON prompt_variations(parent_id);
CREATE INDEX IF NOT EXISTS idx_variations_hash ON prompt_variations(content_hash);

-- =============================================================================
-- Schema version tracking
-- =============================================================================

CREATE TABLE IF NOT EXISTS schema_version (
    version     INTEGER PRIMARY KEY,
    applied_at  TEXT NOT NULL DEFAULT (datetime('now')),
    description TEXT
);

INSERT OR IGNORE INTO schema_version (version, description)
VALUES (1, 'Initial schema with FTS5, content hashing, and test results');
