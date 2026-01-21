# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Production-ready prompt injection attack database for defensive security research
- SQLite database schema with comprehensive attack tracking
- Content-based deduplication using SHA256 hashing
- RAG-independent design with optional RAG linkage
- Automated attack generation using RAG + LLM integration
- Multi-dimensional classification (attack vector, technique, CIA impact)
- Research-grade tracking (paper IDs, CVEs, success rates, defenses)
- Direct integration with ps-fuzz and AI-Agent Scanner testing tools

### Database Schema
- **attacks** table: Main attack storage with UUID primary keys and content hashing
- **testing_results** table: Empirical test data from security tools
- **detection_signatures** table: Defense patterns and signature types
- **attack_relationships** table: Evolution tracking and parent/child lineage
- **defenses** table: Mitigation strategies and effectiveness scores
- **rag_references** table: Optional content-based RAG linkage (rebuildable)

### Core Features
- **Content Addressing**: SHA256 hashes for stable, path-independent identification
- **RAG Independence**: Database works without RAG; RAG enhances but isn't required
- **Flexible References**: RAG links can be rebuilt after reorganization
- **Multi-Dimensional Queries**: Attack vector × technique × CIA impact
- **Tool Integration**: ps-fuzz compatible, AI-Agent Scanner compatible
- **Automated Generation**: RAG + LLM powered attack variant generation

### Python Modules
- `db_manager.py`: Core database manager class with CRUD operations
- `ingest_curated_prompts.py`: Import existing prompt collections
- `rag_prompt_generator.py`: RAG-powered attack generation
- `rag_relinker.py`: Rebuild RAG links after reorganization
- `schema.sql`: Complete database schema definition

### Integration Capabilities
- **ps-fuzz Integration**: Direct attack export for fuzzer testing
- **AI-Agent Scanner Integration**: Compatible attack format
- **RAG System Integration**: Pluggable RAG query functions
- **LLM Integration**: Pluggable LLM generation functions

### Research Features
- Paper ID tracking for academic citations
- CVE ID tracking for vulnerability references
- Success rate metrics across tested models
- Tested model tracking (GPT-4, Claude-3.5, Gemini-Pro, etc.)
- Tag-based categorization and search

### Workflow Support
- Weekly testing cycle workflows
- Paper-to-database pipeline
- Continuous attack generation
- Database gap filling automation
- Export and backup functionality

### Documentation
- Comprehensive README with usage examples
- Query examples and workflows
- Integration guides for ps-fuzz and AI-Agent Scanner
- RAG reorganization procedures
- Database maintenance schedules

[Unreleased]: https://github.com/scthornton/prompt-database/commits/main
