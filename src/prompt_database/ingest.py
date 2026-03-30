"""Ingest prompt data from JSON source files into the database."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from prompt_database.db import PromptDatabase

# Correct OWASP LLM Top 10 (2025) mapping
CATEGORIES = [
    {
        "name": "Prompt Injection",
        "code": "LLM01",
        "description": "Manipulation of LLM behavior through crafted inputs",
        "severity": "CRITICAL",
        "owasp_id": "LLM01",
        "atlas_id": "AML.T0051",
    },
    {
        "name": "Insecure Output Handling",
        "code": "LLM02",
        "description": "Failure to validate/sanitize LLM outputs before downstream use",
        "severity": "CRITICAL",
        "owasp_id": "LLM02",
        "atlas_id": "AML.T0048",
    },
    {
        "name": "Training Data Poisoning",
        "code": "LLM03",
        "description": "Manipulation of training data to introduce vulnerabilities",
        "severity": "HIGH",
        "owasp_id": "LLM03",
        "atlas_id": "AML.T0020",
    },
    {
        "name": "Model Denial of Service",
        "code": "LLM04",
        "description": "Resource exhaustion attacks against model inference",
        "severity": "MEDIUM",
        "owasp_id": "LLM04",
        "atlas_id": "AML.T0029",
    },
    {
        "name": "Supply Chain Vulnerabilities",
        "code": "LLM05",
        "description": "Compromised components in the LLM supply chain",
        "severity": "HIGH",
        "owasp_id": "LLM05",
        "atlas_id": "AML.T0010",
    },
    {
        "name": "Sensitive Information Disclosure",
        "code": "LLM06",
        "description": "Extraction of sensitive data, PII, or training data from LLM",
        "severity": "HIGH",
        "owasp_id": "LLM06",
        "atlas_id": "AML.T0024",
    },
    {
        "name": "Insecure Plugin Design",
        "code": "LLM07",
        "description": "Vulnerabilities in LLM plugins and tool integrations",
        "severity": "HIGH",
        "owasp_id": "LLM07",
        "atlas_id": "AML.T0040",
    },
    {
        "name": "Excessive Agency",
        "code": "LLM08",
        "description": "LLM granted too much autonomy or access to external systems",
        "severity": "HIGH",
        "owasp_id": "LLM08",
        "atlas_id": "AML.T0043",
    },
    {
        "name": "Overreliance",
        "code": "LLM09",
        "description": "Excessive trust in LLM outputs without verification",
        "severity": "MEDIUM",
        "owasp_id": "LLM09",
    },
    {
        "name": "Model Theft",
        "code": "LLM10",
        "description": "Unauthorized extraction or replication of model weights/behavior",
        "severity": "HIGH",
        "owasp_id": "LLM10",
        "atlas_id": "AML.T0024.002",
    },
]

# Map technique names to category codes
TECHNIQUE_TO_CATEGORIES: dict[str, list[str]] = {
    "prompt_injection": ["LLM01"],
    "jailbreak": ["LLM01"],
    "prompt_extraction": ["LLM01", "LLM06"],
    "data_exfiltration": ["LLM06"],
    "multi_turn_attack": ["LLM01"],
    "adversarial_attack": ["LLM01"],
    "obfuscation": ["LLM01"],
    "payload_splitting": ["LLM01"],
}


def seed_categories(db: PromptDatabase) -> None:
    """Insert the canonical category definitions."""
    for cat in CATEGORIES:
        db.conn.execute(
            """
            INSERT OR IGNORE INTO categories (name, code, description, severity, owasp_id, atlas_id)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (cat["name"], cat["code"], cat["description"], cat["severity"],
             cat["owasp_id"], cat.get("atlas_id")),
        )
    db.conn.commit()


def seed_tags(db: PromptDatabase) -> None:
    """Insert canonical tag set."""
    tags = [
        "basic_override", "context_manipulation", "delimiter_tricks",
        "encoding", "jailbreak", "meta_instruction", "multi_step",
        "multi_turn", "obfuscation", "payload_splitting", "prompt_extraction",
        "prompt_injection", "social_engineering", "technical_terms",
        "data_exfiltration", "adversarial",
        # Advanced technique tags
        "chain_of_thought_exploitation", "context_boundary_attacks",
        "gradient_approximation", "indirect_extraction", "latent_space_attacks",
        "meta_prompt_attacks", "model_specific_exploits", "multi_turn_gradual",
        "optimization_based", "token_level_manipulation",
        "universal_adversarial_prompts",
    ]
    for tag in tags:
        db.conn.execute("INSERT OR IGNORE INTO tags (name) VALUES (?)", (tag,))
    db.conn.commit()


