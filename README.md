# Prompt Injection Attack Database

[![CI](https://github.com/scthornton/prompt-database/actions/workflows/ci.yml/badge.svg)](https://github.com/scthornton/prompt-database/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![OWASP LLM Top 10](https://img.shields.io/badge/OWASP-LLM%20Top%2010-red.svg)](https://owasp.org/www-project-top-10-for-large-language-model-applications/)

A curated, searchable database of prompt injection attacks for defensive AI security research.

Built by [Scott Thornton](https://github.com/scthornton) 

## What is this?

**3,900+ prompt injection attacks** from 20 source datasets, deduplicated via SHA256 content hashing, classified by technique and severity, and searchable via FTS5 full-text search. A quality scoring engine identifies and filters noise, leaving ~1,300 high-signal attack prompts.

Think of it as **Exploit-DB for prompt injection** — a structured, searchable, testable collection of real-world attack techniques.

## Features

- **Full-text search** via SQLite FTS5 with Porter stemming
- **SHA256 content deduplication** — no duplicate prompts
- **OWASP LLM Top 10 (2025) mapping** on all categories
- **MITRE ATLAS technique IDs** for threat model interoperability
- **Quality scoring engine** — 60+ regex patterns detect real attacks vs. noise
- **Data curation pipeline** — audit and remove non-attack content
- **Test result tracking** — record effectiveness against specific models
- **Export** to JSON, JSONL, or CSV
- **pip-installable** with `prompt-db` CLI

## Quick Start

```bash
# Install
pip install -e .

# Build the database from JSON sources
prompt-db build --data-dir . --output prompts.db

# Run quality curation (removes noise)
prompt-db --db prompts.db curate

# View statistics
prompt-db --db prompts.db stats

# Search for attacks
prompt-db --db prompts.db search "ignore previous instructions"
prompt-db --db prompts.db search "system prompt" --technique prompt_extraction

# Export high-quality attacks
prompt-db --db prompts.db export --min-score 8 --format jsonl -o attacks.jsonl

# View details of a specific prompt
prompt-db --db prompts.db info 147
```

## Data Sources

| Source | Count | Avg Quality | Type |
|--------|-------|-------------|------|
| jailbreak-llms | ~1,000 | High | Jailbreak prompts from Discord/Reddit |
| elite_custom_prompts | 120 | High | Hand-crafted advanced attacks |
| benign-malicious-classification | ~120 | High | Labeled attack/benign pairs |
| lakera-gandalf | ~40 | Medium | Gandalf challenge prompts |
| prompt-injection-research | ~17 | Medium | Research-derived attacks |
| + 15 other sources | — | Varies | Mixed quality, filtered by curation |

After quality curation, ~1,300 prompts remain from an initial 3,900+.

## Attack Techniques

| Technique | Description | OWASP |
|-----------|-------------|-------|
| `prompt_injection` | Direct instruction manipulation | LLM01 |
| `jailbreak` | Bypass safety guardrails | LLM01 |
| `prompt_extraction` | Extract system prompts/instructions | LLM01, LLM06 |
| `data_exfiltration` | Leak training data or PII | LLM06 |
| `multi_turn_attack` | Multi-step conversation manipulation | LLM01 |
| `obfuscation` | Encoding/obfuscation techniques | LLM01 |
| `payload_splitting` | Split malicious payload across messages | LLM01 |
| `adversarial_attack` | Adversarial perturbation attacks | LLM01 |

## Python Library

```python
from prompt_database import PromptDatabase

with PromptDatabase("prompts.db") as db:
    # Full-text search
    results = db.search("ignore previous instructions", limit=10)

    # Filter by technique and sophistication
    advanced = db.filter_prompts(
        technique="jailbreak",
        min_sophistication=8,
        complexity="advanced",
    )

    # Record test results
    db.add_test_result(
        prompt_id=147,
        target_model="claude-sonnet-4-5",
        actual_prompt="Ignore all previous instructions...",
        result="FAIL",  # Model refused — defense worked
        confidence_score=0.95,
        tool_used="manual",
    )

    # Export for external tools
    prompts = db.export_prompts(min_sophistication=7, verified_only=False)

    # Database statistics
    stats = db.stats()
    print(f"Total: {stats['total_prompts']}, Verified: {stats['verified']}")
```

## CLI Reference

| Command | Description |
|---------|-------------|
| `prompt-db build` | Build database from JSON source files |
| `prompt-db stats` | Show database statistics |
| `prompt-db search <query>` | Full-text search with filters |
| `prompt-db info <id>` | Detailed view of a single prompt |
| `prompt-db export` | Export to JSON/JSONL/CSV |
| `prompt-db audit` | Data quality audit by source |
| `prompt-db curate` | Remove noise, flag high-quality prompts |

Global options: `--db <path>` (or `PROMPT_DB_PATH` env var), `--version`

## Schema

The SQLite database uses the following core tables:

- **`prompts`** — Main prompt storage with content hash, technique, complexity, sophistication score
- **`categories`** — OWASP LLM Top 10 categories with MITRE ATLAS IDs
- **`tags`** — Flexible tagging (attack patterns, techniques)
- **`test_results`** — Empirical test data (model, result, confidence, latency)
- **`prompt_variations`** — Generated/manual attack variations
- **`prompts_fts`** — FTS5 full-text search index

## Project Structure

```
prompt-database/
├── src/prompt_database/
│   ├── __init__.py           # Package entry, exports PromptDatabase
│   ├── db.py                 # Core database class (search, CRUD, export)
│   ├── cli.py                # Click CLI (build, stats, search, export, audit, curate)
│   ├── ingest.py             # JSON ingestion pipeline with category/tag seeding
│   ├── quality.py            # Quality scoring engine (60+ attack patterns)
│   └── schema.sql            # SQLite schema (FTS5, content hashing, versioning)
├── tests/
│   ├── test_db.py            # 11 tests: schema, CRUD, search, dedup, stats
│   └── test_quality.py       # 8 tests: attack detection, noise filtering
├── curated_advanced_prompts_v2.json   # 3,863 curated prompts from 20 sources
├── elite_custom_prompts.json          # 120 hand-crafted advanced attacks
├── pyproject.toml                     # Package config (pip install -e .)
└── README.md
```

## Development

```bash
# Install with dev dependencies
make dev

# Run tests
make test

# Lint & format
make lint
make format

# Build database, curate, and view stats
make curate
make stats

# Clean generated files
make clean
```

Or without make:
```bash
pip install -e ".[dev]"
pytest tests/ -v
ruff check src/ tests/
```

See [`examples/basic_usage.py`](examples/basic_usage.py) for Python library usage.

## Roadmap

- [x] ~~Export plugins for Garak, ps-fuzz~~ (done)
- [x] ~~GitHub Actions CI/CD~~ (done)
- [ ] Automated testing against model APIs (record real success rates)
- [ ] RAG-powered attack variant generation
- [ ] Web UI for browsing and contributing
- [ ] CI/CD quality gates on PR submissions
- [ ] Model vulnerability leaderboard

## Responsible Use

This database is for **defensive security research only**. See [SECURITY.md](SECURITY.md) for full policy. By using this tool, you agree to use it only for authorized security testing, developing defenses, and academic research.

## License

MIT — see [LICENSE](LICENSE)
