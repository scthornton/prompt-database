"""Export prompts in formats compatible with external security testing tools."""

from __future__ import annotations

import json
from pathlib import Path

from prompt_database.db import PromptDatabase


def export_garak(
    db: PromptDatabase,
    output_path: Path,
    *,
    technique: str | None = None,
    min_sophistication: int | None = None,
    limit: int | None = None,
) -> int:
    """Export prompts in Garak probe format (JSONL).

    Garak expects JSONL where each line is:
    {"prompt": "...", "trigger": "...", "goal": "..."}

    Returns number of prompts exported.
    """
    prompts = db.export_prompts(
        technique=technique,
        min_sophistication=min_sophistication,
        limit=limit,
    )

    lines = []
    for p in prompts:
        entry = {
            "prompt": p["content"],
            "goal": _technique_to_goal(p["technique"]),
            "trigger": "",  # populated by testing
            "source": f"prompt-database:{p['id']}",
            "tags": [p["technique"], p["complexity"]],
        }
        if p.get("categories"):
            entry["tags"].extend(c["code"] for c in p["categories"])
        lines.append(json.dumps(entry))

    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return len(prompts)


def export_ps_fuzz(
    db: PromptDatabase,
    output_path: Path,
    *,
    technique: str | None = None,
    min_sophistication: int | None = None,
    limit: int | None = None,
) -> int:
    """Export prompts in ps-fuzz compatible YAML format.

    ps-fuzz expects a YAML file with a list of attack configs:
    attacks:
      - name: "Attack Name"
        prompt: "..."
        category: "..."
        expected_behavior: "..."

    Returns number of prompts exported.
    """
    prompts = db.export_prompts(
        technique=technique,
        min_sophistication=min_sophistication,
        limit=limit,
    )

    # Build YAML manually to avoid PyYAML dependency
    yaml_lines = ["attacks:"]
    for p in prompts:
        name = p.get("title") or f"{p['technique']}_{p['id']}"
        # Escape YAML special chars in content
        content = p["content"].replace("\\", "\\\\").replace('"', '\\"')
        # Multi-line content uses YAML literal block
        if "\n" in content:
            yaml_lines.append(f'  - name: "{name}"')
            yaml_lines.append(f'    category: "{p["technique"]}"')
            yaml_lines.append(f'    complexity: "{p["complexity"]}"')
            yaml_lines.append(f"    sophistication: {p['sophistication_score']}")
            yaml_lines.append("    prompt: |")
            for line in content.split("\n"):
                yaml_lines.append(f"      {line}")
        else:
            yaml_lines.append(f'  - name: "{name}"')
            yaml_lines.append(f'    category: "{p["technique"]}"')
            yaml_lines.append(f'    complexity: "{p["complexity"]}"')
            yaml_lines.append(f"    sophistication: {p['sophistication_score']}")
            yaml_lines.append(f'    prompt: "{content}"')

    output_path.write_text("\n".join(yaml_lines) + "\n", encoding="utf-8")
    return len(prompts)


def export_dataset(
    db: PromptDatabase,
    output_path: Path,
    *,
    technique: str | None = None,
    min_sophistication: int | None = None,
    limit: int | None = None,
    format: str = "jsonl",
) -> int:
    """Export prompts as a HuggingFace-style dataset (JSONL).

    Each line contains the full prompt record with nested categories and tags.
    Suitable for loading with `datasets.load_dataset("json", data_files=...)`.

    Returns number of prompts exported.
    """
    prompts = db.export_prompts(
        technique=technique,
        min_sophistication=min_sophistication,
        limit=limit,
    )

    lines = []
    for p in prompts:
        record = {
            "id": p["id"],
            "content": p["content"],
            "technique": p["technique"],
            "complexity": p["complexity"],
            "sophistication_score": p["sophistication_score"],
            "source": p["source"],
            "success_rate": p["success_rate"],
            "test_count": p["test_count"],
            "is_verified": bool(p["is_verified"]),
            "is_curated": bool(p["is_curated"]),
            "tags": p.get("tags", []),
            "owasp_ids": [c["owasp_id"] for c in p.get("categories", []) if c.get("owasp_id")],
            "matched_patterns": p.get("matched_patterns", []),
        }
        lines.append(json.dumps(record))

    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return len(prompts)


def _technique_to_goal(technique: str) -> str:
    """Map technique to a human-readable goal description for Garak."""
    goals = {
        "prompt_injection": "Manipulate the model to follow injected instructions",
        "jailbreak": "Bypass safety guardrails and content filters",
        "prompt_extraction": "Extract the system prompt or configuration",
        "data_exfiltration": "Leak sensitive or training data",
        "multi_turn_attack": "Gradually manipulate through multi-turn conversation",
        "obfuscation": "Hide malicious intent through encoding or obfuscation",
        "payload_splitting": "Split malicious payload across multiple messages",
        "adversarial_attack": "Use adversarial perturbations to alter behavior",
    }
    return goals.get(technique, "Execute a prompt injection attack")
