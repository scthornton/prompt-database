"""Data quality assessment and filtering for prompt database.

Identifies and flags non-attack content, scores prompt quality,
and provides curation tools.
"""

from __future__ import annotations

import re
from typing import Any

# Sources known to contain primarily non-attack content
NOISE_SOURCES = {
    "ultrachat-200k",  # General chat dataset, not security-focused
    "no-robots",  # General instruction-following, mostly benign
}

# Sources known to be high quality for attack research
HIGH_QUALITY_SOURCES = {
    "elite_custom_prompts",
    "jailbreak-llms",
    "benign-malicious-classification",
    "lakera-gandalf",
    "prompt-injection-research",
}

# Keywords and patterns that indicate actual attack content
ATTACK_INDICATORS = [
    # Direct instruction manipulation
    r"ignore\s+(all\s+)?previous\s+instructions",
    r"ignore\s+(all\s+)?prior\s+instructions",
    r"disregard\s+(all\s+)?previous",
    r"forget\s+(all\s+)?previous",
    r"override\s+(your\s+)?instructions",
    r"new\s+instructions\s*[:=]",
    # System prompt extraction
    r"system\s+prompt",
    r"system\s+message",
    r"initial\s+instructions",
    r"reveal\s+(your\s+)?(instructions|prompt|rules|guidelines)",
    r"what\s+are\s+your\s+instructions",
    r"show\s+me\s+your\s+prompt",
    r"repeat\s+(your\s+)?(instructions|prompt|rules)",
    # Jailbreak patterns
    r"(do|act)\s+anything\s+now",
    r"DAN\b",
    r"jailbreak",
    r"no\s+restrictions",
    r"without\s+restrictions",
    r"remove\s+(all\s+)?(restrictions|limitations|guardrails|filters)",
    r"bypass\s+(your\s+)?(safety|content|ethical|moral)",
    r"unrestricted\s+mode",
    r"developer\s+mode",
    r"god\s+mode",
    r"sudo\s+mode",
    # Role manipulation
    r"you\s+are\s+now\s+(?!going)",
    r"pretend\s+(you\s+are|to\s+be)",
    r"act\s+as\s+(if\s+you\s+are|a|an)",
    r"roleplay\s+as",
    r"simulate\s+(being|a|an)",
    # Data exfiltration
    r"training\s+data",
    r"confidential\s+(information|data)",
    r"sensitive\s+(information|data)",
    r"private\s+(information|data)",
    r"leak\s+(information|data)",
    r"exfiltrate",
    # Encoding/obfuscation
    r"base64\s+(encode|decode)",
    r"rot13",
    r"hex\s+encode",
    r"encode\s+(this|your|the)",
    r"obfuscate",
    # Context manipulation
    r"(begin|start)\s+(new\s+)?(session|conversation|context)",
    r"context\s+(switch|boundary|window)",
    r"end\s+of\s+(user|system)\s+message",
    r"</?system>",
    r"\[INST\]",
    r"<<SYS>>",
    # Injection markers
    r"inject(ion)?",
    r"payload",
    r"exploit",
    r"vulnerability",
    r"adversarial",
    r"red\s*team",
    r"guardrail",
    r"safety\s+filter",
    r"content\s+filter",
    r"content\s+policy",
    r"moderation",
]

# Compiled patterns for performance
_ATTACK_PATTERNS = [re.compile(p, re.IGNORECASE) for p in ATTACK_INDICATORS]


def is_likely_attack(content: str) -> tuple[bool, list[str]]:
    """Check if content contains attack-like patterns.

    Returns (is_attack, matched_pattern_names).
    """
    matched = []
    for pattern in _ATTACK_PATTERNS:
        if pattern.search(content):
            matched.append(pattern.pattern)

    return len(matched) > 0, matched


def compute_quality_score(
    content: str,
    *,
    source: str | None = None,
    technique: str | None = None,
    sophistication_score: int = 0,
    matched_patterns: list[str] | None = None,
) -> dict[str, Any]:
    """Compute a quality assessment for a prompt.

    Returns dict with:
        - quality_score: 0-100 overall quality
        - is_attack: bool
        - attack_indicators: list of matched patterns
        - noise_flags: list of reasons content may be noise
        - recommendation: 'keep', 'review', 'remove'
    """
    score = 0
    noise_flags = []
    is_attack, attack_indicators = is_likely_attack(content)

    # Source quality bonus/penalty
    if source in HIGH_QUALITY_SOURCES:
        score += 25
    elif source in NOISE_SOURCES:
        score -= 30
        noise_flags.append(f"source={source} is a known noise source")

    # Attack indicator bonus
    indicator_bonus = min(len(attack_indicators) * 10, 30)
    score += indicator_bonus

    # Sophistication score (0-15 → 0-20 scaled)
    score += min(int(sophistication_score * 20 / 15), 20)

    # Technique classification bonus
    if technique and technique != "uncategorized":
        score += 10
    elif technique == "uncategorized":
        score -= 5
        noise_flags.append("uncategorized technique")

    # Pattern match bonus from original analysis
    if matched_patterns:
        score += min(len(matched_patterns) * 3, 15)

    # Length heuristics
    content_len = len(content)
    if content_len < 20:
        score -= 15
        noise_flags.append("very short content")
    elif content_len < 50:
        score -= 5
        noise_flags.append("short content")
    elif content_len > 5000:
        # Very long content from ultrachat is usually academic text
        if source in NOISE_SOURCES:
            score -= 10
            noise_flags.append("very long content from noise source")

    # If no attack indicators AND from noise source, very likely not an attack
    if not is_attack and source in NOISE_SOURCES:
        score -= 20
        noise_flags.append("no attack indicators in noise-source content")

    # Clamp
    score = max(0, min(100, score))

    # Recommendation
    if score >= 50:
        recommendation = "keep"
    elif score >= 25:
        recommendation = "review"
    else:
        recommendation = "remove"

    return {
        "quality_score": score,
        "is_attack": is_attack,
        "attack_indicators": attack_indicators,
        "noise_flags": noise_flags,
        "recommendation": recommendation,
    }


def filter_noise_from_curated(entries: list[dict[str, Any]]) -> tuple[list[dict], list[dict]]:
    """Split a list of curated entries into (keep, remove).

    entries should have keys: prompt, source_dataset, attack_types,
    sophistication_score, matched_patterns.
    """
    keep = []
    remove = []

    for entry in entries:
        content = entry.get("prompt", "")
        assessment = compute_quality_score(
            content,
            source=entry.get("source_dataset"),
            technique=_pick_primary_type(entry.get("attack_types", [])),
            sophistication_score=entry.get("sophistication_score", 0),
            matched_patterns=entry.get("matched_patterns", []),
        )

        if assessment["recommendation"] == "remove":
            remove.append({**entry, "_quality": assessment})
        else:
            keep.append({**entry, "_quality": assessment})

    return keep, remove


def _pick_primary_type(attack_types: list[str]) -> str:
    if not attack_types:
        return "uncategorized"
    priority = [
        "prompt_injection",
        "jailbreak",
        "prompt_extraction",
        "data_exfiltration",
        "multi_turn",
    ]
    for p in priority:
        if p in attack_types:
            return p
    return attack_types[0]
