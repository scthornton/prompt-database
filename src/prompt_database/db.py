"""Core database manager for the prompt injection attack database."""

from __future__ import annotations

import hashlib
import importlib.resources
import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any


def _content_hash(text: str) -> str:
    """SHA256 hash of prompt content for deduplication."""
    return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()


class PromptDatabase:
    """Interface to the prompt injection attack SQLite database.

    Usage:
        with PromptDatabase("prompts.db") as db:
            results = db.search("ignore previous instructions")
    """

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self._conn: sqlite3.Connection | None = None

    def __enter__(self) -> PromptDatabase:
        self.connect()
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def connect(self) -> None:
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            raise RuntimeError("Database not connected. Use 'with PromptDatabase(path) as db:'")
        return self._conn

    # =========================================================================
    # Schema management
    # =========================================================================

    def init_schema(self) -> None:
        """Create all tables, indexes, and FTS from schema.sql."""
        schema_sql = importlib.resources.files("prompt_database").joinpath("schema.sql").read_text()
        self.conn.executescript(schema_sql)

    def schema_version(self) -> int:
        """Return current schema version, or 0 if not initialized."""
        try:
            row = self.conn.execute("SELECT MAX(version) FROM schema_version").fetchone()
            return row[0] or 0
        except sqlite3.OperationalError:
            return 0

    # =========================================================================
    # Prompt CRUD
    # =========================================================================

    def add_prompt(
        self,
        content: str,
        *,
        title: str | None = None,
        description: str | None = None,
        technique: str = "uncategorized",
        complexity: str = "intermediate",
        attack_vector: str | None = None,
        source: str | None = None,
        source_id: str | None = None,
        author: str | None = None,
        language: str = "en",
        sophistication_score: int = 0,
        matched_patterns: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        tags: list[str] | None = None,
        categories: list[str] | None = None,
    ) -> int | None:
        """Add a prompt. Returns prompt ID, or None if duplicate."""
        ch = _content_hash(content)

        try:
            cursor = self.conn.execute(
                """
                INSERT INTO prompts (
                    content, content_hash, title, description, technique, complexity,
                    attack_vector, source, source_id, author, language,
                    sophistication_score, matched_patterns, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    content.strip(),
                    ch,
                    title,
                    description,
                    technique,
                    complexity,
                    attack_vector,
                    source,
                    source_id,
                    author,
                    language,
                    sophistication_score,
                    json.dumps(matched_patterns) if matched_patterns else None,
                    json.dumps(metadata) if metadata else None,
                ),
            )
            prompt_id = cursor.lastrowid
        except sqlite3.IntegrityError:
            # Duplicate content_hash
            return None

        if tags:
            self._apply_tags(prompt_id, tags)
        if categories:
            self._apply_categories(prompt_id, categories)

        self.conn.commit()
        return prompt_id

    def _apply_tags(self, prompt_id: int, tag_names: list[str]) -> None:
        for name in tag_names:
            self.conn.execute("INSERT OR IGNORE INTO tags (name) VALUES (?)", (name,))
            tag_id = self.conn.execute("SELECT id FROM tags WHERE name = ?", (name,)).fetchone()[0]
            self.conn.execute(
                "INSERT OR IGNORE INTO prompt_tags (prompt_id, tag_id) VALUES (?, ?)",
                (prompt_id, tag_id),
            )

    def _apply_categories(self, prompt_id: int, category_codes: list[str]) -> None:
        for code in category_codes:
            row = self.conn.execute("SELECT id FROM categories WHERE code = ?", (code,)).fetchone()
            if row:
                self.conn.execute(
                    "INSERT OR IGNORE INTO prompt_categories "
                    "(prompt_id, category_id) VALUES (?, ?)",
                    (prompt_id, row[0]),
                )

    def get_prompt(self, prompt_id: int) -> dict[str, Any] | None:
        """Get a single prompt by ID."""
        row = self.conn.execute("SELECT * FROM prompts WHERE id = ?", (prompt_id,)).fetchone()
        if not row:
            return None
        result = dict(row)
        result["tags"] = self._get_prompt_tags(prompt_id)
        result["categories"] = self._get_prompt_categories(prompt_id)
        return result

    def _get_prompt_tags(self, prompt_id: int) -> list[str]:
        rows = self.conn.execute(
            """
            SELECT t.name FROM tags t
            JOIN prompt_tags pt ON pt.tag_id = t.id
            WHERE pt.prompt_id = ?
            ORDER BY t.name
            """,
            (prompt_id,),
        ).fetchall()
        return [r[0] for r in rows]

    def _get_prompt_categories(self, prompt_id: int) -> list[dict[str, str]]:
        rows = self.conn.execute(
            """
            SELECT c.code, c.name, c.owasp_id FROM categories c
            JOIN prompt_categories pc ON pc.category_id = c.id
            WHERE pc.prompt_id = ?
            """,
            (prompt_id,),
        ).fetchall()
        return [{"code": r[0], "name": r[1], "owasp_id": r[2]} for r in rows]

    # =========================================================================
    # Search
    # =========================================================================

    def search(
        self,
        query: str,
        *,
        technique: str | None = None,
        complexity: str | None = None,
        min_sophistication: int | None = None,
        source: str | None = None,
        verified_only: bool = False,
        limit: int = 25,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """Full-text search across prompts using FTS5."""
        conditions = []
        params: list[Any] = []

        if technique:
            conditions.append("p.technique = ?")
            params.append(technique)
        if complexity:
            conditions.append("p.complexity = ?")
            params.append(complexity)
        if min_sophistication is not None:
            conditions.append("p.sophistication_score >= ?")
            params.append(min_sophistication)
        if source:
            conditions.append("p.source = ?")
            params.append(source)
        if verified_only:
            conditions.append("p.is_verified = 1")

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        if query.strip():
            # Use FTS5 for text search
            sql = f"""
                SELECT p.*, fts.rank
                FROM prompts_fts fts
                JOIN prompts p ON p.id = fts.rowid
                WHERE prompts_fts MATCH ? AND p.is_active = 1 AND {where_clause}
                ORDER BY fts.rank
                LIMIT ? OFFSET ?
            """
            params = [query] + params + [limit, offset]
        else:
            sql = f"""
                SELECT p.*, 0 as rank
                FROM prompts p
                WHERE p.is_active = 1 AND {where_clause}
                ORDER BY p.sophistication_score DESC, p.id
                LIMIT ? OFFSET ?
            """
            params = params + [limit, offset]

        rows = self.conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    def filter_prompts(
        self,
        *,
        technique: str | None = None,
        complexity: str | None = None,
        min_sophistication: int | None = None,
        max_sophistication: int | None = None,
        source: str | None = None,
        tag: str | None = None,
        category_code: str | None = None,
        verified_only: bool = False,
        curated_only: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """Filter prompts by various criteria without text search."""
        conditions = ["p.is_active = 1"]
        params: list[Any] = []
        joins: list[str] = []

        if technique:
            conditions.append("p.technique = ?")
            params.append(technique)
        if complexity:
            conditions.append("p.complexity = ?")
            params.append(complexity)
        if min_sophistication is not None:
            conditions.append("p.sophistication_score >= ?")
            params.append(min_sophistication)
        if max_sophistication is not None:
            conditions.append("p.sophistication_score <= ?")
            params.append(max_sophistication)
        if source:
            conditions.append("p.source = ?")
            params.append(source)
        if verified_only:
            conditions.append("p.is_verified = 1")
        if curated_only:
            conditions.append("p.is_curated = 1")
        if tag:
            joins.append(
                "JOIN prompt_tags pt ON pt.prompt_id = p.id JOIN tags t ON t.id = pt.tag_id"
            )
            conditions.append("t.name = ?")
            params.append(tag)
        if category_code:
            joins.append(
                "JOIN prompt_categories pc ON pc.prompt_id = p.id "
                "JOIN categories c ON c.id = pc.category_id"
            )
            conditions.append("c.code = ?")
            params.append(category_code)

        join_clause = " ".join(joins)
        where_clause = " AND ".join(conditions)

        sql = f"""
            SELECT DISTINCT p.*
            FROM prompts p {join_clause}
            WHERE {where_clause}
            ORDER BY p.sophistication_score DESC, p.id
            LIMIT ? OFFSET ?
        """
        params += [limit, offset]
        rows = self.conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    # =========================================================================
    # Statistics
    # =========================================================================

    def stats(self) -> dict[str, Any]:
        """Return database statistics."""
        total = self.conn.execute("SELECT COUNT(*) FROM prompts WHERE is_active = 1").fetchone()[0]
        verified = self.conn.execute(
            "SELECT COUNT(*) FROM prompts WHERE is_verified = 1"
        ).fetchone()[0]
        curated = self.conn.execute("SELECT COUNT(*) FROM prompts WHERE is_curated = 1").fetchone()[
            0
        ]
        test_count = self.conn.execute("SELECT COUNT(*) FROM test_results").fetchone()[0]
        variation_count = self.conn.execute("SELECT COUNT(*) FROM prompt_variations").fetchone()[0]

        by_technique = dict(
            self.conn.execute(
                "SELECT technique, COUNT(*) FROM prompts WHERE is_active = 1 "
                "GROUP BY technique ORDER BY COUNT(*) DESC"
            ).fetchall()
        )

        by_complexity = dict(
            self.conn.execute(
                "SELECT complexity, COUNT(*) FROM prompts WHERE is_active = 1 "
                "GROUP BY complexity ORDER BY COUNT(*) DESC"
            ).fetchall()
        )

        by_source = dict(
            self.conn.execute(
                "SELECT COALESCE(source, 'unknown'), COUNT(*) FROM prompts WHERE is_active = 1 "
                "GROUP BY source ORDER BY COUNT(*) DESC"
            ).fetchall()
        )

        avg_sophistication = self.conn.execute(
            "SELECT AVG(sophistication_score) FROM prompts WHERE is_active = 1"
        ).fetchone()[0]

        return {
            "total_prompts": total,
            "verified": verified,
            "curated": curated,
            "test_results": test_count,
            "variations": variation_count,
            "avg_sophistication": round(avg_sophistication or 0, 2),
            "by_technique": by_technique,
            "by_complexity": by_complexity,
            "by_source": by_source,
        }

    # =========================================================================
    # Test results
    # =========================================================================

    def add_test_result(
        self,
        prompt_id: int,
        *,
        target_model: str,
        actual_prompt: str,
        result: str,
        response: str | None = None,
        confidence_score: float | None = None,
        model_provider: str | None = None,
        tool_used: str | None = None,
        response_time_ms: float | None = None,
        prompt_tokens: int | None = None,
        completion_tokens: int | None = None,
        detected_refusal: bool = False,
        guardrail_bypassed: bool = False,
        session_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> int:
        """Record a test result and update the prompt's aggregate metrics."""
        cursor = self.conn.execute(
            """
            INSERT INTO test_results (
                prompt_id, target_model, actual_prompt, result, response,
                confidence_score, model_provider, tool_used, response_time_ms,
                prompt_tokens, completion_tokens, detected_refusal,
                guardrail_bypassed, session_id, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                prompt_id,
                target_model,
                actual_prompt,
                result,
                response,
                confidence_score,
                model_provider,
                tool_used,
                response_time_ms,
                prompt_tokens,
                completion_tokens,
                int(detected_refusal),
                int(guardrail_bypassed),
                session_id,
                json.dumps(metadata) if metadata else None,
            ),
        )

        # Update aggregate metrics on the prompt
        self._update_prompt_metrics(prompt_id)
        self.conn.commit()
        return cursor.lastrowid

    def _update_prompt_metrics(self, prompt_id: int) -> None:
        """Recompute success_rate, test_count, etc. from test_results."""
        row = self.conn.execute(
            """
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN result = 'SUCCESS' THEN 1 ELSE 0 END) as successes,
                SUM(CASE WHEN result = 'FAIL' THEN 1 ELSE 0 END) as failures,
                AVG(confidence_score) as avg_conf
            FROM test_results WHERE prompt_id = ?
            """,
            (prompt_id,),
        ).fetchone()

        total = row[0]
        successes = row[1] or 0
        rate = successes / total if total > 0 else 0.0

        self.conn.execute(
            """
            UPDATE prompts SET
                test_count = ?, success_count = ?, failure_count = ?,
                success_rate = ?, avg_confidence = ?, updated_at = datetime('now')
            WHERE id = ?
            """,
            (total, successes, row[2] or 0, rate, row[3], prompt_id),
        )

    # =========================================================================
    # Export
    # =========================================================================

    def export_prompts(
        self,
        *,
        technique: str | None = None,
        min_sophistication: int | None = None,
        verified_only: bool = False,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """Export prompts as a list of dicts for serialization."""
        conditions = ["is_active = 1"]
        params: list[Any] = []

        if technique:
            conditions.append("technique = ?")
            params.append(technique)
        if min_sophistication is not None:
            conditions.append("sophistication_score >= ?")
            params.append(min_sophistication)
        if verified_only:
            conditions.append("is_verified = 1")

        where = " AND ".join(conditions)
        limit_clause = f"LIMIT {limit}" if limit else ""

        rows = self.conn.execute(
            f"SELECT * FROM prompts WHERE {where} "
            f"ORDER BY sophistication_score DESC {limit_clause}",
            params,
        ).fetchall()

        results = []
        for row in rows:
            d = dict(row)
            d["tags"] = self._get_prompt_tags(d["id"])
            d["categories"] = self._get_prompt_categories(d["id"])
            # Parse JSON fields
            json_fields = (
                "matched_patterns",
                "target_models",
                "paper_ids",
                "cve_ids",
                "reference_urls",
            )
            for field in json_fields:
                if d.get(field) and isinstance(d[field], str):
                    try:
                        d[field] = json.loads(d[field])
                    except json.JSONDecodeError:
                        pass
            results.append(d)

        return results

    # =========================================================================
    # Bulk operations
    # =========================================================================

    @contextmanager
    def bulk_insert(self):
        """Context manager for efficient bulk inserts (defers commits)."""
        self.conn.execute("BEGIN TRANSACTION")
        try:
            yield
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise

    # =========================================================================
    # Random sampling
    # =========================================================================

    def random_prompts(
        self,
        count: int = 5,
        *,
        technique: str | None = None,
        min_sophistication: int | None = None,
    ) -> list[dict[str, Any]]:
        """Return random prompts from the database."""
        conditions = ["is_active = 1"]
        params: list[Any] = []

        if technique:
            conditions.append("technique = ?")
            params.append(technique)
        if min_sophistication is not None:
            conditions.append("sophistication_score >= ?")
            params.append(min_sophistication)

        where = " AND ".join(conditions)
        rows = self.conn.execute(
            f"SELECT * FROM prompts WHERE {where} ORDER BY RANDOM() LIMIT ?",
            params + [count],
        ).fetchall()
        return [dict(r) for r in rows]

    # =========================================================================
    # Model comparison
    # =========================================================================

    def compare_models(self) -> list[dict[str, Any]]:
        """Compare test results across different target models."""
        rows = self.conn.execute(
            """
            SELECT
                target_model,
                COUNT(*) as total_tests,
                SUM(CASE WHEN result = 'SUCCESS' THEN 1 ELSE 0 END) as successes,
                SUM(CASE WHEN result = 'FAIL' THEN 1 ELSE 0 END) as failures,
                SUM(CASE WHEN result = 'PARTIAL' THEN 1 ELSE 0 END) as partials,
                ROUND(
                    CAST(SUM(CASE WHEN result = 'SUCCESS' THEN 1 ELSE 0 END) AS REAL)
                    / COUNT(*), 3
                ) as attack_success_rate,
                ROUND(AVG(confidence_score), 3) as avg_confidence,
                ROUND(AVG(response_time_ms), 0) as avg_response_ms
            FROM test_results
            GROUP BY target_model
            ORDER BY attack_success_rate DESC
            """
        ).fetchall()
        return [dict(r) for r in rows]

    def compare_techniques(self, target_model: str | None = None) -> list[dict[str, Any]]:
        """Compare attack success rates by technique."""
        conditions = []
        params: list[Any] = []
        if target_model:
            conditions.append("tr.target_model = ?")
            params.append(target_model)

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        rows = self.conn.execute(
            f"""
            SELECT
                p.technique,
                COUNT(*) as total_tests,
                SUM(CASE WHEN tr.result = 'SUCCESS' THEN 1 ELSE 0 END) as successes,
                ROUND(
                    CAST(SUM(CASE WHEN tr.result = 'SUCCESS' THEN 1 ELSE 0 END) AS REAL)
                    / COUNT(*), 3
                ) as attack_success_rate
            FROM test_results tr
            JOIN prompts p ON p.id = tr.prompt_id
            {where}
            GROUP BY p.technique
            ORDER BY attack_success_rate DESC
            """,
            params,
        ).fetchall()
        return [dict(r) for r in rows]