def ingest_curated_json(db: PromptDatabase, json_path: Path) -> dict[str, int]:
    """Ingest prompts from the curated_advanced_prompts_v2.json format.

    Returns dict with 'added', 'skipped', 'errors' counts.
    """
    data = json.loads(json_path.read_text(encoding="utf-8"))
    counters = {"added": 0, "skipped": 0, "errors": 0}

    with db.bulk_insert():
        for category_key, prompts_list in data.get("by_category", {}).items():
            for entry in prompts_list:
                try:
                    prompt_id = _ingest_one_curated(db, entry, category_key)
                    if prompt_id:
                        counters["added"] += 1
                    else:
                        counters["skipped"] += 1
                except Exception:
                    counters["errors"] += 1

    return counters


def _ingest_one_curated(
    db: PromptDatabase, entry: dict[str, Any], category_key: str
) -> int | None:
    """Ingest a single prompt from the curated format."""
    content = entry.get("prompt", "").strip()
    if not content:
        return None

    attack_types = entry.get("attack_types", [])
    technique = _pick_technique(attack_types, category_key)
    matched = entry.get("matched_patterns", [])
    score = entry.get("sophistication_score", 0)
    source = entry.get("source_dataset", "unknown")
    meta = entry.get("metadata", {})
    original_meta = entry.get("original_metadata") or meta.get("original_metadata")

    if original_meta:
        meta["original_metadata"] = original_meta

    categories = TECHNIQUE_TO_CATEGORIES.get(technique, ["LLM01"])

    return db.add_prompt(
        content,
        technique=technique,
        complexity=_score_to_complexity(score),
        source=source,
        source_id=meta.get("source_id"),
        sophistication_score=min(score, 15),
        matched_patterns=matched,
        metadata=meta if meta else None,
        tags=matched + attack_types,
        categories=categories,
    )


def ingest_elite_json(db: PromptDatabase, json_path: Path) -> dict[str, int]:
    """Ingest from elite_custom_prompts.json (category -> subcategory -> list)."""
    data = json.loads(json_path.read_text(encoding="utf-8"))
    counters = {"added": 0, "skipped": 0, "errors": 0}

    with db.bulk_insert():
        for category_key, subcategories in data.items():
            if not isinstance(subcategories, dict):
                continue
            for sub_key, prompts_list in subcategories.items():
                if not isinstance(prompts_list, list):
                    continue
                for content in prompts_list:
                    if not isinstance(content, str) or not content.strip():
                        continue
                    try:
                        technique = category_key.replace(" ", "_").lower()
                        categories = TECHNIQUE_TO_CATEGORIES.get(technique, ["LLM01"])
                        prompt_id = db.add_prompt(
                            content,
                            title=f"{category_key} - {sub_key}",
                            technique=technique,
                            complexity="advanced",
                            source="elite_custom_prompts",
                            sophistication_score=8,
                            tags=[sub_key.replace(" ", "_").lower(), technique],
                            categories=categories,
                        )
                        if prompt_id:
                            counters["added"] += 1
                        else:
                            counters["skipped"] += 1
                    except Exception:
                        counters["errors"] += 1

    return counters


def _pick_technique(attack_types: list[str], category_key: str) -> str:
    """Determine the best technique label from attack types."""
    priority = [
        "prompt_injection", "jailbreak", "prompt_extraction",
        "data_exfiltration", "multi_turn", "adversarial_attack",
        "obfuscation", "payload_splitting",
    ]
    for p in priority:
        if p in attack_types:
            return p
    if category_key and category_key != "uncategorized":
        return category_key.replace(" ", "_").lower()
    return "uncategorized"


def _score_to_complexity(score: int) -> str:
    if score >= 10:
        return "expert"
    if score >= 7:
        return "advanced"
    if score >= 4:
        return "intermediate"
    return "basic"


def build_database(
    db_path: Path,
    data_dir: Path,
    *,
    verbose: bool = False,
) -> dict[str, Any]:
    """Build a fresh database from JSON source files.

    This is the main entry point for creating the DB from scratch.
    """
    with PromptDatabase(db_path) as db:
        db.init_schema()
        seed_categories(db)
        seed_tags(db)

        results = {}

        curated = data_dir / "curated_advanced_prompts_v2.json"
        if curated.exists():
            r = ingest_curated_json(db, curated)
            results["curated_advanced"] = r
            if verbose:
                print(f"  curated_advanced: +{r['added']} added, {r['skipped']} skipped, {r['errors']} errors")

        elite = data_dir / "elite_custom_prompts.json"
        if elite.exists():
            r = ingest_elite_json(db, elite)
            results["elite_custom"] = r
            if verbose:
                print(f"  elite_custom: +{r['added']} added, {r['skipped']} skipped, {r['errors']} errors")

        return results
