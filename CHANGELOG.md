# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-03-30

### Added
- **Python package** (`prompt-database`) installable via `pip install -e .`
- **`prompt-db` CLI** with commands: `build`, `stats`, `search`, `export`, `info`, `audit`, `curate`
- **SQLite schema** with FTS5 full-text search, SHA256 content-hash deduplication, and schema versioning
- **OWASP LLM Top 10 (2025)** category mapping with correct descriptions
- **MITRE ATLAS** technique IDs on categories for threat model interoperability
- **Quality scoring engine** with 60+ regex patterns for identifying real attacks vs. noise
- **Data curation pipeline** — audit and remove non-attack content (removes ~67% noise)
- **Ingestion pipeline** for `curated_advanced_prompts_v2.json` and `elite_custom_prompts.json`
- **Test result tracking** with automatic success_rate aggregation
- **19 passing tests** covering schema, CRUD, search, dedup, quality, and build
- **Export** to JSON, JSONL, and CSV formats

### Changed
- Database is now built from JSON sources via `prompt-db build` (no longer committed as binary)
- Deduplication reduced 8,568 records to 3,983 unique prompts
- Quality curation further reduces to ~1,300 high-signal attack prompts

### Removed
- Binary `prompts.db` from git tracking (build it yourself from JSON sources)
- Phantom file references in README (db_manager.py, schema.sql, etc. that never existed)

[0.1.0]: https://github.com/scthornton/prompt-database/releases/tag/v0.1.0
