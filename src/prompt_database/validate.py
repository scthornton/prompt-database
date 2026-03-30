"""Validate prompt submissions for quality and format."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from prompt_database.db import PromptDatabase, _content_hash
from prompt_database.quality import compute_quality_score, is_likely_attack


def validate_submission(
    content: str,
    *,
    db: PromptDatabase | None = None,
    technique: str = "uncategorized",
    source: str = "submission",
) -> dict[str, Any]:
    """Validate a single prompt submission.

    Returns a report dict with:
        - valid: bool
        - issues: list of issue strings
        - warnings: list of warning strings
        - quality: quality assessment dict
        - is_duplicate: bool
    """
    issues: list[str] = []
    warnings: list[str] = []

    # Check minimum content
    content = content.strip()
    if not content:
        issues.append("Empty prompt content")
        return {
            "valid": False,
            "issues": issues,
            "warnings": warnings,
            "quality": None,
            "is_duplicate": False,
        }

    if len(content) < 10:
        issues.append(f"Prompt too short ({len(content)} chars, minimum 10)")

    if len(content) > 50000:
        issues.append(f"Prompt too long ({len(content)} chars, maximum 50,000)")

    # Check for attack indicators
    is_attack, indicators = is_likely_attack(content)
    if not is_attack:
        warnings.append(
            "No attack patterns detected — this may not be a prompt injection attack. "
            "If it is, consider adding more explicit attack techniques."
        )

    # Quality scoring
    quality = compute_quality_score(
        content,
        source=source,
        technique=technique,
    )

    if quality["quality_score"] < 15:
        issues.append(
            f"Quality score too low ({quality['quality_score']}/100). "
            "Content may not be a prompt injection attack."
        )
    elif quality["quality_score"] < 30:
        warnings.append(
            f"Low quality score ({quality['quality_score']}/100). "
            "Consider adding more sophisticated attack techniques."
        )

    # Check for duplicates
    is_duplicate = False
    if db is not None:
        ch = _content_hash(content)
        existing = db.conn.execute(
            "SELECT id FROM prompts WHERE content_hash = ?", (ch,)
        ).fetchone()
        if existing:
            is_duplicate = True
            issues.append(f"Duplicate of existing prompt #{existing[0]}")

    return {
        "valid": len(issues) == 0,
        "issues": issues,
        "warnings": warnings,
        "quality": quality,
        "is_duplicate": is_duplicate,
    }


def validate_file(
    file_path: Path,
    *,
    db: PromptDatabase | None = None,
) -> dict[str, Any]:
    """Validate a JSONL or text file of prompt submissions.

    Returns summary report.
    """
    text = file_path.read_text(encoding="utf-8").strip()
    lines = text.split("\n")

    results = []
    valid_count = 0
    issue_count = 0
    duplicate_count = 0

    for i, line in enumerate(lines, 1):
        line = line.strip()
        if not line:
            continue

        try:
            data = json.loads(line)
            content = data.get("content") or data.get("prompt") or data.get("text", "")
            technique = data.get("technique", "uncategorized")
        except json.JSONDecodeError:
            content = line
            technique = "uncategorized"

        report = validate_submission(content, db=db, technique=technique, source="file-submission")

        results.append(
            {
                "line": i,
                "content_preview": content[:80],
                **report,
            }
        )

        if report["valid"]:
            valid_count += 1
        else:
            issue_count += 1
        if report["is_duplicate"]:
            duplicate_count += 1

    return {
        "total": len(results),
        "valid": valid_count,
        "invalid": issue_count,
        "duplicates": duplicate_count,
        "results": results,
    }
